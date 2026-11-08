"""Peer sharing, moderator scope and privacy using PostgreSQL TEMP tables only."""
import sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from uuid import uuid4,UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from main import app
import community as c
from community_models import CommunityModerator as Role,CommunityPost as Post,CommunityFeedback as Feedback,CommunityReport as Report,CommunityReview as Review
from models import Base,User
from journal_models import JournalEntry
from authentication import AccountResponse,get_current_user
from database import engine
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session as RealSession
from sqlalchemy.schema import CreateTable,CreateIndex
from fastapi.testclient import TestClient

author,peer,moderator=uuid4(),uuid4(),uuid4();profile=AccountResponse(user_id=author,email='author@example.com',display_name='Private name',wellness_consent_current=True);checks=[]
def check(name,ok):assert ok,name;checks.append(name)
def become(uid,consent=True):
    global profile
    profile=profile.model_copy(update={'user_id':uid,'email':str(uid)+'@example.com','wellness_consent_current':consent})
def payload(content='Fictional reflection: a study break helped me slow down.',title='A gentler study day'):
    return {'request_id':str(uuid4()),'title':title,'content':content,'notice_version':c.VERSION,'acknowledged':True}
with engine.connect() as connection:
    names=list(Base.metadata.tables);before={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names};connection.rollback();outer=connection.begin()
    try:
        for table in Base.metadata.sorted_tables:
            connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)).replace('CREATE TABLE ','CREATE TEMPORARY TABLE ',1))
            for index in table.indexes:connection.execute(CreateIndex(index))
        connection.execute(text('SET LOCAL search_path=pg_temp,pg_catalog'))
        def session(bind):assert bind is connection;return RealSession(bind=connection,join_transaction_mode='create_savepoint')
        with ExitStack() as stack:
            stack.enter_context(patch.object(c,'engine',connection));stack.enter_context(patch.object(c,'Session',session))
            app.dependency_overrides[get_current_user]=lambda:profile;client=stack.enter_context(TestClient(app))
            with session(connection) as db:
                db.add_all([User(user_id=uid,email=str(uid)+'@example.com',display_name='PRIVATE_ACCOUNT_NAME',password_hash='unused') for uid in (author,peer,moderator)]);db.flush()
                journal=JournalEntry(user_id=author,title='Private only',content='PRIVATE_JOURNAL_NEVER_SHARED');db.add(journal);db.flush();journal_id=journal.journal_id
                db.add(Role(user_id=moderator));db.commit()
            check('sharing notice describes pseudonymity and no contact alert','not completely anonymous' in client.get('/community/notice').json()['text'] and 'no trusted-contact email or SMS' in c.NOTICE)
            check('ordinary account is not a moderator',not client.get('/community/notice').json()['is_moderator'])
            check('empty feed contains no invented community entries',client.get('/community/feed').json()==[])
            check('private journal ID cannot be read as community content',client.get('/community/posts/'+str(journal_id)).status_code==404)
            p=payload()
            for change in ({'acknowledged':False},{'notice_version':'old'}):check('fresh sharing agreement required '+str(change),client.post('/community/posts',json={**p,**change}).status_code==409)
            for change in ({'author_id':str(peer)},{'status':'published'},{'title':'   '},{'content':'\u0000private'},{'content':'x'*2001}):check('invalid or forged submission rejected '+str(list(change)),client.post('/community/posts',json={**p,**change}).status_code==422)
            r=client.post('/community/posts',json=p);post_id=r.json()['id'];check('deliberate submission starts pending',r.status_code==201 and r.json()['status']=='pending')
            check('pending reflection absent from feed',client.get('/community/feed').json()==[] and client.get('/community/posts/'+post_id).status_code==404)
            check('own pending submission visible only in My sharing',client.get('/community/mine').json()['posts'][0]['id']==post_id)
            check('request replay does not duplicate sharing',client.post('/community/posts',json=p).json()['id']==post_id and connection.scalar(select(func.count()).select_from(Post))==1)
            check('changed retry cannot reuse request ID',client.post('/community/posts',json={**p,'content':'Different text'}).status_code==409)
            become(peer);check('other student cannot see pending content',client.get('/community/mine').json()=={'posts':[],'feedback':[]} and client.get('/community/posts/'+post_id).status_code==404)
            check('ordinary account cannot inspect moderation',client.get('/community/moderation/queue').status_code==403)
            decision={'action':'publish','reason':'community_fit','expected_revision':1,'notice_version':c.REVIEW_VERSION,'acknowledged':True}
            check('ordinary account cannot force approval',client.post('/community/moderation/post/'+post_id,json=decision).status_code==403)
            with session(connection) as db:db.add(Role(user_id=author));db.commit()
            become(author);check('moderator cannot approve own sharing',client.post('/community/moderation/post/'+post_id,json=decision).status_code==403)
            with session(connection) as db:db.delete(db.get(Role,author));db.commit()
            become(moderator);queue=client.get('/community/moderation/queue');check('moderator queue excludes identities and private journal',queue.status_code==200 and all(value not in queue.text for value in ('PRIVATE_ACCOUNT_NAME','PRIVATE_JOURNAL_NEVER_SHARED',str(author))))
            check('review checklist acknowledgement required',client.post('/community/moderation/post/'+post_id,json={**decision,'acknowledged':False}).status_code==409)
            check('stale review revision rejected',client.post('/community/moderation/post/'+post_id,json={**decision,'expected_revision':99}).status_code==409)
            check('approval cannot ignore an unsafe review reason',client.post('/community/moderation/post/'+post_id,json={**decision,'reason':'unsafe'}).status_code==422)
            check('review publishes an eligible reflection',client.post('/community/moderation/post/'+post_id,json=decision).json()['status']=='published')
            become(peer);r=client.get('/community/feed');check('published feed hides account identity',len(r.json())==1 and all(value not in r.text for value in ('PRIVATE_ACCOUNT_NAME',str(author),'author_id','request_id','@example.com')))
            check('shared responses are not cached',r.headers.get('cache-control')=='no-store')
            check('published content cannot be silently edited',client.put('/community/posts/'+post_id,json=p).status_code==405)
            response_payload={k:v for k,v in payload(content='Thank you for sharing. Wishing you a gentle evening.').items() if k!='title'}
            r=client.post('/community/posts/'+post_id+'/feedback',json=response_payload);fid=r.json()['id'];check('peer encouragement requires review',r.status_code==201 and r.json()['status']=='pending' and client.get('/community/posts/'+post_id).json()['feedback']==[])
            check('feedback retries are idempotent',client.post('/community/posts/'+post_id+'/feedback',json=response_payload).json()['id']==fid and connection.scalar(select(func.count()).select_from(Feedback))==1)
            check('feedback to unknown reflection rejected',client.post('/community/posts/'+str(uuid4())+'/feedback',json={**response_payload,'request_id':str(uuid4())}).status_code==404)
            become(author);check('self-feedback blocked',client.post('/community/posts/'+post_id+'/feedback',json={**response_payload,'request_id':str(uuid4())}).status_code==400)
            become(moderator);check('reviewed encouragement can publish',client.post('/community/moderation/feedback/'+fid,json=decision).status_code==200)
            become(author);detail=client.get('/community/posts/'+post_id).json();check('approved response is pseudonymous',len(detail['feedback'])==1 and detail['feedback'][0]['author_label']=='A fellow student 🌱' and str(peer) not in str(detail))
            report=client.post('/community/feedback/'+fid+'/report',json={'reason':'unsafe'});check('published feedback can be reported',report.status_code==201)
            client.post('/community/feedback/'+fid+'/report',json={'reason':'unsafe'});check('duplicate reports are not multiplied',connection.scalar(select(func.count()).select_from(Report))==1)
            become(moderator);q=client.get('/community/moderation/queue').json()['items'];item=next(x for x in q if x['id']==fid)
            check('report goes to moderation without reporter identity',item['reports']==['unsafe'] and str(author) not in str(item))
            check('stale decision after report rejected',client.post('/community/moderation/feedback/'+fid,json={**decision,'action':'reject','reason':'unsafe','expected_revision':2}).status_code==409)
            check('moderator can remove reported feedback',client.post('/community/moderation/feedback/'+fid,json={**decision,'action':'reject','reason':'unsafe','expected_revision':item['revision']}).json()['status']=='rejected')
            check('report is resolved with audited decision',connection.scalar(select(func.count()).select_from(Report).where(Report.resolved_at.is_(None)))==0 and connection.scalar(select(func.count()).select_from(Review))==3)
            become(peer);check('removed feedback disappears from shared view',client.get('/community/posts/'+post_id).json()['feedback']==[])
            dangerous=payload('Fictional test only: I want to jump off a building.');flag=client.post('/community/posts',json=dangerous).json()
            check('explicit danger language is held with support flag',flag['status']=='flagged' and flag['support_required'] is True)
            private=client.post('/community/posts',json=payload('Contact me at fictional@example.com')).json();check('contact details are held for privacy review',private['status']=='flagged')
            become(moderator);q=client.get('/community/moderation/queue').json()['items'];check('support-needed item prioritised',q[0]['id']==flag['id'])
            check('support flag cannot be overridden into publication',client.post('/community/moderation/post/'+flag['id'],json=decision).status_code==409)
            check('privacy flag cannot be overridden into publication',client.post('/community/moderation/post/'+private['id'],json=decision).status_code==409)
            check('flagged content can be declined for support',client.post('/community/moderation/post/'+flag['id'],json={**decision,'action':'reject','reason':'needs_support'}).status_code==200)
            become(peer);check('other person cannot withdraw author reflection',client.post('/community/post/'+post_id+'/withdraw').status_code==404)
            become(author,False);check('withdrawn wellness prevents further community reading',client.get('/community/feed').status_code==403)
            check('withdrawal remains available without wellness consent',client.post('/community/post/'+post_id+'/withdraw').json()['status']=='withdrawn' and client.get('/community/mine').status_code==200)
            become(peer);check('withdrawn reflection and its feedback are no longer public',client.get('/community/feed').json()==[] and client.get('/community/posts/'+post_id).status_code==404)
            become(author);check('withdrawn request replay does not republish',client.post('/community/posts',json=p).json()['status']=='withdrawn')
            with session(connection) as db:
                for n in range(9):db.add(Post(author_id=author,request_id=uuid4(),title='Synthetic quota entry',content='Fictional',status='rejected',notice_version=c.VERSION,notice_text=c.NOTICE))
                db.commit()
            check('daily posting quota enforced',client.post('/community/posts',json=payload()).status_code==429)
            check('private journal remains unchanged',connection.scalar(select(JournalEntry.content).where(JournalEntry.journal_id==journal_id))=='PRIVATE_JOURNAL_NEVER_SHARED')
            check('no private journal link exists in shared tables','journal_id' not in Post.__table__.columns)
            check('review audit does not copy submitted text','content' not in Review.__table__.columns)
            become(moderator)
            with session(connection) as db:db.delete(db.get(Role,moderator));db.commit()
            check('revoking moderator role blocks the next request',client.get('/community/moderation/queue').status_code==403)
            app.dependency_overrides.clear();check('anonymous community access denied',client.get('/community/feed').status_code==401 and client.get('/community/moderation/queue').status_code==401)
    finally:app.dependency_overrides.clear();outer.rollback()
    check('all original public records and delivery outboxes preserved',before=={n:connection.scalar(text('SELECT count(*) FROM public.'+n)) for n in names})
print(f'Passed {len(checks)} peer-sharing/moderation checks. TEMP data only; no email, SMS or AI called.')
for name in checks:print('PASS:',name)
