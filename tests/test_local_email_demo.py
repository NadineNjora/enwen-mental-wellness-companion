"""Laptop presentation delivery: TEMP records, fake transport, no real messages."""
import sys,re
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from datetime import timedelta
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from main import app
import live_contacts as contacts,live_email_alerts as alerts,ai_chat,chat_history,safety_alerts
from authentication import AccountResponse,get_current_user
from database import engine
from models import Base,User,Consent
from registration import CONSENT_VERSION
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable,CreateIndex
from fastapi.testclient import TestClient

checks=[];uid=uuid4();profile=AccountResponse(user_id=uid,email='student@example.com',display_name='Demo Student',wellness_consent_current=True)
def check(name,ok):assert ok,name;checks.append(name)
with engine.connect() as connection:
    names=list(Base.metadata.tables);before={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names};connection.rollback();outer=connection.begin()
    try:
        for table in Base.metadata.sorted_tables:
            connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)).replace('CREATE TABLE ','CREATE TEMPORARY TABLE ',1))
            for index in table.indexes:connection.execute(CreateIndex(index))
        connection.execute(text('SET LOCAL search_path=pg_temp,pg_catalog'))
        def session(bind):assert bind is connection;return RealSession(bind=connection,join_transaction_mode='create_savepoint')
        with ExitStack() as stack:
            for module in (contacts,alerts,chat_history,safety_alerts):
                stack.enter_context(patch.object(module,'engine',connection));stack.enter_context(patch.object(module,'Session',session))
            stack.enter_context(patch.dict(contacts.os.environ,{'CONTACT_DELIVERY_MODE':'local_demo','LOCAL_DEMO_USER_EMAIL':profile.email,'LOCAL_DEMO_RECIPIENT':'sender@university-mail.dev','LOCAL_DEMO_NOTIFICATIONS':'true','EMAIL_FROM_ADDRESS':'sender@university-mail.dev','EMAIL_SENDER_VERIFIED':'true','LIVE_CONTACT_EMAIL_ENABLED':'true','LIVE_CONTACT_ALERTS_ENABLED':'true','BREVO_API_KEY':'synthetic','AI_PROVIDER':'ollama','PUBLIC_APP_URL':''}))
            invitation_mail=stack.enter_context(patch.object(contacts,'send_real_invitation',return_value='synthetic-invitation'))
            alert_mail=stack.enter_context(patch.object(alerts,'send_real_invitation',return_value='synthetic-alert'))
            app.dependency_overrides[get_current_user]=lambda:profile
            client=stack.enter_context(TestClient(app));base='/trusted-contact/live'
            with session(connection) as db:
                db.add(User(user_id=uid,email=profile.email,display_name='Demo Student',password_hash='unused'));db.flush()
                db.add(Consent(user_id=uid,consent_type='wellness_use',notice_version=CONSENT_VERSION,notice_text='Synthetic',decision='accepted'));db.commit()
            check('local mode declares laptop-only demonstration', 'not public deployment' in client.get(base+'/notice').json()['reason'])
            with patch.dict(contacts.os.environ,{'CONTACT_DELIVERY_MODE':'production'}):check('production still rejects missing public HTTPS',not client.get(base+'/notice').json()['ready'])
            with patch.dict(contacts.os.environ,{'LOCAL_DEMO_RECIPIENT':'different@university-mail.dev'}):check('demo recipient must equal verified mailbox',not client.get(base+'/notice').json()['ready'])
            payload={'request_id':str(uuid4()),'full_name':'Presentation mailbox','email':'sender@university-mail.dev','notice_version':contacts.VERSION,'acknowledged':True}
            check('other recipient blocked',client.post(base,json={**payload,'email':'other@university-mail.dev'}).status_code==403 and not invitation_mail.called)
            with patch.dict(contacts.os.environ,{'LOCAL_DEMO_USER_EMAIL':'other@example.com'}):check('other student blocked',client.post(base,json=payload).status_code==403 and not invitation_mail.called)
            sent=client.post(base,json=payload);check('configured invitation accepted once',sent.status_code==201 and invitation_mail.call_count==1)
            body=invitation_mail.call_args.args[2];token=re.search(r'#token=([\w-]{43})',body)[1]
            check('invitation explicitly synthetic and loopback','NO REAL' in body.upper() and 'http://127.0.0.1:8000/static/live-contact-response.html' in body)
            check('acceptance not silently recorded',client.get(base).json()['status']=='pending')
            check('no alert without recipient acceptance',alerts.create_live_alert(uid,uuid4(),True)['alert']['status']=='blocked_demo' and not alert_mail.called)
            decision={'token':token,'decision':'accepted','notice_version':contacts.RECIPIENT_VERSION,'acknowledged':True}
            check('explicit recipient acceptance works',client.post(base+'/respond',json=decision).status_code==200)
            check('student permission remains required',alerts.create_live_alert(uid,uuid4(),True)['alert']['status']=='blocked_consent' and not alert_mail.called)
            check('student permission can be recorded',client.post(base+'/alert-permission',json={'accepted':True,'notice_version':alerts.VERSION}).status_code==200)
            with patch.dict(contacts.os.environ,{'LOCAL_DEMO_NOTIFICATIONS':'false'}):check('demo authorisation switch enforced',alerts.create_live_alert(uid,uuid4(),True)['alert']['status']=='blocked_demo' and not alert_mail.called)
            with patch.object(ai_chat,'generate_reply') as normal:
                request_id=str(uuid4());response=client.post('/chat',json={'messages':[{'role':'user','content':'Fictional demonstration: I want to jump off a building'}],'request_id':request_id,'external_ai_consent':True,'notice_version':ai_chat.notice_version()})
                check('chat interrupts generation and sends one demo',response.status_code==200 and response.json()['safety']['alert']['status']=='provider_accepted' and not normal.called and alert_mail.call_count==1)
            args=alert_mail.call_args
            check('demo transport only targets verified mailbox',args.args[0]=='sender@university-mail.dev')
            check('synthetic subject and no private words',args.kwargs['subject']=='ENWEN DEMO: automatic check-in test' and 'NO REAL EMERGENCY' in args.args[2] and 'jump' not in args.args[2])
            with session(connection) as db:
                row=db.scalar(select(alerts.LiveEmailAlert).where(alerts.LiveEmailAlert.status=='provider_accepted'));row.created_at-=timedelta(days=1);db.commit()
            check('one demo allowance persists beyond cooldown',alerts.create_live_alert(uid,uuid4(),True)['alert']['status']=='blocked_cooldown' and alert_mail.call_count==1)
    finally:app.dependency_overrides.clear();outer.rollback()
    check('existing public records preserved',before=={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names})
print(f'Passed {len(checks)} local email demonstration checks; fake transport only.')
for name in checks:print('PASS:',name)
