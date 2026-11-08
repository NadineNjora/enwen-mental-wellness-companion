"""Minimal real-email check-ins, only with both parties' current permission."""
import os
from datetime import datetime,timedelta
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Response
from pydantic import BaseModel,ConfigDict,StrictBool,Field
from sqlalchemy import DateTime,ForeignKey,String,Text,UniqueConstraint,select,func
from sqlalchemy.orm import Mapped,mapped_column,Session
from models import Base,User,Consent
from database import engine
from authentication import AccountResponse,get_current_user
from registration import CONSENT_VERSION
from live_contact_models import LiveContactInvitation as Invitation
from live_contacts import RECIPIENT_VERSION,configuration,send_real_invitation,reject,local_demo,demo_recipient
from email_service import EmailServiceError

VERSION='live-email-alert-1'
NOTICE=("I choose to enable automated wellbeing check-in emails to my accepted, verified-by-link trusted contact. "
        "ENWEN may send one when its prototype chat safety screen flags explicit danger language. "
        "Signals may be wrong or missed. The email shares my display name and a request to check in, not my messages, journals or mood scores. "
        "Delivery and human response are not guaranteed. I can switch permission off; my contact can withdraw. This does not enable SMS or emergency dispatch.")
router=APIRouter(prefix='/trusted-contact/live/alert-permission',tags=['Live email alert permission'])
class Permission(BaseModel):
    model_config=ConfigDict(extra='forbid')
    accepted:StrictBool
    notice_version:str=Field(max_length=40)
class LiveEmailPermission(Base):
    __tablename__='live_email_permissions'
    permission_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    user_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),index=True)
    invitation_id:Mapped[UUID|None]=mapped_column(ForeignKey('live_contact_invitations.invitation_id'))
    notice_version:Mapped[str]=mapped_column(String(40))
    notice_text:Mapped[str]=mapped_column(Text)
    decision:Mapped[str]=mapped_column(String(20))
    recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
class LiveEmailAlert(Base):
    __tablename__='live_email_alerts'
    __table_args__=(UniqueConstraint('user_id','request_id',name='uq_live_email_alert_request'),)
    event_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    user_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),index=True)
    request_id:Mapped[UUID]=mapped_column()
    invitation_id:Mapped[UUID|None]=mapped_column(ForeignKey('live_contact_invitations.invitation_id'))
    status:Mapped[str]=mapped_column(String(32))
    provider_reference:Mapped[str|None]=mapped_column(String(512))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
MESSAGES={'disabled':'Live check-in emails are disabled. No real notification was sent.',
 'blocked_demo':'This is marked as a fictional demonstration. No real person was notified.',
 'blocked_consent':'Current live-email permission is missing or withdrawn. No real notification was sent.',
 'blocked_unconfirmed':'No currently accepted real contact agreement is available. No real notification was sent.',
 'blocked_cooldown':'A recent check-in request is already recorded. No duplicate email was sent.',
 'provider_accepted':'Brevo accepted a minimal check-in email. Inbox delivery and a human response are not confirmed.',
 'uncertain':'Email acceptance is not confirmed. No automatic retry occurred; contact someone directly instead of waiting.'}
def result(row):
    status='uncertain' if row.status=='dispatching' else row.status
    return {'event_id':str(row.event_id),'alert':{'status':status,'message':MESSAGES[status]}}
def latest(db,user_id,kind):
    if kind=='live_email_alert':return db.scalar(select(LiveEmailPermission).where(LiveEmailPermission.user_id==user_id).order_by(LiveEmailPermission.recorded_at.desc(),LiveEmailPermission.permission_id.desc()).limit(1))
    return db.scalar(select(Consent).where(Consent.user_id==user_id,Consent.consent_type==kind).order_by(Consent.recorded_at.desc(),Consent.consent_id.desc()).limit(1))
def agreed(db,user_id,kind,version,enrollment=None):
    row=latest(db,user_id,kind)
    valid=bool(row and row.decision=='accepted' and row.notice_version==version)
    if kind=='live_email_alert':valid=valid and enrollment is not None and row.notice_text.endswith('\nEnrollment: '+str(enrollment.invitation_id))
    return valid
