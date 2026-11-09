"""Pseudonymous peer reflections with review-before-publication and owner withdrawal."""
import re
from datetime import timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import BaseModel,ConfigDict,Field,StrictBool,field_validator
from sqlalchemy import select,func,update
from sqlalchemy.orm import Session
from authentication import AccountResponse,get_current_user
from database import engine
from models import User
from community_models import CommunityModerator as Moderator,CommunityPost as Post,CommunityFeedback as Feedback,CommunityReport as Report,CommunityReview as Review
from safety_screen import support_signal

router=APIRouter(prefix='/community',tags=['Peer reflections'])
VERSION='community-sharing-2'
NOTICE=('I choose to share this reflection or response with signed-in students after moderation. My name and email stay hidden from peers; ENWEN keeps ownership and review records. '
 'I will leave out identifying details. I can withdraw my sharing; review records remain. My private journal is not shared. This is peer encouragement, not counselling. Sharing does not alert your contact; seek human support for urgent help.')
REVIEW_VERSION='community-review-2'
REVIEW_NOTICE='Help keep the garden kind. Check for identifying details, harassment, unsafe advice and distress before approving. Hold flagged content for support; another moderator reviews your own sharing.'
FLOWERS=('Lily','Peony','Rose','Iris','Jasmine','Daisy','Hibiscus','Orchid','Marigold','Sunflower','Lotus','Violet')
REASONS={'privacy','unsafe','harassment','needs_support','community_fit','other'}

def fail(code,message):raise HTTPException(code,message,headers={'Cache-Control':'no-store'})
def member(user:AccountResponse=Depends(get_current_user)):
    if not user.wellness_consent_current:fail(403,'Current wellness consent is required to use the community.')
    return user
def staff(user:AccountResponse=Depends(get_current_user)):
    with Session(engine) as db:
        if db.get(Moderator,user.user_id) is None:fail(403,'Community moderator access is required.')
    return user
def owner_lock(db,user):
    if db.scalar(select(User.user_id).where(User.user_id==user.user_id).with_for_update()) is None:fail(401,'Please log in again.')
