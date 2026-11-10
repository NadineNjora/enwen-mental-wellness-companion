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
 'provider_accepted':'A check-in email has been submitted for your trusted person. Please reach out directly too; delivery and a response are not confirmed.',
 'uncertain':'Email acceptance is not confirmed. No automatic retry occurred; contact someone directly instead of waiting.'}
def result(row):
    status='uncertain' if row.status=='dispatching' else row.status
    message=MESSAGES[status]
    if status=='blocked_cooldown' and local_demo():
        message='The authorised one-email presentation test has already been used. No new email was sent. Wider sending requires public deployment and a separate delivery setup.'
    return {'event_id':str(row.event_id),'alert':{'status':status,'message':message,'requested_at':row.created_at.isoformat()}}

def recent_alert(db,user_id,current_time):
    return db.scalar(select(LiveEmailAlert.event_id).where(LiveEmailAlert.user_id==user_id,
        LiveEmailAlert.status.in_(('dispatching','provider_accepted','uncertain')),
        *(() if local_demo() else (LiveEmailAlert.created_at>current_time-timedelta(minutes=10),))).limit(1))

def delivery_state(db,user,enrollment,accepted):
    """Describe the same gates used by dispatch; permission alone is not readiness."""
    if local_demo():
        try: eligible=user.email.lower()==os.getenv('LOCAL_DEMO_USER_EMAIL','').strip().lower() and (not enrollment or enrollment.email.lower()==demo_recipient()) and os.getenv('LOCAL_DEMO_NOTIFICATIONS','false').lower()=='true'
        except ValueError: eligible=False
        if not eligible:return False,'This computer can send only the approved demonstration account’s email to its verified mailbox.'
    try:configuration()
    except (ValueError,TypeError):return False,'Email sending is not configured for this installation.'
    if os.getenv('LIVE_CONTACT_ALERTS_ENABLED','false').lower()!='true':return False,'Check-in email sending is not enabled on this installation.'
    if not enrollment:return False,'Your trusted person needs to accept their email invitation first.'
    if not accepted or not user.wellness_consent_current:return False,'Check-in email permission is needed before sending.'
    if recent_alert(db,user.user_id,db.scalar(select(func.clock_timestamp()))):
        return False,('The one-email presentation test has already been used. No further check-in emails will be sent in this mode.' if local_demo() else 'A check-in email was recently requested. New alerts are paused for ten minutes to avoid duplicates.')
    return True,('Ready for the approved one-email presentation test to your verified mailbox.' if local_demo() else 'Ready to request a check-in from your accepted trusted person.')
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
        accepted=agreed(db,user.user_id,'live_email_alert',VERSION,recipient)
        available,reason=delivery_state(db,user,recipient,accepted)
        last=db.scalar(select(LiveEmailAlert).where(LiveEmailAlert.user_id==user.user_id).order_by(LiveEmailAlert.created_at.desc(),LiveEmailAlert.event_id.desc()).limit(1))
        return {'notice_version':VERSION,'text':NOTICE,'short_text':'I allow ENWEN to ask my accepted trusted person to check in when chat messages suggest danger. It shares my name, not my private words or scores. Signals may be wrong or missed. I can turn this off; my person can withdraw. Email and a response are not guaranteed.','accepted':accepted,'delivery_enabled':os.getenv('LIVE_CONTACT_ALERTS_ENABLED','false').lower()=='true',
            'sending_available':available,'sending_reason':reason,'delivery_mode':'local_demo' if local_demo() else 'production',
            'last_alert':{'status':result(last)['alert']['status'],'message':result(last)['alert']['message'],'created_at':last.created_at} if last else None}
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
            elif recent_alert(db,user_id,now):status='blocked_cooldown'
            else:
                try:_,sender=configuration()
                except (ValueError,TypeError):status='disabled'
                else:
                    status='dispatching';recipient=enrollment.email
                    body=("We’re reaching out on behalf of "+enrollment.shared_student_name+". They may be having a difficult moment and could use a familiar, caring voice. "
                          "As their trusted person, please call or message them when you can, listen without judgement, and ask what support would help. "
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
    try:reference=send_real_invitation(recipient,sender,body,subject='ENWEN DEMO: automatic check-in test' if local_demo() else 'Your trusted person needs you — ENWEN')
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
