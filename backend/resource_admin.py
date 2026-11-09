"""Review drafts, publish and retire public sources with atomic knowledge sync."""
import hashlib,json
from datetime import date,timedelta,timezone
from typing import Literal,Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Response,Query
from pydantic import BaseModel,ConfigDict,Field,StrictBool,StringConstraints,field_validator
from sqlalchemy import select,func,text
from sqlalchemy.orm import Session
from authentication import AccountResponse,get_current_user
from database import engine
from models import User
from resource_models import WellnessResource as Resource
from resource_admin_models import ResourceCurator as Curator,ResourceDraft as Draft,ResourceAudit as Audit
from knowledge import KnowledgePassage, FIELDS
from resource_policy import SOURCES,source,MAX_ACTIVE_RESOURCES

router=APIRouter(prefix='/resource-admin',tags=['Public resource curation'])
VERSION='resource-review-1'
RETIRE_VERSION='resource-retire-1'
RETIRE_NOTICE=('I choose to retire this public resource and have supplied the reason. It will be excluded from new library results and new AI retrieval. Student bookmarks, old chat citations and public-resource revision history will be retained. Restoring it requires a fresh source-reviewed draft. This action does not edit or delete private student records.')
NOTICE=('I have opened this public source today and checked the final destination, publisher, summary and audience limitations. '
 'The summary is in my own words, follows the source, and does not add diagnoses, treatment claims or instructions to the AI. '
 'I understand publication changes the student resource library and the public-summary corpus used by Llama. '
 'Source review is not clinical certification. Retirement removes a resource from new library results and new AI retrieval; bookmarks and previously saved chat citations are retained. '
 'My decision and before/after public metadata are kept in the revision history. This role does not grant access to private student records.')
ResourceId=Annotated[str,StringConstraints(pattern=r'^[a-z0-9][a-z0-9-]{2,59}$')]
Category=Literal['stress','studies','rest','connection','human-support']

def fail(code,message):raise HTTPException(code,message,headers={'Cache-Control':'no-store'})
def curator(user:AccountResponse=Depends(get_current_user)):
    with Session(engine) as db:
        if db.get(Curator,user.user_id) is None:fail(403,'Public-resource curator access is required.')
    return user
def clock(db):return db.scalar(select(func.clock_timestamp()))
def today(db):return clock(db).astimezone(timezone(timedelta(hours=3))).date()
def actor_lock(db,user):
    if db.scalar(select(User.user_id).where(User.user_id==user.user_id).with_for_update()) is None:fail(401,'Please log in again.')
    if db.get(Curator,user.user_id) is None:fail(403,'Public-resource curator access is required.')
def resource_lock(db,identifier):db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:key))'),{'key':'enwen-resource:'+identifier})
def library_lock(db):db.execute(text("SELECT pg_advisory_xact_lock(hashtext('enwen-public-library'))"))
def snapshot(row):
    if row is None:return None
    return {**{key:(getattr(row,key).isoformat() if key=='source_checked_on' else getattr(row,key)) for key in FIELDS},'active':row.active,'revision':row.revision}
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def draft_view(row,user):return {'draft_id':str(row.draft_id),'resource_id':row.resource_id,'base_revision':row.base_revision,'status':row.status,'published_revision':row.published_revision,'payload':row.payload,'created_at':row.created_at,'is_mine':row.creator_id==user.user_id}
def audit_view(row,user):return {'audit_id':str(row.audit_id),'resource_id':row.resource_id,'revision':row.revision,'action':row.action,'reason':row.reason,'before':row.before,'after':row.after,'recorded_at':row.recorded_at,'actor_label':'You' if row.actor_id==user.user_id else 'Another authorised curator'}

class Content(BaseModel):
    model_config=ConfigDict(extra='forbid')
    resource_id:ResourceId
    title:str=Field(min_length=1,max_length=180)
    summary:str=Field(min_length=1,max_length=1200)
    url:str=Field(min_length=1,max_length=500)
    audience_note:str=Field(min_length=1,max_length=300)
    category:Category
    source_checked_on:date
    @field_validator('title','summary','audience_note','url')
    @classmethod
    def clean(cls,value):
        value=value.strip()
        if not value or any(ord(ch)<32 and ch not in '\n\t\r' for ch in value):raise ValueError('Use non-blank text without control characters.')
        return value
    @field_validator('url')
    @classmethod
    def public_source(cls,value):return source(value)[0]
class CreateDraft(Content):
    request_id:UUID
    expected_revision:int=Field(strict=True,ge=0)