@router.get('')
def read_permission(response:Response,user:AccountResponse=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:
        recipient=db.scalar(select(Invitation).where(Invitation.user_id==user.user_id,Invitation.decision=='accepted',Invitation.revoked_at.is_(None),Invitation.recipient_notice_version==RECIPIENT_VERSION).order_by(Invitation.created_at.desc()).limit(1))
        return {'notice_version':VERSION,'text':NOTICE,'accepted':agreed(db,user.user_id,'live_email_alert',VERSION,recipient),'delivery_enabled':os.getenv('LIVE_CONTACT_ALERTS_ENABLED','false').lower()=='true'}
@router.post('')
def permission(data:Permission,response:Response,user:AccountResponse=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    if data.notice_version!=VERSION:reject(409,'Read the current live-email alert notice.')
    with Session(engine) as db,db.begin():
        if db.scalar(select(User.user_id).where(User.user_id==user.user_id).with_for_update()) is None:reject(401,'Please log in again.')
        recipient=db.scalar(select(Invitation).where(Invitation.user_id==user.user_id,Invitation.decision=='accepted',Invitation.revoked_at.is_(None),Invitation.recipient_notice_version==RECIPIENT_VERSION).limit(1))
        if data.accepted and (not user.wellness_consent_current or not recipient):reject(409,'An accepted real contact agreement and current wellness consent are required first.')
        db.add(LiveEmailPermission(user_id=user.user_id,invitation_id=recipient.invitation_id if data.accepted else None,notice_version=VERSION,notice_text=NOTICE+('\nEnrollment: '+str(recipient.invitation_id) if data.accepted else ''),decision='accepted' if data.accepted else 'withdrawn',recorded_at=db.scalar(select(func.clock_timestamp()))))
    return {'accepted':data.accepted,'automatic_sms_enabled':False}
def create_live_alert(user_id,request_id,demonstration=False):
    user_id,request_id=UUID(str(user_id)),UUID(str(request_id));recipient=None;sender=None;body=None
    with Session(engine) as db,db.begin():
        if db.scalar(select(User.user_id).where(User.user_id==user_id).with_for_update()) is None:reject(401,'Please log in again.')
        old=db.scalar(select(LiveEmailAlert).where(LiveEmailAlert.user_id==user_id,LiveEmailAlert.request_id==request_id))
        if old:return result(old)
        now=db.scalar(select(func.clock_timestamp()))
        enrollment=db.scalar(select(Invitation).where(Invitation.user_id==user_id,Invitation.decision=='accepted',Invitation.revoked_at.is_(None),Invitation.recipient_notice_version==RECIPIENT_VERSION).order_by(Invitation.created_at.desc()).limit(1))
        status='disabled'
        demo_allowed=False
        if local_demo():
            account=db.get(User,user_id)
            try:demo_allowed=bool(enrollment and enrollment.email.lower()==demo_recipient() and account and account.email.lower()==os.getenv('LOCAL_DEMO_USER_EMAIL','').strip().lower() and os.getenv('LOCAL_DEMO_NOTIFICATIONS','false').lower()=='true')
            except ValueError:pass
        if local_demo() and not demo_allowed:status='blocked_demo'
        elif demonstration and not demo_allowed:status='blocked_demo'
        elif os.getenv('LIVE_CONTACT_ALERTS_ENABLED','false').lower()=='true':
            if not agreed(db,user_id,'wellness_use',CONSENT_VERSION) or not agreed(db,user_id,'live_email_alert',VERSION,enrollment):status='blocked_consent'
            elif not enrollment:status='blocked_unconfirmed'
            elif db.scalar(select(LiveEmailAlert.event_id).where(LiveEmailAlert.user_id==user_id,LiveEmailAlert.status.in_(('dispatching','provider_accepted','uncertain')),*(() if local_demo() else (LiveEmailAlert.created_at>now-timedelta(minutes=10),))).limit(1)):status='blocked_cooldown'
            else:
                try:_,sender=configuration()
                except (ValueError,TypeError):status='disabled'
                else:
                    status='dispatching';recipient=enrollment.email
                    body=("ENWEN recorded an automated request for a human check-in for "+enrollment.shared_student_name+". "
                          "You agreed to receive these messages as their trusted contact. Please check in directly if you can. "
                          "This signal can be wrong and is not a clinical assessment or emergency dispatch. No private conversation, journal or mood text is included. "
                          "To withdraw, use the separate withdrawal link in your original ENWEN invitation email.")
                    if local_demo():body=("PRESENTATION DEMONSTRATION ONLY — NO REAL EMERGENCY. "
                        "This is the authorised ENWEN automatic check-in email test for Demo Student. "
                        "No real distress is reported and no emergency response is requested. The chat interruption and contact-notification path have been exercised. "
                        "No private journal, mood or chat content is included. Use the withdrawal link in your invitation if you want to withdraw.")
        row=LiveEmailAlert(user_id=user_id,request_id=request_id,invitation_id=enrollment.invitation_id if enrollment else None,status=status,created_at=now)
        db.add(row);db.flush();identifier=row.event_id
        if recipient is None:return result(row)
    reference=None
    try:reference=send_real_invitation(recipient,sender,body,subject='ENWEN DEMO: automatic check-in test' if local_demo() else 'ENWEN: a request to check in')
    except EmailServiceError:pass
    with Session(engine) as db,db.begin():
        row=db.scalar(select(LiveEmailAlert).where(LiveEmailAlert.event_id==identifier).with_for_update())
        row.status='provider_accepted' if reference else 'uncertain';row.provider_reference=reference;row.completed_at=db.scalar(select(func.clock_timestamp()))
        return result(row)
def own_event(user_id,event_id):
    with Session(engine) as db:
        row=db.scalar(select(LiveEmailAlert).where(LiveEmailAlert.user_id==UUID(str(user_id)),LiveEmailAlert.event_id==UUID(str(event_id))))
        if row is None:reject(404,'Support notification was not found.')
        return result(row)
