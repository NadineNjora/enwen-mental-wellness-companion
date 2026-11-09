from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StrictBool,
    field_validator,
)
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import engine
from models import Consent, User
from trusted_contact_models import TrustedContact


router = APIRouter(prefix="/auth", tags=["Authentication"])
password_hasher = PasswordHash.recommended()


# Keep the existing wellness notice unchanged.
CONSENT_VERSION = "prototype-1"

CONSENT_TEXT = (
    "ENWEN is an academic prototype, not medical advice, diagnosis, "
    "or an emergency service. Use fictional information for this test. "
    "I agree to the storage of my test account and this consent record "
    "for prototype testing. This does not authorize contacting anyone."
)


# Separate permission for fictional contact testing only.
CONTACT_CONSENT_VERSION = "contact-test-1"

CONTACT_CONSENT_TEXT = (
    "Use fictional trusted-contact details only. I agree to storing "
    "the fictional contact's name, relationship and email with my test "
    "account to test contact setup and simulated notifications. "
    "No invitation or safety-alert email will be sent at this stage. "
    "This permission does not authorize live email. Live notifications "
    "will require a new notice, fresh permission and confirmation "
    "from the nominated contact. ENWEN is not an emergency service."
)


class TrustedContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=100)
    relationship_label: str | None = Field(default=None, max_length=50)
    email: EmailStr = Field(max_length=254)

    @field_validator("full_name", "relationship_label")
    @classmethod
    def clean_contact_text(cls, value):
        if value is None:
            return None

        value = value.strip()

        if not value or "\x00" in value:
            raise ValueError(
                "Use non-blank text without null characters."
            )

        return value


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    display_name: str | None = Field(default=None, max_length=100)
    password: SecretStr = Field(min_length=12, max_length=128)

    consent_accepted: StrictBool
    consent_version: str = Field(min_length=1, max_length=30)

    trusted_contact: TrustedContactRequest
    contact_consent_accepted: StrictBool
    contact_consent_version: str = Field(min_length=1, max_length=30)
    invite_contact_by_email: StrictBool = False
    invitation_notice_version: str | None = Field(default=None,max_length=40)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value):
        if value is None:
            return None

        value = value.strip()

        if not value or "\x00" in value:
            raise ValueError(
                "Use a non-blank name without null characters."
            )

        return value


# Authentication imports this class.
# Keep its response fields unchanged.
class RegistrationResponse(BaseModel):
    user_id: UUID
    email: str
    display_name: str | None


class RegistrationResult(RegistrationResponse):
    contact_invitation_status: str | None = None


@router.get("/consent")
def get_consent_notice(response: Response):
    response.headers["Cache-Control"] = "no-store"

    return {
        "version": CONSENT_VERSION,
        "text": CONSENT_TEXT,
    }


@router.get("/contact-consent")
def get_contact_consent_notice(response: Response):
    response.headers["Cache-Control"] = "no-store"

    return {
        "version": CONTACT_CONSENT_VERSION,
        "text": CONTACT_CONSENT_TEXT,
        "delivery_mode": "simulation_only",
    }


@router.post(
    "/register",
    response_model=RegistrationResult,
    status_code=201,
)
def register_account(data: RegistrationRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    from signup_invitations import VERSION as INVITE_VERSION,choice_for,dispatch_once
    if data.invite_contact_by_email and data.invitation_notice_version!=INVITE_VERSION:
        raise HTTPException(409,'Read the current signup invitation notice before choosing email.')

    if not data.consent_accepted:
        raise HTTPException(
            400,
            "Consent is required to create a test account.",
        )

    if data.consent_version != CONSENT_VERSION:
        raise HTTPException(
            409,
            "Please read and accept the current consent notice.",
        )

    if not data.contact_consent_accepted:
        raise HTTPException(
            400,
            "Accept the contact-testing notice before saving contact details.",
        )

    if data.contact_consent_version != CONTACT_CONSENT_VERSION:
        raise HTTPException(
            409,
            "Please read and accept the current contact-testing notice.",
        )

    email = str(data.email).lower()
    contact_email = str(data.trusted_contact.email).lower()

    if email == contact_email:
        raise HTTPException(
            400,
            "Use a different email for your trusted contact.",
        )

    hashed_password = password_hasher.hash(
        data.password.get_secret_value()
    )

    try:
        with Session(engine) as session:
            with session.begin():
                user = User(
                    email=email,
                    display_name=data.display_name,
                    password_hash=hashed_password,
                )

                session.add(user)
                session.flush()
                if data.invite_contact_by_email:
                    session.add(choice_for(user.user_id,data.trusted_contact))

                session.add_all([
                    Consent(
                        user_id=user.user_id,
                        consent_type="wellness_use",
                        notice_version=CONSENT_VERSION,
                        notice_text=CONSENT_TEXT,
                        decision="accepted",
                    ),
                    Consent(
                        user_id=user.user_id,
                        consent_type="contact_alert",
                        notice_version=CONTACT_CONSENT_VERSION,
                        notice_text=CONTACT_CONSENT_TEXT,
                        decision="accepted",
                    ),
                    TrustedContact(
                        user_id=user.user_id,
                        full_name=data.trusted_contact.full_name,
                        relationship_label=(
                            data.trusted_contact.relationship_label
                        ),
                        email=contact_email,
                        confirmation_status="pending",
                        confirmed_at=None,
                    ),
                ])

                result = RegistrationResult(
                    user_id=user.user_id,
                    email=user.email,
                    display_name=user.display_name,
                )

    except IntegrityError as error:
        constraint = getattr(
            getattr(error.orig, "diag", None),
            "constraint_name",
            None,
        )

        if (
            getattr(error.orig, "sqlstate", None) == "23505"
            and constraint == "users_email_key"
        ):
            raise HTTPException(
                409,
                "An account with this email already exists.",
            ) from None

        raise HTTPException(
            503,
            "Registration could not be saved.",
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            503,
            "Registration could not be saved.",
        ) from None

    if data.invite_contact_by_email:
        try:result.contact_invitation_status=dispatch_once(result.user_id)
        except Exception:result.contact_invitation_status='uncertain'
    else:result.contact_invitation_status='not_requested'
    return result
