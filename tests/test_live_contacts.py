"""Real enrollment tests use TEMP tables and fake Brevo; no real mail."""
import sys,re
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from uuid import UUID,uuid4
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
import live_contacts as module
from main import app
from authentication import AccountResponse,get_current_user
from database import engine
from models import Base,User,Consent
from registration import CONSENT_VERSION
from live_contact_models import LiveContactInvitation as Invitation
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable,CreateIndex
from email_service import EmailServiceError

checks=[];mail=[];uid,other=uuid4(),uuid4()
profile=AccountResponse(user_id=uid,email="owner@university-mail.dev",display_name="Fictional Student",wellness_consent_current=True)
def check(name,result): assert result,name;checks.append(name)
def captured(recipient,sender,body):mail.append(body);return "fake-provider-reference"
def body():return {"request_id":str(uuid4()),"full_name":"Fictional Person","email":"contact@university-mail.dev","notice_version":module.VERSION,"acknowledged":True}
with engine.connect() as connection:
    names=list(Base.metadata.tables)
    before={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names};connection.rollback();outer=connection.begin()
    try:
        for table in Base.metadata.sorted_tables:
            connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)).replace('CREATE TABLE ','CREATE TEMPORARY TABLE ',1))
            for index in table.indexes:connection.execute(CreateIndex(index))
        connection.execute(text('SET LOCAL search_path=pg_temp,pg_catalog'))
        def session(bind):assert bind is connection;return RealSession(bind=connection,join_transaction_mode='create_savepoint')
        with ExitStack() as stack:
            stack.enter_context(patch.object(module,'engine',connection));stack.enter_context(patch.object(module,'Session',session))
            transport=stack.enter_context(patch.object(module,'send_real_invitation',side_effect=captured))
            stack.enter_context(patch.dict(module.os.environ,{'CONTACT_DELIVERY_MODE':'production','PUBLIC_APP_URL':'https://wellness-demo.university.ac.ke','LIVE_CONTACT_EMAIL_ENABLED':'true','EMAIL_FROM_ADDRESS':'sender@university-mail.dev','EMAIL_SENDER_VERIFIED':'true','BREVO_API_KEY':'synthetic-only'}))
            app.dependency_overrides[get_current_user]=lambda:profile
            with session(connection) as db:
                db.add_all([User(user_id=x,email=str(x)+'@example.com',display_name='Fictional',password_hash='unused') for x in (uid,other)]);db.flush()
                db.add(Consent(user_id=uid,consent_type='wellness_use',notice_version=CONSENT_VERSION,notice_text='Synthetic',decision='accepted'));db.commit()
            client=stack.enter_context(TestClient(app));base='/trusted-contact/live'
            check('notice ready and non-clinical',client.get(base+'/notice').json()['ready'] and not client.get(base+'/notice').json()['automatic_alerts_enabled'])
            for origin in ('http://127.0.0.1:8000','https://127.0.0.1','https://localhost','https://local.internal','https://user:pass@public.org','https://public.org/path'):
                with patch.dict(module.os.environ,{'PUBLIC_APP_URL':origin}):check('unreachable/unsafe origin blocked '+origin,client.get(base+'/notice').json()['ready'] is False)
            with patch.dict(module.os.environ,{'PUBLIC_APP_URL':''}):check('deployment absence prevents send',client.post(base,json=body()).status_code==503 and not mail)
            payload=body()
            check('fresh acknowledgement required',client.post(base,json={**payload,'acknowledged':False}).status_code==409)
            check('stale notice rejected',client.post(base,json={**payload,'notice_version':'old'}).status_code==409)
            check('own mailbox not a trusted contact',client.post(base,json={**payload,'email':profile.email}).status_code==400)
            response=client.post(base,json=payload);result=response.json();identifier=result['invitation_id']
            check('deliberate invitation accepted once',response.status_code==201 and len(mail)==1 and result['delivery_status']=='provider_accepted')
            check('API never exposes token', 'token' not in response.text and 'withdrawal_hash' not in response.text)
            token=re.search(r'#token=([\w-]{43})',mail[-1])[1];withdraw=re.search(r'#withdraw=([\w-]{43})',mail[-1])[1]
            check('invitation contains shared name without account email','Fictional Student' in mail[-1] and profile.email not in mail[-1])
            check('idempotent replay sends no second email',client.post(base,json=payload).status_code==201 and len(mail)==1)
            check('request cannot change recipient',client.post(base,json={**payload,'email':'different@university-mail.dev'}).status_code==409)
            check('cooldown prevents spam',client.post(base,json=body()).status_code==429)
            decision={'token':token,'decision':'accepted','notice_version':module.RECIPIENT_VERSION,'acknowledged':True}
            check('GET cannot accept invitation',client.get(base+'/respond').status_code==405)
            check('recipient acknowledgement required',client.post(base+'/respond',json={**decision,'acknowledged':False}).status_code==409)
            check('recipient acceptance records separate enrollment',client.post(base+'/respond',json=decision).json()['status']=='accepted')
            check('link is single use',client.post(base+'/respond',json=decision).status_code==410)
            check('acceptance never enables automatic alerts',client.get(base).json()['automatic_alerts_enabled'] is False)
            check('another owner cannot revoke',client.delete(base+'/'+str(uuid4())).status_code==404)
            check('recipient can withdraw after acceptance',client.post(base+'/respond',json={**decision,'token':withdraw,'decision':'withdraw'}).json()['status']=='revoked')
            check('withdrawn token cannot accept again',client.post(base+'/respond',json=decision).status_code==410)
            check('stored token is hashed',connection.scalar(select(Invitation.token_hash))!=token)
            check('local practice contact records unaffected',connection.scalar(text('SELECT count(*) FROM trusted_contacts'))==0)
            check('owner status is no-store',client.get(base).headers.get('cache-control')=='no-store')
            with session(connection) as db:
                row=db.get(Invitation,UUID(identifier));row.created_at-=timedelta(minutes=2);db.commit()
            transport.side_effect=EmailServiceError('synthetic failure');second=body();uncertain=client.post(base,json=second)
            check('uncertain provider result honest',uncertain.status_code==201 and uncertain.json()['delivery_status']=='uncertain')
            calls=transport.call_count;client.post(base,json=second)
            check('uncertain send is not repeated',transport.call_count==calls)
            uncertain_token=re.search(r'#token=([\w-]{43})',transport.call_args.args[2])[1]
            with session(connection) as db:
                expired=db.get(Invitation,UUID(uncertain.json()['invitation_id']));expired.created_at-=timedelta(days=2);expired.expires_at-=timedelta(days=2);db.commit()
            check('expired recipient link cannot accept',client.post(base+'/respond',json={**decision,'token':uncertain_token}).status_code==410)
            app.dependency_overrides[get_current_user]=lambda:AccountResponse(user_id=other,email='other@university-mail.dev',display_name='Other',wellness_consent_current=True)
            check('other account sees no owner enrollment',client.get(base).json() is None)
            check('other account cannot withdraw actual owner record',client.delete(base+'/'+identifier).status_code==404)
            app.dependency_overrides.clear()
            check('anonymous enrollment denied',client.post(base,json=body()).status_code==401)
            check('anonymous owner status denied',client.get(base).status_code==401)
    finally:
        app.dependency_overrides.clear();outer.rollback()
    after={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names}
    check('all public record counts preserved',before==after)
print(f'Passed {len(checks)} real-email enrollment checks. TEMP data and fake transport only; no real emails sent.')
for name in checks:print('PASS:',name)