def now(db):return db.scalar(select(func.clock_timestamp()))
def privacy_signal(value):return bool(re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://|www\.|(?<!\w)\+?\d[\d ().-]{6,}\d(?!\w)',value,re.I))
def flags(value):return bool(support_signal(value)),privacy_signal(value)
def model(kind):return Post if kind=='post' else Feedback
def identifier(row):return row.post_id if isinstance(row,Post) else row.feedback_id
def public(row,user):
    value={'id':str(identifier(row)),'content':row.content,'published_at':row.published_at,'is_mine':row.author_id==user.user_id,'author_label':'A petal from '+FLOWERS[identifier(row).int % len(FLOWERS)]+' 🌸'}
    if isinstance(row,Post):value['title']=row.title
    return value
def own(row):
    value={'id':str(identifier(row)),'kind':'post' if isinstance(row,Post) else 'feedback','content':row.content,'status':row.status,'created_at':row.created_at,'support_required':row.support_flag,'review_reason':row.review_reason}
    if isinstance(row,Post):value['title']=row.title
    return value

class Submission(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_id:UUID
    content:str=Field(min_length=1,max_length=2000)
    notice_version:str=Field(max_length=40)
    acknowledged:StrictBool
    @field_validator('content')
    @classmethod
    def text(cls,value):
        value=value.strip()
        if not value or any(ord(c)<32 and c not in '\n\r\t' for c in value):raise ValueError('Enter text without control characters.')
        return value
class PostCreate(Submission):
    title:str=Field(min_length=1,max_length=120)
    @field_validator('title')
    @classmethod
    def title_text(cls,value):return Submission.text(value).replace('\n',' ').replace('\r',' ')
class FeedbackCreate(Submission):content:str=Field(min_length=1,max_length=500)
class ReportCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reason:Literal['privacy','unsafe','harassment','other']
class ReviewCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['publish','reject']
    reason:Literal['privacy','unsafe','harassment','needs_support','community_fit','other']
    expected_revision:int=Field(strict=True,ge=1)
    notice_version:str=Field(max_length=40)
    acknowledged:StrictBool
def acknowledgement(data):
    if data.notice_version!=VERSION or not data.acknowledged:fail(409,'Read and agree to the current community-sharing notice.')
def quota(db,table,user_id,maximum):
    if db.scalar(select(func.count()).select_from(table).where(table.author_id==user_id,table.created_at>now(db)-timedelta(days=1)))>=maximum:fail(429,'Your daily sharing limit has been reached. Please return later.')

@router.get('/notice')
def notice(response:Response,user:AccountResponse=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:is_staff=db.get(Moderator,user.user_id) is not None
    return {'notice_version':VERSION,'text':NOTICE,'is_moderator':is_staff,'review_version':REVIEW_VERSION,'review_text':REVIEW_NOTICE}

@router.post('/posts',status_code=201)
def create_post(data:PostCreate,response:Response,user:AccountResponse=Depends(member)):
    response.headers['Cache-Control']='no-store';acknowledgement(data)
    with Session(engine) as db,db.begin():
        owner_lock(db,user)
        old=db.scalar(select(Post).where(Post.author_id==user.user_id,Post.request_id==data.request_id))
        if old:
            if old.title!=data.title or old.content!=data.content:fail(409,'This request identifier belongs to a different submission.')
            return own(old)
        quota(db,Post,user.user_id,10);support,privacy=flags(data.title+'\n'+data.content)
        row=Post(author_id=user.user_id,request_id=data.request_id,title=data.title,content=data.content,status='flagged' if support or privacy else 'pending',support_flag=support,privacy_flag=privacy,notice_version=VERSION,notice_text=NOTICE)
        db.add(row);db.flush();return own(row)

@router.get('/feed')
def feed(response:Response,limit:int=Query(12,ge=1,le=24),offset:int=Query(0,ge=0,le=10000),user:AccountResponse=Depends(member)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:
        rows=db.scalars(select(Post).where(Post.status=='published').order_by(Post.published_at.desc(),Post.post_id.desc()).offset(offset).limit(limit)).all()
        return [public(row,user) for row in rows]

@router.get('/mine')
def mine(response:Response,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=10000),user:AccountResponse=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:
        # Independent pagination for each category keeps private submission history bounded.
        posts=db.scalars(select(Post).where(Post.author_id==user.user_id).order_by(Post.created_at.desc(),Post.post_id.desc()).offset(offset).limit(limit)).all()
        feedback=db.scalars(select(Feedback).where(Feedback.author_id==user.user_id).order_by(Feedback.created_at.desc(),Feedback.feedback_id.desc()).offset(offset).limit(limit)).all()
        return {'posts':[own(row) for row in posts],'feedback':[own(row) for row in feedback]}

@router.get('/posts/{post_id}')
def read_post(post_id:UUID,response:Response,offset:int=Query(0,ge=0,le=10000),limit:int=Query(20,ge=1,le=50),user:AccountResponse=Depends(member)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:
        post=db.get(Post,post_id)
        if not post or post.status!='published':fail(404,'This shared reflection is unavailable.')
        rows=db.scalars(select(Feedback).where(Feedback.post_id==post_id,Feedback.status=='published').order_by(Feedback.published_at,Feedback.feedback_id).offset(offset).limit(limit)).all()
        return {'post':public(post,user),'feedback':[public(row,user) for row in rows]}

@router.post('/posts/{post_id}/feedback',status_code=201)
def create_feedback(post_id:UUID,data:FeedbackCreate,response:Response,user:AccountResponse=Depends(member)):
    response.headers['Cache-Control']='no-store';acknowledgement(data)
    with Session(engine) as db,db.begin():
        owner_lock(db,user)
        old=db.scalar(select(Feedback).where(Feedback.author_id==user.user_id,Feedback.request_id==data.request_id))
        if old:
            if old.post_id!=post_id or old.content!=data.content:fail(409,'This request identifier belongs to a different response.')
            return own(old)
        post=db.scalar(select(Post).where(Post.post_id==post_id).with_for_update())
        if not post or post.status!='published':fail(404,'This shared reflection is unavailable.')
        if post.author_id==user.user_id:fail(400,'Peer encouragement is for another student’s reflection.')
        quota(db,Feedback,user.user_id,20);support,privacy=flags(data.content)
        row=Feedback(author_id=user.user_id,request_id=data.request_id,post_id=post_id,content=data.content,status='flagged' if support or privacy else 'pending',support_flag=support,privacy_flag=privacy,notice_version=VERSION,notice_text=NOTICE)
        db.add(row);db.flush();return own(row)

def locked_target(db,kind,target_id):
    if kind=='post':return db.scalar(select(Post).where(Post.post_id==target_id).with_for_update())
    parent=db.scalar(select(Feedback.post_id).where(Feedback.feedback_id==target_id))
    if parent is None:return None
    db.scalar(select(Post.post_id).where(Post.post_id==parent).with_for_update())
    return db.scalar(select(Feedback).where(Feedback.feedback_id==target_id).with_for_update())

@router.post('/{kind}/{target_id}/withdraw')
def withdraw(kind:Literal['post','feedback'],target_id:UUID,response:Response,user:AccountResponse=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db,db.begin():
        owner_lock(db,user);row=locked_target(db,kind,target_id)
        if not row or row.author_id!=user.user_id:fail(404,'Your shared submission was not found.')
        if row.status!='withdrawn':row.status='withdrawn';row.revision+=1
        return own(row)

@router.post('/{kind}/{target_id}/report',status_code=201)
def report(kind:Literal['post','feedback'],target_id:UUID,data:ReportCreate,response:Response,user:AccountResponse=Depends(member)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db,db.begin():
        owner_lock(db,user);row=locked_target(db,kind,target_id)
        if not row or row.status!='published' or (kind=='feedback' and db.get(Post,row.post_id).status!='published'):fail(404,'This shared content is unavailable.')
        old=db.scalar(select(Report).where(Report.reporter_id==user.user_id,Report.kind==kind,Report.target_id==target_id))
        if old:return {'recorded':True}
        count=db.scalar(select(func.count()).select_from(Report).where(Report.reporter_id==user.user_id,Report.created_at>now(db)-timedelta(days=1)))
        if count>=30:fail(429,'Your daily report limit has been reached.')
        db.add(Report(reporter_id=user.user_id,kind=kind,target_id=target_id,reason=data.reason));row.revision+=1
        return {'recorded':True}

@router.get('/moderation/queue')
def queue(response:Response,user:AccountResponse=Depends(staff)):
    response.headers['Cache-Control']='no-store';items=[]
    with Session(engine) as db:
        for kind,table in (('post',Post),('feedback',Feedback)):
            reported=select(Report.report_id).where(Report.kind==kind,Report.target_id==(Post.post_id if kind=='post' else Feedback.feedback_id),Report.resolved_at.is_(None)).exists()
            query=select(table).where(table.author_id!=user.user_id,((table.status.in_(('pending','flagged')))|((table.status=='published')&reported)))
            if kind=='feedback':query=query.join(Post,Post.post_id==Feedback.post_id).where(Post.status=='published')
            for row in db.scalars(query.order_by(table.support_flag.desc(),table.privacy_flag.desc(),table.created_at).limit(50)):
                reports=db.scalars(select(Report.reason).where(Report.kind==kind,Report.target_id==identifier(row),Report.resolved_at.is_(None))).all()
                value=own(row);value.update(revision=row.revision,privacy_flag=row.privacy_flag,reports=reports);items.append(value)
    items.sort(key=lambda x:(not x['support_required'],not bool(x['reports']),not x['privacy_flag'],x['created_at'],x['id']))
    return {'items':items[:20],'notice_version':REVIEW_VERSION,'text':REVIEW_NOTICE}

@router.post('/moderation/{kind}/{target_id}')
def review(kind:Literal['post','feedback'],target_id:UUID,data:ReviewCreate,response:Response,user:AccountResponse=Depends(staff)):
    response.headers['Cache-Control']='no-store'
    if data.notice_version!=REVIEW_VERSION or not data.acknowledged:fail(409,'Acknowledge the current moderation checklist.')
    with Session(engine) as db,db.begin():
        owner_lock(db,user)
        if db.get(Moderator,user.user_id) is None:fail(403,'Community moderator access is required.')
        row=locked_target(db,kind,target_id)
        if not row:fail(404,'Submission was not found.')
        if row.author_id==user.user_id:fail(403,'A different moderator must review your own sharing.')
        if row.revision!=data.expected_revision:fail(409,'This submission changed. Refresh the review queue.')
        if row.status not in ('pending','flagged','published'):fail(409,'This submission is no longer awaiting that decision.')
        if kind=='feedback' and db.get(Post,row.post_id).status!='published':fail(409,'The parent reflection is no longer published.')
        if data.action=='publish' and (row.status!='pending' or row.support_flag or row.privacy_flag):fail(409,'Flagged or previously reviewed content cannot be published. Decline it with a reason.')
        if data.action=='publish' and data.reason!='community_fit':fail(422,'Use community suitability when approving a submission.')
        row.status='published' if data.action=='publish' else 'rejected';row.reviewed_at=now(db);row.review_reason=data.reason;row.revision+=1
        if data.action=='publish':row.published_at=row.reviewed_at
        db.add(Review(moderator_id=user.user_id,kind=kind,target_id=target_id,action=data.action,reason=data.reason))
        db.execute(update(Report).where(Report.kind==kind,Report.target_id==target_id,Report.resolved_at.is_(None)).values(resolved_at=row.reviewed_at))
        return {'status':row.status}