class Acknowledgement(BaseModel):
    model_config=ConfigDict(extra='forbid')
    notice_version:str=Field(max_length=40)
    acknowledged:StrictBool
class Retire(Acknowledgement):
    request_id:UUID
    expected_revision:int=Field(strict=True,ge=1)
    reason:str=Field(min_length=1,max_length=300)
    @field_validator('reason')
    @classmethod
    def clean_reason(cls,value):return Content.clean(value)
def acknowledge(data,version=VERSION):
    if data.notice_version!=version or not data.acknowledged:fail(409,'Read and acknowledge the current notice for this resource decision.')

@router.get('/notice')
def notice(response:Response,user:AccountResponse=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:return {'can_curate':db.get(Curator,user.user_id) is not None,'notice_version':VERSION,'text':NOTICE,'retire_version':RETIRE_VERSION,'retire_text':RETIRE_NOTICE,'today':today(db),'timezone':'Africa/Nairobi (UTC+03:00)','sources':[{'host':host,'publisher':name} for host,name in SOURCES.items()],'maximum_active':MAX_ACTIVE_RESOURCES}

@router.get('/resources')
def resources(response:Response,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=10000),user:AccountResponse=Depends(curator)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:return [snapshot(row) for row in db.scalars(select(Resource).order_by(Resource.title,Resource.resource_id).offset(offset).limit(limit))]

@router.post('/drafts',status_code=201)
def create_draft(data:CreateDraft,response:Response,user:AccountResponse=Depends(curator)):
    response.headers['Cache-Control']='no-store'
    payload=data.model_dump(mode='json',exclude={'request_id','expected_revision'});payload['publisher']=source(payload['url'])[1]
    with Session(engine) as db,db.begin():
        actor_lock(db,user)
        old=db.scalar(select(Draft).where(Draft.creator_id==user.user_id,Draft.request_id==data.request_id))
        if old:
            if old.payload!=payload or old.base_revision!=data.expected_revision:fail(409,'This request identifier belongs to a different draft.')
            return draft_view(old,user)
        if data.source_checked_on>today(db):fail(422,'A source-check date cannot be in the future.')
        resource_lock(db,data.resource_id);row=db.scalar(select(Resource).where(Resource.resource_id==data.resource_id).with_for_update());base=snapshot(row)
        if (row.revision if row else 0)!=data.expected_revision:fail(409,'The resource changed. Refresh its current version before preparing a draft.')
        count=db.scalar(select(func.count()).select_from(Draft).where(Draft.creator_id==user.user_id,Draft.created_at>clock(db)-timedelta(days=1)))
        if count>=30:fail(429,'The 30-draft daily limit has been reached.')
        draft=Draft(creator_id=user.user_id,request_id=data.request_id,resource_id=data.resource_id,base_revision=data.expected_revision,base_fingerprint=fingerprint(base),payload=payload)
        db.add(draft);db.flush();return draft_view(draft,user)

@router.get('/drafts')
def drafts(response:Response,state:Literal['draft','published','discarded','all']='draft',limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=10000),user:AccountResponse=Depends(curator)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:
        query=select(Draft)
        if state!='all':query=query.where(Draft.status==state)
        return [draft_view(row,user) for row in db.scalars(query.order_by(Draft.created_at.desc(),Draft.draft_id.desc()).offset(offset).limit(limit))]

@router.post('/drafts/{draft_id}/publish')
def publish(draft_id:UUID,data:Acknowledgement,response:Response,user:AccountResponse=Depends(curator)):
    response.headers['Cache-Control']='no-store';acknowledge(data)
    with Session(engine) as db,db.begin():
        actor_lock(db,user);draft=db.scalar(select(Draft).where(Draft.draft_id==draft_id).with_for_update())
        if not draft:fail(404,'Draft was not found.')
        if draft.status=='discarded':fail(409,'This draft was discarded. Prepare a fresh draft.')
        if draft.status=='published':
            current=db.get(Resource,draft.resource_id)
            return {'recorded_revision':draft.published_revision,'current_revision':current.revision,'active':current.active,'replayed':True}
        library_lock(db);resource_lock(db,draft.resource_id)
        row=db.scalar(select(Resource).where(Resource.resource_id==draft.resource_id).with_for_update());before=snapshot(row)
        if (row.revision if row else 0)!=draft.base_revision or fingerprint(before)!=draft.base_fingerprint:fail(409,'The published resource changed after this draft. Prepare a fresh draft against the current version.')
        content=Content.model_validate({k:v for k,v in draft.payload.items() if k!='publisher'});payload=content.model_dump(mode='json');payload['publisher']=source(content.url)[1]
        if payload!=draft.payload:fail(409,'Source policy changed. Prepare a fresh draft.')
        if content.source_checked_on!=today(db):fail(409,'Publishing requires a source checked today in Nairobi. Recheck the source and prepare a fresh dated draft.')
        duplicate=db.scalar(select(Resource.resource_id).where(Resource.resource_id!=draft.resource_id,Resource.url==payload['url']).limit(1))
        if duplicate:fail(409,'This source URL already has a resource. Update that resource instead of creating a duplicate.')
        if row is None or not row.active:
            if db.scalar(select(func.count()).select_from(Resource).where(Resource.active.is_(True)))>=MAX_ACTIVE_RESOURCES:fail(409,'The active source limit has been reached. Retire an older source first.')
        if row is None:row=Resource(resource_id=draft.resource_id);db.add(row)
        for key in FIELDS:
            if key!='resource_id':setattr(row,key,content.source_checked_on if key=='source_checked_on' else payload[key])
        row.active=True;row.revision=draft.base_revision+1;row.updated_at=clock(db);db.flush()
        passage=db.get(KnowledgePassage,row.resource_id)
        if passage is None:passage=KnowledgePassage(resource_id=row.resource_id);db.add(passage)
        for key in FIELDS:setattr(passage,key,payload[key])
        passage.active=True;draft.status='published';draft.published_revision=row.revision;draft.completed_at=row.updated_at
        db.add(Audit(actor_id=user.user_id,request_id=draft.draft_id,resource_id=row.resource_id,revision=row.revision,action='publish',reason='Source reviewed and publication acknowledged.',before=before,after=snapshot(row),notice_version=VERSION,notice_text=NOTICE))
        return {'recorded_revision':row.revision,'current_revision':row.revision,'active':True,'replayed':False}

@router.post('/drafts/{draft_id}/discard')
def discard(draft_id:UUID,response:Response,user:AccountResponse=Depends(curator)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db,db.begin():
        actor_lock(db,user);row=db.scalar(select(Draft).where(Draft.draft_id==draft_id).with_for_update())
        if not row:fail(404,'Draft was not found.')
        if row.status=='published':fail(409,'This draft is already published. Use retirement to remove the published resource.')
        row.status='discarded';row.completed_at=row.completed_at or clock(db);return {'status':'discarded'}

@router.post('/resources/{resource_id}/retire')
def retire(resource_id:ResourceId,data:Retire,response:Response,user:AccountResponse=Depends(curator)):
    response.headers['Cache-Control']='no-store';acknowledge(data,RETIRE_VERSION)
    with Session(engine) as db,db.begin():
        actor_lock(db,user);old=db.scalar(select(Audit).where(Audit.actor_id==user.user_id,Audit.request_id==data.request_id))
        if old:
            if old.resource_id!=resource_id or old.action!='retire' or old.reason!=data.reason:fail(409,'This request identifier belongs to a different decision.')
            current=db.get(Resource,resource_id);return {'recorded_revision':old.revision,'current_revision':current.revision,'active':current.active,'replayed':True}
        library_lock(db);resource_lock(db,resource_id);row=db.scalar(select(Resource).where(Resource.resource_id==resource_id).with_for_update())
        if not row:fail(404,'Resource was not found.')
        if row.revision!=data.expected_revision:fail(409,'The resource changed. Refresh before retiring it.')
        if not row.active:fail(409,'This resource is already retired.')
        before=snapshot(row);row.active=False;row.revision+=1;row.updated_at=clock(db)
        passage=db.get(KnowledgePassage,resource_id)
        if passage:passage.active=False
        db.add(Audit(actor_id=user.user_id,request_id=data.request_id,resource_id=resource_id,revision=row.revision,action='retire',reason=data.reason,before=before,after=snapshot(row),notice_version=RETIRE_VERSION,notice_text=RETIRE_NOTICE))
        return {'recorded_revision':row.revision,'current_revision':row.revision,'active':False,'replayed':False}

@router.get('/history')
def history(response:Response,limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=10000),user:AccountResponse=Depends(curator)):
    response.headers['Cache-Control']='no-store'
    with Session(engine) as db:return [audit_view(row,user) for row in db.scalars(select(Audit).order_by(Audit.recorded_at.desc(),Audit.audit_id.desc()).offset(offset).limit(limit))]
