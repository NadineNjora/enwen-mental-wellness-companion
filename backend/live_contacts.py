"""Explicit real-email invitations. No SMS, clinical decision or automatic alert."""
import hashlib
import ipaddress
import os
import re
import secrets
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StrictBool, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from authentication import AccountResponse, get_current_user
from database import engine
from email_service import EmailServiceError
from live_contact_models import LiveContactInvitation as Invitation
from models import User, Consent
from registration import CONSENT_VERSION

router = APIRouter(prefix="/trusted-contact/live", tags=["Real email contact enrollment"])
VERSION = "live-email-invite-1"
NOTICE = ("I agree to store this person's name and email and ask them by real email to be my trusted contact. "
          "I have their permission to provide these details. The email shares my ENWEN display name and a secure response link, "
          "not my chats, journals, mood history or diagnosis. They may decline or withdraw. "
          "Accepting enrolls them as a contact; automatic wellness alerts and SMS are not enabled by this invitation.")
RECIPIENT_VERSION = "live-recipient-2"
RECIPIENT_NOTICE = ("An ENWEN student nominated you as a trusted contact. Accepting confirms possession of this invitation link "
    "and your agreement to be recorded as their contact. It does not give access to private records, require a clinical role "
    "or guarantee an emergency response. You agree to receive minimal wellbeing check-in emails if the student separately enables them. "
    "These automated signals can be wrong; no private message text is included. Acceptance alone does not activate alerts. SMS is not included. "
    "You may decline now or withdraw using the separate link in your email. ENWEN is not an emergency service.")

def reject(code, message):
    raise HTTPException(code, message, headers={"Cache-Control":"no-store"})

def local_demo():
    return os.getenv('CONTACT_DELIVERY_MODE','production').strip().lower()=='local_demo'

def demo_recipient():
    from email_validator import validate_email
    value=validate_email(os.getenv('LOCAL_DEMO_RECIPIENT','').strip(),check_deliverability=False).normalized.lower()
    if value!=os.getenv('EMAIL_FROM_ADDRESS','').strip().lower():
        raise ValueError('Local demonstration recipient must be the verified sender mailbox.')
    return value

def public_origin():
    value = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/") or parsed.port not in (None,443):
        raise ValueError("A public HTTPS application origin is required.")
    if host == "localhost" or "." not in host or host.endswith((".localhost", ".local", ".internal", ".test", ".example", ".invalid")):
        raise ValueError("A public HTTPS application origin is required.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return value
    raise ValueError("Use a deployed application hostname, not a local address.")

def configuration():
    if local_demo():
        demo_recipient()
        if not os.getenv('LOCAL_DEMO_USER_EMAIL','').strip():raise ValueError('Choose the demonstration student account.')
        origin='http://127.0.0.1:8000'
    else:origin = public_origin()
    if os.getenv("LIVE_CONTACT_EMAIL_ENABLED", "false").lower() != "true":
        raise ValueError("Real contact invitations are not enabled on this installation.")
    if os.getenv("EMAIL_SENDER_VERIFIED", "false").lower() != "true" or not os.getenv("BREVO_API_KEY", "").strip():
        raise ValueError("The verified email sender and API key must be configured.")
    sender = os.getenv("EMAIL_FROM_ADDRESS", "").strip()
    # This only checks local settings. The provider still decides account access.
    from email_validator import validate_email
    sender = validate_email(sender, check_deliverability=False).normalized
    return origin, sender

class Enroll(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=254)
    notice_version: str = Field(max_length=40)
    acknowledged: StrictBool
    @field_validator("full_name")
    @classmethod
    def name(cls, value):
        value = " ".join(value.split())
        if not value or any(ord(c)<32 for c in value): raise ValueError("Enter a name without control characters.")
        return value

class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=43, max_length=43)
    decision: str = Field(pattern="^(accepted|declined|withdraw)$")
    notice_version: str = Field(max_length=40)
    acknowledged: StrictBool

