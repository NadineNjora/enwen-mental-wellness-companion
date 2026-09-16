import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr
from pwdlib.exceptions import UnknownHashError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import engine
from models import Consent, User
from registration import CONSENT_VERSION, RegistrationResponse, password_hasher

load_dotenv(Path(__file__).with_name(".env"))
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if len(JWT_SECRET) < 64:
    raise RuntimeError("Set JWT_SECRET in your backend .env using the generated key.")

ALGORITHM = "HS256"
ISSUER = "enwen-api"
AUDIENCE = "enwen-client"
TOKEN_MINUTES = 15
DUMMY_HASH = password_hasher.hash("dummy-password-not-an-account")

router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_MINUTES * 60


class AccountResponse(RegistrationResponse):
    wellness_consent_current: bool


def unauthorized(message="Invalid or expired login token."):
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, response: Response):
    try:
        with Session(engine) as session:
            user = session.scalar(
                select(User).where(User.email == str(data.email).lower())
            )
            stored_hash = user.password_hash if user else DUMMY_HASH
            password_ok = password_hasher.verify(
                data.password.get_secret_value(), stored_hash
            )
            if not password_ok or user is None:
                raise unauthorized("Incorrect email or password.")

            user_id = str(user.user_id)

    except UnknownHashError:
        raise unauthorized("Incorrect email or password.") from None
    except SQLAlchemyError:
        raise HTTPException(503, "Login is temporarily unavailable.") from None

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(minutes=TOKEN_MINUTES),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "type": "access",
        },
        JWT_SECRET,
        algorithm=ALGORITHM,
    )
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=token)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None:
        raise unauthorized("Please log in first.")

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["sub", "iat", "exp", "iss", "aud", "type"]},
        )
        if payload["type"] != "access":
            raise unauthorized()
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, ValueError, TypeError):
        raise unauthorized() from None

    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user is None:
                raise unauthorized()

            latest_consent = session.scalar(
                select(Consent)
                .where(
                    Consent.user_id == user_id,
                    Consent.consent_type == "wellness_use",
                )
                .order_by(Consent.recorded_at.desc(), Consent.consent_id.desc())
                .limit(1)
            )
            consent_current = (
                latest_consent is not None
                and latest_consent.decision == "accepted"
                and latest_consent.notice_version == CONSENT_VERSION
            )
            return AccountResponse(
                user_id=user.user_id,
                email=user.email,
                display_name=user.display_name,
                wellness_consent_current=consent_current,
            )

    except SQLAlchemyError:
        raise HTTPException(
            503, "Account details are temporarily unavailable."
        ) from None


@router.get("/me", response_model=AccountResponse)
def my_account(
    response: Response,
    current_user: AccountResponse = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return current_user