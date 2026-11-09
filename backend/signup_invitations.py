"""An explicitly requested, single signup invitation; no background resending."""
import os,json
from uuid import NAMESPACE_URL,uuid5
from fastapi import APIRouter,Response,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import engine
from models import User,Consent
from trusted_contact_models import TrustedContact
from signup_invitation_models import SignupInvitationChoice as Choice

VERSION='signup-invite-1'
NOTICE=('I have this person’s permission to share their name and email. After my account is saved, I ask ENWEN to try sending one invitation with my display name and secure response links. '
        'My private entries are not shared. They can decline or withdraw. Check-in emails need a separate choice from me after they accept. If sending is unavailable, I can invite them from Trusted contact.')
router=APIRouter(prefix='/auth',tags=['Registration invitation choice'])

def enabled():
    return os.getenv('SIGNUP_CONTACT_INVITATIONS_ENABLED','false').lower()=='true'

def ready():
    from live_contacts import local_demo,configuration
    if not enabled() or local_demo():return False
    try:configuration();return True
    except (ValueError,TypeError):return False

@router.get('/signup-invitation-notice')
def notice(response:Response):
    response.headers['Cache-Control']='no-store'
    return {'notice_version':VERSION,'text':NOTICE,'ready':ready()}

def permission_snapshot(full_name,email):
    return NOTICE+'\nRecipient: '+json.dumps({'full_name':full_name,'email':str(email).lower()},sort_keys=True,ensure_ascii=False)

def choice_for(user_id,contact):
    return Choice(user_id=user_id,request_id=uuid5(NAMESPACE_URL,'enwen:signup-invitation:'+str(user_id)),notice_version=VERSION,notice_text=permission_snapshot(contact.full_name,contact.email))

def dispatch_once(user_id):
    from authentication import AccountResponse
    from registration import CONSENT_VERSION
    from live_contacts import invite,Enroll,VERSION as INVITE_VERSION
    with Session(engine) as db,db.begin():
        row=db.scalar(select(Choice).where(Choice.user_id==user_id).with_for_update())
        if row is None:return 'not_requested'
        if row.status!='requested':return 'uncertain' if row.status=='dispatching' else row.status
        if not ready():row.status='setup_required';return row.status
        user=db.get(User,user_id);contact=db.scalar(select(TrustedContact).where(TrustedContact.user_id==user_id))
        consent=db.scalar(select(Consent).where(Consent.user_id==user_id,Consent.consent_type=='wellness_use').order_by(Consent.recorded_at.desc(),Consent.consent_id.desc()).limit(1))
        if not user or not contact or not consent or consent.decision!='accepted' or consent.notice_version!=CONSENT_VERSION or row.notice_version!=VERSION or row.notice_text!=permission_snapshot(contact.full_name,contact.email):
            row.status='blocked';return row.status
        actor=AccountResponse(user_id=user.user_id,email=user.email,display_name=user.display_name,wellness_consent_current=True)
        data=Enroll(request_id=row.request_id,full_name=contact.full_name,email=contact.email,notice_version=INVITE_VERSION,acknowledged=True)
        row.status='dispatching'
    try:outcome=invite(data,Response(),actor)['delivery_status']
    except HTTPException as error:outcome='blocked' if error.status_code<500 else 'uncertain'
    except Exception:outcome='uncertain'
    with Session(engine) as db,db.begin():
        row=db.scalar(select(Choice).where(Choice.user_id==user_id).with_for_update())
        row.status=outcome
    return outcome