def digest(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()

def summary(row, now):
    state = "revoked" if row.revoked_at else row.decision or ("expired" if row.expires_at <= now else "pending")
    return {"invitation_id":str(row.invitation_id), "full_name":row.full_name, "email":row.email,
            "status":state,"delivery_status":"uncertain" if row.delivery_status=="dispatching" else row.delivery_status,
            "created_at":row.created_at,"expires_at":row.expires_at,"automatic_alerts_enabled":False}

@router.get("/notice")
def notice(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        configuration(); ready=True; reason=("Local presentation demo: real email goes only to your verified mailbox. Open invitation links on this computer; this is not public deployment." if local_demo() else "Ready for a deliberate invitation.")
    except (ValueError, TypeError):
        ready=False; reason="Real invitations require an enabled Brevo sender and a deployed public HTTPS response page."
    return {"notice_version":VERSION,"text":NOTICE,"short_text":"I have this person’s permission to share their name and email. This invitation shares my display name and response links, never my private entries. They can decline or withdraw. Check-in emails need my separate permission.","recipient_notice_version":RECIPIENT_VERSION,
            "recipient_text":RECIPIENT_NOTICE,"ready":ready,"reason":reason,"automatic_alerts_enabled":False}

@router.get("")
def own(response: Response, user: AccountResponse=Depends(get_current_user)):
    response.headers["Cache-Control"]="no-store"
    try:
        with Session(engine) as db:
            row=db.scalar(select(Invitation).where(Invitation.user_id==user.user_id).order_by(Invitation.created_at.desc(),Invitation.invitation_id.desc()).limit(1))
            return summary(row,db.scalar(select(func.clock_timestamp()))) if row else None
    except SQLAlchemyError: reject(503,"Invitation status is unavailable. Nothing was sent.")


@router.get('/capability')
def capability(response:Response,user:AccountResponse=Depends(get_current_user)):
    value=notice(response)
    if local_demo() and user.email.lower()!=os.getenv('LOCAL_DEMO_USER_EMAIL','').strip().lower():
        value['ready']=False
        value['reason']='Email invitations are currently limited to the approved presentation account. Wider sending needs the public website setup.'
    return value

def send_real_invitation(recipient, sender, body, subject="An ENWEN trusted-contact invitation"):
    try:
        with httpx.Client(timeout=httpx.Timeout(15,connect=5),follow_redirects=False,trust_env=False) as client:
            reply=client.post("https://api.brevo.com/v3/smtp/email",headers={"api-key":os.environ["BREVO_API_KEY"],"Accept":"application/json"},
                json={"sender":{"name":"ENWEN","email":sender},"to":[{"email":recipient}],
                      "subject":subject,"textContent":body})
        if reply.status_code!=201: raise EmailServiceError("Acceptance unconfirmed")
        reference=reply.json().get("messageId")
        if not isinstance(reference,str) or not reference.strip() or len(reference)>512: raise EmailServiceError("Acceptance unconfirmed")
        return reference
    except (httpx.HTTPError,ValueError,TypeError,AttributeError,KeyError):
        raise EmailServiceError("Acceptance unconfirmed") from None

@router.post("",status_code=201)
def invite(data: Enroll,response: Response,user: AccountResponse=Depends(get_current_user)):
    response.headers["Cache-Control"]="no-store"
    if not user.wellness_consent_current: reject(403,"Current wellness consent is required.")
    if data.notice_version!=VERSION or not data.acknowledged: reject(409,"Read and accept the current real-email notice.")
    recipient=str(data.email).lower()
    if local_demo() and (recipient!=demo_recipient() or user.email.lower()!=os.getenv('LOCAL_DEMO_USER_EMAIL','').strip().lower()):
        reject(403,'Local presentation invitations are restricted to the configured demo account and verified mailbox.')
    if recipient==user.email.lower(): reject(400,"Choose a trusted person with a different mailbox from your account.")
    if recipient.rsplit("@",1)[1] in ("example.com","example.net","example.org"): reject(400,"Use the local invitation flow for fictional addresses.")
    try:
        with Session(engine) as db,db.begin():
            if db.scalar(select(User.user_id).where(User.user_id==user.user_id).with_for_update()) is None: reject(401,"Please log in again.")
            now=db.scalar(select(func.clock_timestamp()))
            previous=db.scalar(select(Invitation).where(Invitation.user_id==user.user_id,Invitation.request_id==data.request_id))
            if previous:
                if previous.email!=recipient or previous.full_name!=data.full_name: reject(409,"This request identifier belongs to another invitation.")
                return summary(previous,now)
            try: origin,sender=configuration()
            except (ValueError,TypeError): reject(503,"Real invitations need an enabled sender and a public HTTPS response page. Nothing was sent.")
            db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:key))'),{'key':'enwen-invitation-recipient:'+recipient})
            recipient_count=db.scalar(select(func.count()).select_from(Invitation).where(Invitation.email==recipient,Invitation.created_at>now-timedelta(days=1)))
            if recipient_count>=3:reject(429,'This person has already received several invitations today. Please wait before sending another.')
            latest=db.scalar(select(Invitation).where(Invitation.user_id==user.user_id).order_by(Invitation.created_at.desc()).limit(1))
            if latest and now-latest.created_at<timedelta(minutes=1): reject(429,"Wait at least one minute before another invitation.")
            recent=db.scalar(select(func.count()).select_from(Invitation).where(Invitation.user_id==user.user_id,Invitation.created_at>now-timedelta(days=1)))
            if recent>=5: reject(429,"The five-invitation daily limit has been reached.")
            active=db.scalars(select(Invitation).where(Invitation.user_id==user.user_id,Invitation.revoked_at.is_(None))).all()
            if any(item.decision=="accepted" for item in active): reject(409,"Withdraw the existing accepted enrollment before nominating another person.")
            for item in active: item.revoked_at=now
            token,withdrawal=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
            row=Invitation(user_id=user.user_id,request_id=data.request_id,full_name=data.full_name,email=recipient,
                shared_student_name=" ".join((user.display_name or "An ENWEN student").split())[:100],consent_version=VERSION,consent_text=NOTICE,
                token_hash=digest(token),withdrawal_hash=digest(withdrawal),created_at=now,expires_at=now+timedelta(hours=24),delivery_status="dispatching")
            db.add(row);db.flush(); identifier=row.invitation_id
            body=(row.shared_student_name+" nominated you as a trusted contact in ENWEN.\n\n"+RECIPIENT_NOTICE+
                "\n\nRead and choose Accept or Decline (expires in 24 hours):\n"+origin+"/static/live-contact-response.html#token="+token+
                "\n\nKeep this separate withdrawal link to withdraw later:\n"+origin+"/static/live-contact-response.html#withdraw="+withdrawal+
                "\n\nOpening either page alone does not change your decision. No private student records are shared.")
            if local_demo():body="PRESENTATION DEMONSTRATION ONLY. No real distress or emergency is reported. Open the links on the computer running ENWEN.\n\n"+body
        # Claim commits before transport. Replays never resend an uncertain email.
        reference=None
        try: reference=send_real_invitation(recipient,sender,body)
        except EmailServiceError: pass
        with Session(engine) as db,db.begin():
            row=db.scalar(select(Invitation).where(Invitation.invitation_id==identifier).with_for_update())
            row.delivery_status="provider_accepted" if reference else "uncertain";row.provider_reference=reference
            return summary(row,db.scalar(select(func.clock_timestamp())))
    except SQLAlchemyError: reject(503,"Invitation outcome could not be confirmed. Refresh status before trying again; no automatic retry occurred.")

