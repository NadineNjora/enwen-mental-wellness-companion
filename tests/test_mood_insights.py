"""Student factors and Nairobi calendar summaries; TEMP data, no email or AI."""
import sys,json
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from uuid import UUID,uuid4
from datetime import datetime,time,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from main import app
import moods,mood_insights as insights
from mood_context_models import MoodContext,CONTEXTS
from models import Base,User,MoodEntry
from database import engine
from authentication import AccountResponse,get_current_user
from sqlalchemy import text,select,func
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable,CreateIndex
from fastapi.testclient import TestClient

checks=[];uid,other=uuid4(),uuid4();profile=AccountResponse(user_id=uid,email='synthetic@example.com',display_name='Synthetic Student',wellness_consent_current=True)
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
            for module in (moods,insights):stack.enter_context(patch.object(module,'engine',connection));stack.enter_context(patch.object(module,'Session',session))
            app.dependency_overrides[get_current_user]=lambda:profile
            client=stack.enter_context(TestClient(app))
            with session(connection) as db:
                db.add_all([User(user_id=x,email=str(x)+'@example.com',password_hash='unused') for x in (uid,other)]);db.commit()
            empty=client.get('/moods/insights?days=7');check('empty window has no invented values',empty.status_code==200 and empty.json()['total_checkins']==0 and empty.json()['scale_summaries']==[])
            check('catalog contains student and weather contexts',set(x['key'] for x in client.get('/moods/context-options').json()['options'])==set(CONTEXTS))
            payload={'mood_score':7,'scale_max':10,'note':'PRIVATE_NOTE_DO_NOT_ANALYSE','contexts':['exams','finances']}
            response=client.post('/moods',json=payload);check('structured context saves with check-in',response.status_code==201 and set(response.json()['contexts'])=={'exams','finances'})
            identifier=UUID(response.json()['mood_id'])
            check('check-in and factors share a transaction',connection.scalar(select(func.count()).select_from(MoodContext).where(MoodContext.mood_id==identifier))==2)
            for value in (['exams','exams'],['invented'],list(CONTEXTS)[:7],[True]):check('invalid factors rejected '+str(value),client.post('/moods',json={**payload,'contexts':value}).status_code==422)
            check('invalid submissions do not create check-ins',len(client.get('/moods').json())==1)
            with session(connection) as db:
                now=db.scalar(select(func.clock_timestamp()));today=now.astimezone(insights.EAT).date()
                daytime=datetime.combine(today-timedelta(days=2),time(10,30),tzinfo=insights.EAT)
                first=MoodEntry(user_id=uid,mood_score=9,scale_max=10,created_at=daytime)
                db.add(first);db.flush();db.add(MoodContext(mood_id=first.mood_id,context_key='exams'))
                db.add_all([MoodEntry(user_id=uid,mood_score=4,scale_max=5,note='LEGACY_PRIVATE',created_at=datetime.combine(today-timedelta(days=1),time(22),tzinfo=insights.EAT)),MoodEntry(user_id=uid,mood_score=1,scale_max=10,created_at=now-timedelta(days=100)),MoodEntry(user_id=uid,mood_score=1,scale_max=10,created_at=now+timedelta(days=1)),MoodEntry(user_id=other,mood_score=1,scale_max=10,note='OTHER_OWNER_NOTE')]);db.commit()
            response=client.get('/moods/insights?days=7');data=response.json()
            check('seven-day query accepted',response.status_code==200 and data['period_days']==7)
            check('old future and other-owner rows excluded',data['total_checkins']==3)
            check('Nairobi calendar days counted',data['days_with_checkins']==3 and data['timezone'].startswith('Africa/Nairobi'))
            scales={x['scale_max']:x for x in data['scale_summaries']}
            check('legacy and current averages stay separate',scales[10]['average_score']==8 and scales[5]['average_score']==4 and scales[5]['count']==1)
            check('combined average normalises each score before averaging',data['normalised_summary']=={'scale_max':10,'count':3,'average_score':8.0})
            check('only explicitly selected factors counted',{x['key']:x['count'] for x in data['contexts']}=={'exams':2,'finances':1} and data['unlabelled_checkins']==1)
            check('notes and other owner details excluded',all(value not in response.text for value in ('PRIVATE_NOTE_DO_NOT_ANALYSE','LEGACY_PRIVATE','OTHER_OWNER_NOTE',str(other))))
            check('morning and evening use Nairobi time',next(x['count'] for x in data['times'] if x['key']=='morning')>=1 and next(x['count'] for x in data['times'] if x['key']=='evening')>=1)
            check('daily and weekday counts are consistent',len(data['daily'])==7 and sum(x['count'] for x in data['daily'])==3 and sum(x['count'] for x in data['weekdays'])==3)
            check('summary is private and uncached',response.headers.get('cache-control')=='no-store')
            check('factors restored on list',next(x for x in client.get('/moods').json() if x['mood_id']==str(identifier))['contexts']==['exams','finances'])
            for days in (30,90):check(str(days)+' day period accepted',client.get('/moods/insights?days='+str(days)).status_code==200)
            for days in ('8','0','999','abc'):check('unsupported period rejected '+days,client.get('/moods/insights?days='+days).status_code==422)
            profile=profile.model_copy(update={'user_id':other});own=client.get('/moods/insights?days=7').json()
            check('other student gets only own summary',own['total_checkins']==1 and own['contexts']==[])
            profile=profile.model_copy(update={'wellness_consent_current':False})
            check('withdrawn wellness blocks factors and summaries',client.get('/moods/insights').status_code==403 and client.get('/moods/context-options').status_code==403)
            app.dependency_overrides.clear();check('anonymous summary denied',client.get('/moods/insights').status_code==401)
    finally:app.dependency_overrides.clear();outer.rollback()
    check('all original public records preserved',before=={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names})
print(f'Passed {len(checks)} student-context and mood-insight checks; temporary data only.')
for name in checks:print('PASS:',name)
