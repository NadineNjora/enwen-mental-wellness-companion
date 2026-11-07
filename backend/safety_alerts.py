"""Record and demonstrate a trusted-contact support notification locally.

This module NEVER sends SMS, real email, a user's name or any chat content.
The existing contact confirmation and consent are prototype-test decisions.
"""
import re
from datetime import timedelta
from smtplib import SMTPException
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from authentication import AccountResponse, get_current_user
from database import engine
from mail_service import TestEmailDeliveryError, send_test_email
from models import Consent, User
from registration import CONSENT_VERSION, CONTACT_CONSENT_VERSION
from safety_models import SafetyAlert
from trusted_contact_models import TrustedContact

router = APIRouter(prefix="/safety/alerts", tags=["Support notification status"])
COOLDOWN = timedelta(minutes=10)
TEST_ADDRESS = re.compile(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*@example\.com")
TEST_SUBJECT = "ENWEN local support-flow demonstration"
TEST_BODY = (
    "SYNTHETIC ENWEN LOCAL SUPPORT-FLOW DEMONSTRATION.\n\n"
    "This message demonstrates the prototype's trusted-contact notification path. "
    "It does not report a real emergency and does not request an emergency response. "
    "No chat, journal, mood, account or phone details are included. "
    "This message is captured only in Mailpit on the computer running ENWEN. "
    "No real person has been contacted."
)
MESSAGES = {
    "local_test_captured": "A clearly synthetic support-flow email was captured in local Mailpit. No real person or phone was contacted.",
    "blocked_no_contact": "No trusted contact is saved. No notification was sent. Use the support contacts shown here directly.",
    "blocked_unconfirmed": "Your trusted contact has not accepted, or their agreement was declined or revoked. No notification was sent.",
    "blocked_consent": "Current contact-testing permission is not recorded. No notification was sent.",
    "blocked_live_not_configured": "Real trusted-contact delivery is not configured or authorised. No notification was sent. Local test invitations do not verify a real phone or mailbox.",
    "blocked_cooldown": "A recent local support notification is already recorded for this contact. No duplicate notification was sent.",
    "uncertain": "Local notification capture is unconfirmed. Check Mailpit and the recorded status before retrying; nothing was automatically resent.",
}


def _result(event_id, status):
    # A committed claim with no completion may be in flight or have been
    # interrupted. Neither case is safe to describe as sent or to retry.
    public_status = "uncertain" if status == "dispatching" else status
    return {"event_id": str(event_id), "alert": {"status": public_status, "message": MESSAGES[public_status]}}


def _permissions_current(session, user_id):
    for consent_type, version in (("wellness_use", CONSENT_VERSION), ("contact_alert", CONTACT_CONSENT_VERSION)):
        consent = session.scalar(select(Consent).where(
            Consent.user_id == user_id, Consent.consent_type == consent_type,
        ).order_by(Consent.recorded_at.desc(), Consent.consent_id.desc()).limit(1))
        if consent is None or consent.decision != "accepted" or consent.notice_version != version:
            return False
    return True


def create_alert(user_id, request_id, conversation_id=None, demonstration=False):
    """Commit one request outcome before attempting the local-only transport.

    The caller provides the authenticated user_id; never use a body-provided
    user identifier. A replay returns its recorded outcome without resending.
    Database errors propagate so the caller can still show support resources
    while honestly reporting that recording/capture could not be confirmed.
    """
    user_id, request_id = UUID(str(user_id)), UUID(str(request_id))
    conversation_id = UUID(str(conversation_id)) if conversation_id is not None else None
    if not isinstance(demonstration, bool):
        raise ValueError("demonstration must be a boolean")
    recipient = None
    with Session(engine) as session:
        with session.begin():
            # One account has one trusted contact; serialising the account
            # protects first insert/replay and cooldown checks across workers.
            user = session.scalar(select(User).where(User.user_id == user_id).with_for_update())
            if user is None:
                raise HTTPException(401, "Please log in again.")
            existing = session.scalar(select(SafetyAlert).where(
                SafetyAlert.user_id == user_id, SafetyAlert.request_id == request_id,
            ))
            if existing is not None:
                return _result(existing.event_id, existing.status)
            contact = session.scalar(select(TrustedContact).where(
                TrustedContact.user_id == user_id,
            ).with_for_update())
            now = session.scalar(select(func.clock_timestamp()))
            status = "blocked_no_contact"
            if contact is not None:
                if contact.confirmation_status != "confirmed":
                    status = "blocked_unconfirmed"
                elif not _permissions_current(session, user_id):
                    status = "blocked_consent"
                elif not TEST_ADDRESS.fullmatch(contact.email.strip().lower()):
                    status = "blocked_live_not_configured"
                else:
                    recent = session.scalar(select(SafetyAlert.event_id).where(
                        SafetyAlert.contact_id == contact.contact_id,
                        SafetyAlert.created_at > now - COOLDOWN,
                        SafetyAlert.status.in_(("dispatching", "local_test_captured", "uncertain")),
                    ).limit(1))
                    status = "blocked_cooldown" if recent is not None else "dispatching"
                    if status == "dispatching":
                        recipient = contact.email.strip().lower()
            record = SafetyAlert(user_id=user_id, request_id=request_id, conversation_id=conversation_id,
                contact_id=contact.contact_id if contact else None, status=status, demonstration=demonstration,
                created_at=now, completed_at=None if status == "dispatching" else now)
            session.add(record)
            session.flush()
            event_id = record.event_id
        # The claim is committed here BEFORE SMTP. If a process dies after
        # capture, the dispatching record prevents another automatic send.
    if recipient is None:
        return _result(event_id, status)

    status = "local_test_captured"
    try:
        send_test_email(recipient=recipient, subject=TEST_SUBJECT, body=TEST_BODY)
    except (TestEmailDeliveryError, OSError, SMTPException, ValueError):
        status = "uncertain"
    with Session(engine) as session:
        with session.begin():
            record = session.scalar(select(SafetyAlert).where(
                SafetyAlert.event_id == event_id, SafetyAlert.user_id == user_id,
            ).with_for_update())
            if record is None:
                # A missing claim must never be repaired by resending.
                return _result(event_id, "uncertain")
            if record.status == "dispatching":
                record.status = status
                record.completed_at = session.scalar(select(func.clock_timestamp()))
            return _result(record.event_id, record.status)


def get_own_event(user_id, event_id):
    with Session(engine) as session:
        event = session.scalar(select(SafetyAlert).where(
            SafetyAlert.event_id == UUID(str(event_id)), SafetyAlert.user_id == UUID(str(user_id)),
        ))
        if event is None:
            raise HTTPException(404, "Support notification was not found.")
        return _result(event.event_id, event.status)


@router.get("/{event_id}")
def read_alert(event_id: UUID, response: Response, user: AccountResponse = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return get_own_event(user.user_id, event_id)