@router.post("/respond")
def respond(data: Decision,response: Response):
    response.headers["Cache-Control"]="no-store"
    if data.notice_version!=RECIPIENT_VERSION or not data.acknowledged: reject(409,"Read and acknowledge the current recipient notice.")
    token=data.token.get_secret_value()
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}",token): reject(410,"This link is unavailable.")
    field=Invitation.withdrawal_hash if data.decision=="withdraw" else Invitation.token_hash
    try:
        with Session(engine) as db,db.begin():
            # Match sender's account-before-invitation locking order.
            owner=db.scalar(select(Invitation.user_id).where(field==digest(token)))
            if owner is None: reject(410,"This link is unavailable.")
            db.scalar(select(User.user_id).where(User.user_id==owner).with_for_update())
            row=db.scalar(select(Invitation).where(field==digest(token)).with_for_update())
            now=db.scalar(select(func.clock_timestamp()))
            if not row or row.revoked_at: reject(410,"This link is unavailable.")
            if data.decision=="withdraw": row.revoked_at=now
            else:
                if row.decision or row.expires_at<=now: reject(410,"This link is unavailable.")
                current=db.scalar(select(Consent).where(Consent.user_id==owner,Consent.consent_type=="wellness_use").order_by(Consent.recorded_at.desc(),Consent.consent_id.desc()).limit(1))
                if data.decision=="accepted" and (current is None or current.decision!="accepted" or current.notice_version!=CONSENT_VERSION):
                    reject(409,"The student must renew their current consent before this enrollment can be accepted. You may still decline or withdraw.")
                row.decision=data.decision;row.responded_at=now
                row.recipient_notice_version=RECIPIENT_VERSION;row.recipient_notice_text=RECIPIENT_NOTICE
            return {"status":"revoked" if row.revoked_at else row.decision,"automatic_alerts_enabled":False}
    except SQLAlchemyError: reject(503,"Your decision could not be confirmed. Nothing was automatically retried.")

@router.delete("/{invitation_id}",status_code=204)
def revoke(invitation_id: UUID,user: AccountResponse=Depends(get_current_user)):
    try:
        with Session(engine) as db,db.begin():
            db.scalar(select(User.user_id).where(User.user_id==user.user_id).with_for_update())
            row=db.scalar(select(Invitation).where(Invitation.invitation_id==invitation_id,Invitation.user_id==user.user_id).with_for_update())
            if not row: reject(404,"Invitation not found.")
            row.revoked_at=row.revoked_at or db.scalar(select(func.clock_timestamp()))
    except SQLAlchemyError: reject(503,"Withdrawal could not be confirmed. Refresh status.")
    return Response(status_code=204,headers={"Cache-Control":"no-store"})
