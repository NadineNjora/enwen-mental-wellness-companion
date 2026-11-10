"""Personalisation, database retrieval and live alerts with TEMP data/fake mail."""
import sys,json
from pathlib import Path
from uuid import uuid4
from contextlib import ExitStack
from unittest.mock import patch
from datetime import timedelta
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from main import app
import recommendations as rec,knowledge as kb,live_email_alerts as alerts,live_contacts,safety_alerts,chat_history,ai_chat
from authentication import AccountResponse,get_current_user
from database import engine
from models import Base,User,Consent,MoodEntry
from resource_models import WellnessResource
from live_contact_models import LiveContactInvitation as Enrollment
from registration import CONSENT_VERSION
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable,CreateIndex

checks=[];uid,other=uuid4(),uuid4()
profile=AccountResponse(user_id=uid,email='student@example.com',display_name='Synthetic Student',wellness_consent_current=True)
def check(name,condition):assert condition,name;checks.append(name)
def alert_status(value):return value['alert']['status']
with engine.connect() as connection:
    names=list(Base.metadata.tables);before={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names};connection.rollback();outer=connection.begin()
    try:
        for table in Base.metadata.sorted_tables:
            connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)).replace('CREATE TABLE ','CREATE TEMPORARY TABLE ',1))
            for index in table.indexes:connection.execute(CreateIndex(index))
        connection.execute(text('SET LOCAL search_path=pg_temp,pg_catalog'))
        def session(bind):assert bind is connection;return RealSession(bind=connection,join_transaction_mode='create_savepoint')
        with ExitStack() as stack:
            for module in (rec,kb,alerts,live_contacts,safety_alerts,chat_history):
                stack.enter_context(patch.object(module,'engine',connection));stack.enter_context(patch.object(module,'Session',session))
            transport=stack.enter_context(patch.object(alerts,'send_real_invitation',return_value='synthetic-reference'))
            stack.enter_context(patch.dict(alerts.os.environ,{'CONTACT_DELIVERY_MODE':'production','LIVE_CONTACT_ALERTS_ENABLED':'true','LIVE_CONTACT_EMAIL_ENABLED':'true','PUBLIC_APP_URL':'https://wellness-demo.university.ac.ke','EMAIL_FROM_ADDRESS':'sender@university-mail.dev','EMAIL_SENDER_VERIFIED':'true','BREVO_API_KEY':'synthetic-key','AI_PROVIDER':'ollama'}))
            app.dependency_overrides[get_current_user]=lambda:profile
            client=stack.enter_context(TestClient(app))
            with session(connection) as db:
                db.add_all([User(user_id=x,email=str(x)+'@example.com',display_name='Synthetic',password_hash='unused') for x in (uid,other)]);db.flush()
                db.add(Consent(user_id=uid,consent_type='wellness_use',notice_version=CONSENT_VERSION,notice_text='Synthetic',decision='accepted'))
                for row in kb.json.loads(Path(kb.__file__).with_name('resources_catalog.json').read_text(encoding='utf-8-sig')):
                    db.add(kb.KnowledgePassage(**{k:row[k] for k in kb.FIELDS}))
                    db.add(WellnessResource(**{**row,'source_checked_on':date.fromisoformat(row['source_checked_on'])}))
                db.commit()
            empty=client.get('/wellness/suggestions');check('empty history gives no invented mood',empty.json()['latest_checkin'] is None)
            with session(connection) as db:
                db.add(MoodEntry(user_id=uid,mood_score=2,scale_max=10,note='SYNTHETIC_PRIVATE_NOTE'))
                db.add(MoodEntry(user_id=other,mood_score=10,scale_max=10,note='OTHER_OWNER_NOTE'));db.commit()
            response=client.get('/wellness/suggestions');data=response.json()
            check('recommendations use own latest score',data['latest_checkin']['score']==2 and data['latest_checkin']['scale_max']==10)
            check('lower score offers human/grounding choices',any(x['href']=='#/pause' for x in data['steps']))
            check('notes not exposed or sent to retrieval','SYNTHETIC_PRIVATE_NOTE' not in response.text and 'OTHER_OWNER_NOTE' not in response.text)
            check('private suggestions are no-store',response.headers.get('cache-control')=='no-store')
            with session(connection) as db:
                db.add(MoodEntry(user_id=uid,mood_score=4,scale_max=5,created_at=db.scalar(select(func.clock_timestamp()))+timedelta(seconds=1)));db.commit()
            data=client.get('/wellness/suggestions').json();check('legacy denominator preserved',data['latest_checkin']['score']==4 and data['latest_checkin']['scale_max']==5 and '4/5' in data['basis'])
            check('higher check-in offers reflection/history',any(x['href']=='#/mood-history' for x in data['steps']))
            result=kb.retrieve('masomo exams coursework');check('database retrieval grounds study query',any(row['resource_id']=='nhs-student-stress' for row in result))
            check('retrieval exposes attribution and method',all(row['url'].startswith('https://') and row['retrieval_method'].startswith('BM25') for row in result))
            check('no arbitrary result for unmatched text',kb.retrieve('zzzzzzqqqqxx')==[])
            check('bounded retrieval',len(kb.retrieve('student stress sleep support'))<=3)
            check('personal data not indexed',not any('user_id' in c.name or 'journal' in c.name for c in kb.KnowledgePassage.__table__.columns))
            path='/trusted-contact/live/alert-permission';permission={'accepted':True,'notice_version':alerts.VERSION}
            check('alert permission requires accepted recipient',client.post(path,json=permission).status_code==409)
            with session(connection) as db:
                now=db.scalar(select(func.clock_timestamp()));enrollment=Enrollment(user_id=uid,request_id=uuid4(),full_name='Synthetic Contact',email='trusted@university-mail.dev',shared_student_name='Synthetic Student',consent_version=live_contacts.VERSION,consent_text=live_contacts.NOTICE,token_hash='a'*64,withdrawal_hash='b'*64,delivery_status='provider_accepted',decision='accepted',recipient_notice_version=live_contacts.RECIPIENT_VERSION,recipient_notice_text=live_contacts.RECIPIENT_NOTICE,created_at=now,expires_at=now+timedelta(hours=24));db.add(enrollment);db.flush();eid=enrollment.invitation_id;db.commit()
            check('no live message without student permission',alert_status(alerts.create_live_alert(uid,uuid4()))=='blocked_consent' and transport.call_count==0)
            check('permission version enforced',client.post(path,json={**permission,'notice_version':'old'}).status_code==409)
            check('student can enable current accepted person',client.post(path,json=permission).status_code==200 and client.get(path).json()['accepted'])
            check('fictional demonstrations never email real person',alert_status(alerts.create_live_alert(uid,uuid4(),True))=='blocked_demo' and transport.call_count==0)
            with patch.dict(alerts.os.environ,{'LIVE_CONTACT_ALERTS_ENABLED':'false'}):check('deployment switch blocks live sends',alert_status(alerts.create_live_alert(uid,uuid4()))=='disabled')
            request=uuid4();sent=alerts.create_live_alert(uid,request)
            check('eligible live claim uses email once',alert_status(sent)=='provider_accepted' and transport.call_count==1)
            check('email includes minimal check-in without private note','SYNTHETIC_PRIVATE_NOTE' not in transport.call_args.args[2] and 'Synthetic Student' in transport.call_args.args[2])
            check('provider acceptance is not human response','not confirmed' in sent['alert']['message'])
            check('request replay does not resend',alerts.create_live_alert(uid,request)==sent and transport.call_count==1)
            check('separate eligible event has no artificial waiting period',alert_status(alerts.create_live_alert(uid,uuid4()))=='provider_accepted' and transport.call_count==2)
            check('owner can inspect recorded event',client.get('/safety/alerts/'+sent['event_id']).status_code==200)
            from types import SimpleNamespace
            with session(connection) as db:check('permission cannot transfer to a different enrollment',not alerts.agreed(db,uid,'live_email_alert',alerts.VERSION,SimpleNamespace(invitation_id=uuid4())))
            with patch.object(ai_chat,'generate_reply') as normal:
                flagged=client.post('/chat',json={'messages':[{'role':'user','content':'I want to jump off a building'}],'request_id':str(uuid4()),'external_ai_consent':True,'notice_version':ai_chat.notice_version()})
                check('chat screen dispatches immediately through live permission policy',flagged.status_code==200 and flagged.json()['safety']['alert']['status']=='provider_accepted' and transport.call_count==3 and not normal.called)
                check('chat never claims confirmed real alert delivery',flagged.json()['alerts_sent'] is False)
            check('student can withdraw permission',client.post(path,json={'accepted':False,'notice_version':alerts.VERSION}).status_code==200)
            check('withdrawal prevents further sends',alert_status(alerts.create_live_alert(uid,uuid4()))=='blocked_consent' and transport.call_count==3)
            with session(connection) as db:
                old=db.get(Enrollment,eid);old.revoked_at=db.scalar(select(func.clock_timestamp()));db.commit()
            check('revoked recipient cannot be enabled',client.post(path,json=permission).status_code==409)
            check('withdrawn/revoked permission shown off',not client.get(path).json()['accepted'])
            profile.wellness_consent_current=False;check('withdrawn wellness blocks recommendations',client.get('/wellness/suggestions').status_code==403);profile.wellness_consent_current=True
            app.dependency_overrides[get_current_user]=lambda:AccountResponse(user_id=other,email='other@example.com',display_name='Other',wellness_consent_current=True)
            check('other owner cannot see alert event',client.get('/safety/alerts/'+sent['event_id']).status_code==404)
            check('other owner gets own recommendation',client.get('/wellness/suggestions').json()['latest_checkin']['score']==10)
            app.dependency_overrides.clear();check('anonymous suggestions denied',client.get('/wellness/suggestions').status_code==401);check('anonymous alert permission denied',client.post(path,json=permission).status_code==401)
    finally:app.dependency_overrides.clear();outer.rollback()
    check('all original public records preserved',before=={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names})
print(f'Passed {len(checks)} functional checks. Temporary data and fake email only; no real contact notified.')
for name in checks:print('PASS:',name)
