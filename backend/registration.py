from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StrictBool
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import engine
from models import Consent, User

router = APIRouter(prefix="/auth", tags=["Authentication"])
password_hasher = PasswordHash.recommended()

CONSENT_VERSION = "prototype-1"
CONSENT_TEXT = (
    "ENWEN is an academic prototype, not medical advice, diagnosis, "
    "or an emergency service. Use fictional information for this test. "
    "I agree to the storage of my test account and this consent record "
    "for prototype testing. This does not authorize contacting anyone."
)


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    display_name: str | None = Field(default=None, max_length=100)
    password: SecretStr = Field(min_length=12, max_length=128)
    consent_accepted: StrictBool
    consent_version: str = Field(min_length=1, max_length=30)


class RegistrationResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str | None


@router.get("/consent")
def get_consent_notice():
    return {"version": CONSENT_VERSION, "text": CONSENT_TEXT}


@router.post("/register", response_model=RegistrationResponse, status_code=201)
def register_account(data: RegistrationRequest):
    if not data.consent_accepted:
        raise HTTPException(400, "Consent is required to create a test account.")

    if data.consent_version != CONSENT_VERSION:
        raise HTTPException(409, "Please read and accept the current consent notice.")

    hashed_password = password_hasher.hash(data.password.get_secret_value())

    try:
        with Session(engine) as session:
            with session.begin():
                user = User(
                    email=str(data.email).lower(),
                    display_name=data.display_name,
                    password_hash=hashed_password,
                )
                session.add(user)
                session.flush()

                session.add(
                    Consent(
                        user_id=user.user_id,
                        consent_type="wellness_use",
                        notice_version=CONSENT_VERSION,
                        notice_text=CONSENT_TEXT,
                        decision="accepted",
                    )
                )

                response = RegistrationResponse(
                    user_id=user.user_id,
                    email=user.email,
                    display_name=user.display_name,
                )

    except IntegrityError as error:
        constraint = getattr(
            getattr(error.orig, "diag", None), "constraint_name", None
        )
        if (
            getattr(error.orig, "sqlstate", None) == "23505"
            and constraint == "users_email_key"
        ):
            raise HTTPException(
                409, "An account with this email already exists."
            ) from None

        raise HTTPException(503, "Registration could not be saved.") from None

    except SQLAlchemyError:
        raise HTTPException(503, "Registration could not be saved.") from None

    return response