"""Public-source lifecycle and atomic AI-index updates; PostgreSQL TEMP data only."""
import sys,json
from pathlib import Path
from uuid import uuid4,UUID
from datetime import timedelta
from contextlib import ExitStack
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from main import app
import resource_admin as admin,resources,knowledge
from resource_admin_models import ResourceCurator as Role,ResourceDraft as Draft,ResourceAudit as Audit
from resource_models import WellnessResource as Resource,ResourceBookmark as Bookmark
from community_models import CommunityModerator
from models import Base,User
from authentication import AccountResponse,get_current_user
from database import engine
from sqlalchemy import select,func,text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable,CreateIndex
from fastapi.testclient import TestClient

curator_id,student,moderator=uuid4(),uuid4(),uuid4();profile=AccountResponse(user_id=student,email='synthetic@example.com',display_name='Synthetic',wellness_consent_current=True);checks=[]
def check(name,ok):assert ok,name;checks.append(name)
def become(uid):
    global profile
    profile=profile.model_copy(update={'user_id':uid})
with engine.connect() as connection:
    names=list(Base.metadata.tables);before={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names};connection.rollback();outer=connection.begin()
    try:
        for table in Base.metadata.sorted_tables:
            connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)).replace('CREATE TABLE ','CREATE TEMPORARY TABLE ',1))
            for index in table.indexes:connection.execute(CreateIndex(index))
        connection.execute(text('SET LOCAL search_path=pg_temp,pg_catalog'))
        def session(bind):assert bind is connection;return RealSession(bind=connection,join_transaction_mode='create_savepoint')
        with ExitStack() as stack:
            for module in (admin,resources,knowledge):stack.enter_context(patch.object(module,'engine',connection));stack.enter_context(patch.object(module,'Session',session))
            app.dependency_overrides[get_current_user]=lambda:profile;client=stack.enter_context(TestClient(app));base='/resource-admin'
            with session(connection) as db:
                db.add_all([User(user_id=u,email=str(u)+'@example.com',display_name='PRIVATE_ACCOUNT_NAME',password_hash='unused') for u in (curator_id,student,moderator)]);db.flush()
                db.add(Role(user_id=curator_id));db.add(CommunityModerator(user_id=moderator));checked=admin.today(db)
                original={'resource_id':'original-source','title':'Synthetic student study guide','publisher':'NHS','category':'studies','summary':'Synthetic coursework reading','url':'https://www.nhs.uk/test-source/','audience_note':'Synthetic UK audience note','source_checked_on':checked}
                db.add(Resource(**original));db.add(knowledge.KnowledgePassage(**{**original,'source_checked_on':checked.isoformat()}));db.flush();db.add(Bookmark(user_id=student,resource_id='original-source'));db.commit()
            def payload(identifier='new-source',**changes):return {'resource_id':identifier,'title':'Synthetic source title','category':'rest','summary':'Synthetic sleep and rest reading','url':'https://www.nhs.uk/test-new-source/','audience_note':'Synthetic UK service information','source_checked_on':checked.isoformat(),'expected_revision':0,'request_id':str(uuid4()),**changes}
            ack={'notice_version':admin.VERSION,'acknowledged':True}
            check('ordinary user is not a resource curator',not client.get(base+'/notice').json()['can_curate'])
            check('ordinary user cannot list curation records',client.get(base+'/resources').status_code==403 and client.get(base+'/history').status_code==403)
            check('ordinary user cannot create source drafts',client.post(base+'/drafts',json=payload()).status_code==403)
            become(moderator);check('community role does not grant source-editing permission',not client.get(base+'/notice').json()['can_curate'] and client.get(base+'/drafts').status_code==403)
            become(curator_id);check('curator can inspect public source versions',client.get(base+'/resources').json()[0]['revision']==1)
            for url in ('http://www.nhs.uk/path','https://evil.example/path','https://127.0.0.1/x','file:///private','https://user:pass@www.nhs.uk/path','https://www.nhs.uk:444/path','https://www.nhs.uk/path#private','https://www.facebook.com/unrelated/','https://www.nhs.uk/path?api_key=SECRET_URL_VALUE'):
                r=client.post(base+'/drafts',json=payload(url=url));check('unsafe source URL rejected '+url.split('?')[0],r.status_code==422 and 'SECRET_URL_VALUE' not in r.text)
            for change in ({'publisher':'Forged publisher'},{'active':True},{'expected_revision':True},{'resource_id':'../private'},{'summary':'\u0000private'},{'source_checked_on':(checked+timedelta(days=1)).isoformat()}):check('invalid draft rejected '+str(list(change)),client.post(base+'/drafts',json=payload(**change)).status_code==422)
            p=payload();r=client.post(base+'/drafts',json=p);draft_id=r.json()['draft_id'];check('draft is deliberately unpublished',r.status_code==201 and r.json()['status']=='draft')
            check('draft does not enter library or AI index',len(client.get('/resources').json())==1 and not any(x['resource_id']=='new-source' for x in knowledge.retrieve('sleep rest')))
            check('publisher is derived from source',r.json()['payload']['publisher']=='NHS')
            check('draft creation replay preserves identity',client.post(base+'/drafts',json=p).json()['draft_id']==draft_id and connection.scalar(select(func.count()).select_from(Draft))==1)
            check('changed draft cannot reuse request identity',client.post(base+'/drafts',json={**p,'title':'Changed'}).status_code==409)
            path=base+'/drafts/'+draft_id+'/publish'
            check('publication requires source review acknowledgement',client.post(path,json={**ack,'acknowledged':False}).status_code==409)
            check('stale publication notice rejected',client.post(path,json={**ack,'notice_version':'old'}).status_code==409)
            r=client.post(path,json=ack);check('reviewed draft publishes first revision',r.status_code==200 and r.json()['recorded_revision']==1)
            check('publication populates student library and index',len(client.get('/resources').json())==2 and any(x['resource_id']=='new-source' for x in knowledge.retrieve('sleep rest')))
            check('published fields agree across both stores',connection.scalar(select(Resource.summary).where(Resource.resource_id=='new-source'))==connection.scalar(select(knowledge.KnowledgePassage.summary).where(knowledge.KnowledgePassage.resource_id=='new-source')))
            check('publication replay adds no audit or revision',client.post(path,json=ack).json()['replayed'] and connection.scalar(select(func.count()).select_from(Audit))==1)
            check('published draft cannot be discarded',client.post(base+'/drafts/'+draft_id+'/discard').status_code==409)
            stale=client.post(base+'/drafts',json=payload('original-source',expected_revision=1,url=original['url'],summary='Synthetic revised coursework')).json()['draft_id']
            second=client.post(base+'/drafts',json=payload('original-source',expected_revision=1,url=original['url'],summary='Another synthetic coursework revision')).json()['draft_id']
            check('curator can update original source',client.post(base+'/drafts/'+stale+'/publish',json=ack).json()['recorded_revision']==2)
            check('stale drafts cannot overwrite newer publication',client.post(base+'/drafts/'+second+'/publish',json=ack).status_code==409)
            check('bookmarks survive publication update',connection.scalar(select(func.count()).select_from(Bookmark))==1)
            retirement={'request_id':str(uuid4()),'expected_revision':2,'reason':'Synthetic outdated source test','notice_version':admin.RETIRE_VERSION,'acknowledged':True}
            rpath=base+'/resources/original-source/retire'
            check('retirement has a distinct notice',client.post(rpath,json={**retirement,'notice_version':admin.VERSION}).status_code==409)
            check('retirement requires deliberate agreement',client.post(rpath,json={**retirement,'acknowledged':False}).status_code==409)
            check('retirement changes both active flags',client.post(rpath,json=retirement).json()['active'] is False and connection.scalar(select(knowledge.KnowledgePassage.active).where(knowledge.KnowledgePassage.resource_id=='original-source')) is False)
            become(student);check('retired source absent from saved library view',client.get('/resources?saved_only=true').json()==[] and connection.scalar(select(func.count()).select_from(Bookmark))==1)
            check('retired source absent from new AI retrieval',not any(x['resource_id']=='original-source' for x in knowledge.retrieve('coursework')))
            check('retired source cannot be newly bookmarked',client.put('/resources/original-source/bookmark').status_code==404)
            become(curator_id);check('retirement replay is idempotent',client.post(rpath,json=retirement).json()['replayed'])
            old=client.post(base+'/drafts',json=payload('original-source',expected_revision=3,url=original['url'],source_checked_on=(checked-timedelta(days=1)).isoformat())).json()['draft_id']
            check('old source check cannot restore publication',client.post(base+'/drafts/'+old+'/publish',json=ack).status_code==409)
            restored=client.post(base+'/drafts',json=payload('original-source',expected_revision=3,url=original['url'],summary='Fresh synthetic coursework summary')).json()['draft_id']
            check('fresh reviewed draft restores resource',client.post(base+'/drafts/'+restored+'/publish',json=ack).json()['recorded_revision']==4)
            check('old retirement replay cannot disable a restored source',client.post(rpath,json=retirement).json()['active'] is True)
            become(student);check('retained bookmark returns after restoration',len(client.get('/resources?saved_only=true').json())==1)
            become(curator_id)
            duplicate=client.post(base+'/drafts',json=payload('duplicate-source',url=original['url'])).json()['draft_id'];check('duplicate source URLs cannot be published',client.post(base+'/drafts/'+duplicate+'/publish',json=ack).status_code==409)
            discarded=client.post(base+'/drafts',json=payload('discard-source',url='https://www.nhs.uk/discard-source/')).json()['draft_id']
            check('unpublished draft can be discarded',client.post(base+'/drafts/'+discarded+'/discard').json()['status']=='discarded')
            check('discarded draft cannot publish',client.post(base+'/drafts/'+discarded+'/publish',json=ack).status_code==409)
            fault=client.post(base+'/drafts',json=payload('original-source',expected_revision=4,url=original['url'],summary='SHOULD_ROLL_BACK')).json()['draft_id']
            real_snapshot=admin.snapshot
            def broken_snapshot(row):
                if row and row.resource_id=='original-source' and row.revision==5:raise SQLAlchemyError('synthetic audit failure')
                return real_snapshot(row)
            with patch.object(admin,'snapshot',side_effect=broken_snapshot):r=client.post(base+'/drafts/'+fault+'/publish',json=ack)
            check('failed audit rolls back entire publication',r.status_code==503 and connection.scalar(select(Resource.revision).where(Resource.resource_id=='original-source'))==4 and connection.scalar(select(knowledge.KnowledgePassage.summary).where(knowledge.KnowledgePassage.resource_id=='original-source'))=='Fresh synthetic coursework summary')
            check('failed draft remains reviewable',connection.scalar(select(Draft.status).where(Draft.draft_id==UUID(fault)))=='draft')
            with session(connection) as db:db.add(knowledge.KnowledgePassage(resource_id='orphan-source',title='Orphan coursework',publisher='Synthetic',category='studies',summary='Orphan coursework private marker',url='https://www.nhs.uk/orphan/',audience_note='Synthetic',source_checked_on=checked.isoformat(),active=True));db.commit()
            check('unpublished orphan passages cannot enter retrieval',not any(x['resource_id']=='orphan-source' for x in knowledge.retrieve('orphan coursework')))
            r=client.get(base+'/history');check('audit history includes public before-after metadata',r.status_code==200 and any(x['before'] and x['after'] for x in r.json()))
            check('history exposes no account identity or private data',all(value not in r.text for value in ('PRIVATE_ACCOUNT_NAME',str(student),str(curator_id),'actor_id','request_id')))
            check('curation history is uncached',r.headers.get('cache-control')=='no-store')
            with session(connection) as db:db.delete(db.get(Role,curator_id));db.commit()
            check('role revocation blocks next curation request',client.get(base+'/resources').status_code==403)
            app.dependency_overrides.clear();check('anonymous curation is denied',client.get(base+'/resources').status_code==401)
    finally:app.dependency_overrides.clear();outer.rollback()
    check('all original public records preserved',before=={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names})
print(f'Passed {len(checks)} resource-curation checks. TEMP records only; no emails, SMS, source fetches or AI generation.')
for name in checks:print('PASS:',name)
