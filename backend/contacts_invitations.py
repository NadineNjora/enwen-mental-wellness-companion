
import hashlib
import re
import secrets
from contextlib import contextmanager
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AccountResponse, get_current_user
from contact_invitation_models import TrustedContactInvitation
from database import engine
from mail_service import TestEmailDeliveryError, send_test_email
from models import Consent, User
from registration import CONSENT_VERSION, CONTACT_CONSENT_VERSION, CONTACT_CONSENT_TEXT, TrustedContactRequest
from trusted_contact_models import TrustedContact


router = APIRouter(
    prefix="/trusted-contact", tags=["Trusted contact (local test)"]
)

NOTICE_VERSION = "local-invite-1"
NOTICE_TEXT = (
    "This is fictional ENWEN prototype testing. Invitations are captured "
    "on this computer in Mailpit, not delivered to a real person. Accept "
    "or Decline records only a test decision. It does not verify real "
    "mailbox ownership, authorise live alerts or give access to private "
    "journals. ENWEN is not an emergency service."
)
NO_STORE = {"Cache-Control": "no-store"}
TEST_ADDRESS = re.compile(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*@example\.com")
RESPONSE_PAGE = "http://127.0.0.1:8000/static/contacts_response.html"


class InvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notice_version: str = Field(min_length=1, max_length=30)
    test_only_acknowledged: StrictBool


class InvitationDecision(InvitationRequest):
    token: SecretStr = Field(min_length=43, max_length=43)
    decision: Literal["accepted", "declined"]


class ContactSetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trusted_contact: TrustedContactRequest
    contact_consent_accepted: StrictBool
    contact_consent_version: str = Field(min_length=1, max_length=30)


def reject(status: int, message: str):
    raise HTTPException(status, message, headers=NO_STORE)


@contextmanager
def transaction():
    try:
        with Session(engine) as session:
            with session.begin():
                yield session
    except SQLAlchemyError:
        reject(503, "The database operation could not be confirmed. Check status before retrying.")


def check_notice(data: InvitationRequest):
    if data.notice_version != NOTICE_VERSION:
        reject(409, "Please read the current local invitation notice.")
    if not data.test_only_acknowledged:
        reject(400, "Acknowledge the local-test notice before continuing.")


def test_permissions_current(session: Session, user_id):
    # Read the latest decision, not any historical acceptance.
    for consent_type, version in (
        ("wellness_use", CONSENT_VERSION),
        ("contact_alert", CONTACT_CONSENT_VERSION),
    ):
        consent = session.scalar(
            select(Consent)
            .where(Consent.user_id == user_id, Consent.consent_type == consent_type)
            .order_by(Consent.recorded_at.desc(), Consent.consent_id.desc())
            .limit(1)
        )
        if consent is None or consent.decision != "accepted" or consent.notice_version != version:
            return False
    return True


def require_test_permissions(session: Session, user_id):
    if not test_permissions_current(session, user_id):
        reject(403, "Current wellness and contact-testing permission are required.")


@router.get("/invitation-notice")
def invitation_notice(response: Response):
    response.headers.update(NO_STORE)
    return {
        "notice_version": NOTICE_VERSION,
        "text": NOTICE_TEXT,
        "delivery_mode": "local_test",
    }


@router.get("")
def my_trusted_contact(
    response: Response,
    current_user: AccountResponse = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    with transaction() as session:
        contact = session.scalar(
            select(TrustedContact).where(TrustedContact.user_id == current_user.user_id)
        )
        if contact is None:
            reject(404, "This account has no trusted contact yet. Add your person to get started.")
        latest = session.scalar(
            select(TrustedContactInvitation)
            .where(TrustedContactInvitation.contact_id == contact.contact_id)
            .order_by(TrustedContactInvitation.created_at.desc(), TrustedContactInvitation.invitation_id.desc())
            .limit(1)
        )
        now = session.scalar(select(func.clock_timestamp()))
        retry_after = max(0, 60 - int((now - latest.created_at).total_seconds())) if latest else 0
        latest_status = None
        if latest:
            latest_status = latest.decision or (
                "revoked" if latest.revoked_at else
                "expired" if latest.expires_at <= now else "awaiting_response"
            )
        reason = None
        if contact.confirmation_status != "pending":
            reason = "This contact has already responded or was revoked."
        elif not test_permissions_current(session, current_user.user_id):
            reason = "Current wellness and contact-testing permission are required."
        elif not TEST_ADDRESS.fullmatch(contact.email.strip().lower()):
            reason = "Local tests require a fictional @example.com contact. Real email delivery is disabled."
        elif retry_after:
            reason = "Please wait before requesting another test invitation."
        result = {
            "full_name": contact.full_name,
            "email": contact.email,
            "relationship_label": contact.relationship_label,
            "confirmation_status": contact.confirmation_status,
            "confirmed_at": contact.confirmed_at,
            "delivery_mode": "local_test",
            "live_notifications_enabled": False,
            "can_invite": reason is None,
            "invitation_block_reason": reason,
            "retry_after_seconds": retry_after,
            "latest_invitation": None if latest is None else {
                "status": latest_status,
                "created_at": latest.created_at,
                "expires_at": latest.expires_at,
            },
        }
    return result


@router.post("", status_code=201)
def add_trusted_contact(data: ContactSetupRequest, response: Response, current_user: AccountResponse = Depends(get_current_user)):
    response.headers.update(NO_STORE)
    if not current_user.wellness_consent_current:
        reject(403, "Current wellness consent is required.")
    if not data.contact_consent_accepted:
        reject(400, "Please read and accept the trusted-contact notice.")
    if data.contact_consent_version != CONTACT_CONSENT_VERSION:
        reject(409, "The trusted-contact notice has changed. Please read it again.")
    email = str(data.trusted_contact.email).strip().lower()
    if email == current_user.email.strip().lower():
        reject(400, "Your trusted person must have a different email address from yours.")
    with transaction() as session:
        # Serialise competing requests for the same account; never overwrite a person.
        if session.scalar(select(User).where(User.user_id == current_user.user_id).with_for_update()) is None:
            reject(401, "Please log in again.")
        if session.scalar(select(TrustedContact.contact_id).where(TrustedContact.user_id == current_user.user_id)):
            reject(409, "A trusted person is already saved. Refresh to view them.")
        contact = TrustedContact(user_id=current_user.user_id, full_name=data.trusted_contact.full_name,
            relationship_label=data.trusted_contact.relationship_label, email=email, confirmation_status="pending")
        session.add(contact)
        session.add(Consent(user_id=current_user.user_id, consent_type="contact_alert",
            notice_version=CONTACT_CONSENT_VERSION, notice_text=CONTACT_CONSENT_TEXT, decision="accepted"))
        session.flush()
        result = {"contact_id": str(contact.contact_id), "confirmation_status": "pending", "full_name": contact.full_name}
    return result


@router.post("/invitations", status_code=201)
def create_test_invitation(
    data: InvitationRequest,
    response: Response,
    current_user: AccountResponse = Depends(get_current_user),
):
    response.headers.update(NO_STORE)
    check_notice(data)

    try:
        with transaction() as session:
            # Lock the contact first, also in the response endpoint below.
            contact = session.scalar(
                select(TrustedContact)
                .where(TrustedContact.user_id == current_user.user_id)
                .with_for_update()
            )
            if contact is None:
                reject(404, "Add your trusted person before preparing an invitation.")
            require_test_permissions(session, current_user.user_id)
            if contact.confirmation_status != "pending":
                reject(409, "This contact has already responded or was revoked. No invitation was sent.")
            recipient = contact.email.strip().lower()
            if not TEST_ADDRESS.fullmatch(recipient):
                reject(400, "Use a fictional contact ending in @example.com. Gmail/Yahoo delivery is disabled.")

            now = session.scalar(select(func.clock_timestamp()))
            last_created = session.scalar(
                select(func.max(TrustedContactInvitation.created_at))
                .where(TrustedContactInvitation.contact_id == contact.contact_id)
            )
            if last_created and now - last_created < timedelta(seconds=60):
                reject(429, "Wait at least 60 seconds between invitation requests.")

            # A replacement invalidates the previous unused link, including expired ones.
            session.execute(
                update(TrustedContactInvitation)
                .where(
                    TrustedContactInvitation.contact_id == contact.contact_id,
                    TrustedContactInvitation.used_at.is_(None),
                    TrustedContactInvitation.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            raw_token = secrets.token_urlsafe(32)
            invitation = TrustedContactInvitation(
                contact_id=contact.contact_id,
                token_hash=hashlib.sha256(raw_token.encode("ascii")).hexdigest(),
                delivery_mode="local_test",
                created_at=now,
                expires_at=now + timedelta(hours=24),
            )
            session.add(invitation)
            session.flush()

            # A URL fragment keeps the secret out of HTTP paths and access logs.
            link = RESPONSE_PAGE + "#token=" + raw_token
            send_test_email(
                recipient=recipient,
                subject="Practise responding to an ENWEN trusted-contact invitation",
                body=(
                    "A fictional trusted contact has been nominated for this local demo.\n\n"
                    "Open this link on the same computer running ENWEN:\n"
                    + link
                    + "\n\nOpening the page does not accept the invitation. "
                    "Choose Accept or Decline on the page.\n"
                    + "This one-use link expires at "
                    + invitation.expires_at.isoformat()
                    + ". A replacement invitation invalidates this link.\n\n"
                    + NOTICE_TEXT
                ),
            )
            result = {
                "invitation_id": str(invitation.invitation_id),
                "expires_at": invitation.expires_at,
                "delivery_mode": "local_test",
                "message": "Invitation captured by Mailpit. The contact is still pending.",
            }
    except TestEmailDeliveryError:
        # Rollback invalidates any new link captured during an uncertain SMTP failure.
        reject(503, "Capture could not be confirmed. Check Mailpit; any new link from this failed attempt may be invalid. No automatic retry occurred.")
    return result


@router.post("/invitations/respond")
def respond_to_test_invitation(data: InvitationDecision, response: Response):
    response.headers.update(NO_STORE)
    check_notice(data)
    raw_token = data.token.get_secret_value()
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw_token):
        reject(410, "This invitation is invalid, expired, replaced or already used.")
    digest = hashlib.sha256(raw_token.encode("ascii")).hexdigest()

    with transaction() as session:
        contact_id = session.scalar(
            select(TrustedContactInvitation.contact_id)
            .where(TrustedContactInvitation.token_hash == digest)
        )
        if contact_id is None:
            reject(410, "This invitation is invalid, expired, replaced or already used.")
        contact = session.scalar(
            select(TrustedContact).where(TrustedContact.contact_id == contact_id).with_for_update()
        )
        invitation = session.scalar(
            select(TrustedContactInvitation)
            .where(TrustedContactInvitation.token_hash == digest)
            .with_for_update()
        )
        now = session.scalar(select(func.clock_timestamp()))
        if (
            contact is None
            or invitation is None
            or contact.confirmation_status != "pending"
            or invitation.delivery_mode != "local_test"
            or invitation.used_at is not None
            or invitation.revoked_at is not None
            or invitation.expires_at <= now
        ):
            reject(410, "This invitation is invalid, expired, replaced or already used.")
        require_test_permissions(session, contact.user_id)
        invitation.decision = data.decision
        invitation.used_at = now
        contact.confirmation_status = "confirmed" if data.decision == "accepted" else "declined"
        contact.confirmed_at = now if data.decision == "accepted" else None
        result = {
            "decision": data.decision,
            "confirmation_status": contact.confirmation_status,
            "delivery_mode": "local_test",
            "live_notifications_enabled": False,
            "message": "Test response recorded. No real mailbox was verified and no live alerts are enabled.",
        }
    return result
