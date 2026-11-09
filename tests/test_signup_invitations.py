"""Explicit signup choice, guarded delivery and duplicate protection. TEMP data/fake mail."""
import sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable,CreateIndex
from fastapi.testclient import TestClient
from main import app
from database import engine
from models import Base,User
import registration as reg,signup_invitations as signup,live_contacts as contacts
from signup_invitation_models import SignupInvitationChoice as Choice
from email_service import EmailServiceError

checks=[];messages=[]
def check(label,value):assert value,label;checks.append(label)
def payload(number,invite=True,contact=None):
 return {'email':f'student{number}@university-mail.dev','display_name':'Fictional Student','password':'Synthetic-Only-Password','consent_accepted':True,'consent_version':reg.CONSENT_VERSION,'contact_consent_accepted':True,'contact_consent_version':reg.CONTACT_CONSENT_VERSION,'trusted_contact':{'full_name':'Fictional Person','email':contact or f'person{number}@university-mail.dev'},'invite_contact_by_email':invite,'invitation_notice_version':signup.VERSION if invite else None}
with engine.connect() as connection:
 names=list(Base.metadata.tables);before={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names};connection.rollback();outer=connection.begin()
 try:
  for table in Base.metadata.sorted_tables:
   connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)).replace('CREATE TABLE ','CREATE TEMPORARY TABLE ',1))
   for index in table.indexes:connection.execute(CreateIndex(index))
  connection.execute(text('SET LOCAL search_path=pg_temp,pg_catalog'))
  def session(bind):assert bind is connection;return RealSession(bind=connection,join_transaction_mode='create_savepoint')
  with ExitStack() as stack:
   for module in (reg,signup,contacts):stack.enter_context(patch.object(module,'engine',connection));stack.enter_context(patch.object(module,'Session',session))
   stack.enter_context(patch.object(reg.password_hasher,'hash',return_value='unused-synthetic-hash'))
   stack.enter_context(patch.dict(signup.os.environ,{'SIGNUP_CONTACT_INVITATIONS_ENABLED':'true','CONTACT_DELIVERY_MODE':'production','LIVE_CONTACT_EMAIL_ENABLED':'true'}))
   stack.enter_context(patch.object(contacts,'configuration',return_value=('https://fictional-campus.university-mail.dev','sender@university-mail.dev')))
   transport=stack.enter_context(patch.object(contacts,'send_real_invitation',side_effect=lambda *a,**k:messages.append((a,k)) or 'fake-provider-reference'))
   client=stack.enter_context(TestClient(app))
   check('public signup notice is explicit and non-cached',client.get('/auth/signup-invitation-notice').headers['cache-control']=='no-store')
   no=client.post('/auth/register',json=payload(1,False));check('unchecked choice creates account without email',no.status_code==201 and not messages and no.json()['contact_invitation_status']=='not_requested')
   stale=client.post('/auth/register',json={**payload(2),'invitation_notice_version':'old'});check('stale invitation choice rejected before account creation',stale.status_code==409 and connection.scalar(select(func.count()).select_from(User))==1)
   strict=client.post('/auth/register',json={**payload(2),'invite_contact_by_email':'true'});check('signup email choice must be strict boolean',strict.status_code==422 and not messages)
   with patch.dict(signup.os.environ,{'SIGNUP_CONTACT_INVITATIONS_ENABLED':'false'}):
    off=client.post('/auth/register',json=payload(2));check('deployment switch off saves account and choice but sends nothing',off.status_code==201 and off.json()['contact_invitation_status']=='setup_required' and not messages)
   from uuid import UUID
   with patch.dict(signup.os.environ,{'CONTACT_DELIVERY_MODE':'local_demo'}):
    local=client.post('/auth/register',json=payload(3));check('signup automatic delivery is blocked in laptop mode',local.status_code==201 and local.json()['contact_invitation_status']=='setup_required' and not messages)
   sent=client.post('/auth/register',json=payload(4));check('explicit ready signup submits exactly one invitation',sent.status_code==201 and sent.json()['contact_invitation_status']=='provider_accepted' and len(messages)==1)
   uid=UUID(sent.json()['user_id']);check('choice binds exact notice and nominated recipient',connection.scalar(select(Choice.notice_text).where(Choice.user_id==uid))==signup.permission_snapshot('Fictional Person','person4@university-mail.dev'))
   check('repeat dispatch never sends again',signup.dispatch_once(uid)=='provider_accepted' and len(messages)==1)
   check('duplicate registration never repeats email',client.post('/auth/register',json=payload(4)).status_code==409 and len(messages)==1)
   check('invitation does not contain private health records','Fictional Student' in messages[0][0][2] and 'mood scores' not in messages[0][0][2])
   with patch.object(contacts,'send_real_invitation',side_effect=EmailServiceError('Synthetic failure')):
    uncertain=client.post('/auth/register',json=payload(5));check('mail failure preserves saved account with honest status',uncertain.status_code==201 and uncertain.json()['contact_invitation_status']=='uncertain')
   for number in (6,7,8):check('recipient bounded send '+str(number),client.post('/auth/register',json=payload(number,contact='same-person@university-mail.dev')).json()['contact_invitation_status']=='provider_accepted')
   capped=client.post('/auth/register',json=payload(9,contact='same-person@university-mail.dev'));check('cross-account recipient limit stops a fourth invitation',capped.status_code==201 and capped.json()['contact_invitation_status']=='blocked')
   check('signup choice does not enable safety-email permission',connection.scalar(text('SELECT count(*) FROM live_email_permissions'))==0)
 finally:outer.rollback()
 check('all existing public records unchanged',before=={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names})
print('Passed',len(checks),'guarded signup invitation checks. All email transport fake; public data unchanged.')
for label in checks:print('PASS:',label)
