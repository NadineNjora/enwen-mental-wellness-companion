"""Private, non-diagnostic suggestions from the owner's most recent check-in."""
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from authentication import AccountResponse,get_current_user
from models import MoodEntry
from database import engine
from knowledge import retrieve
router=APIRouter(prefix='/wellness',tags=['Personal wellness suggestions'])
def suggest(entry):
    if entry is None:return {'basis':'No check-in yet. Choose a starting point that suits you.','latest_checkin':None,'steps':[{'title':'Start with how today feels','href':'#/check-in'},{'title':'Make room for a thought','href':'#/journal'}],'topic':'student stress'}
    score,scale=entry.mood_score,entry.scale_max
    if score/scale<=.3:
        steps=[{'title':'Try a grounding pause','href':'#/pause'},{'title':'Find a person to talk to','href':'#/resources'},{'title':'Write what you need today','href':'#/journal'}];topic='stress grounding human support'
    elif score/scale<=.6:
        steps=[{'title':'Explore what has been on your mind','href':'#/journal'},{'title':'Take a mindful pause','href':'#/pause'},{'title':'Explore student stress resources','href':'#/resources'}];topic='student coursework stress'
    else:
        steps=[{'title':'Capture what has supported you','href':'#/journal'},{'title':'Notice your mood over time','href':'#/mood-history'},{'title':'Make room for rest','href':'#/pause'}];topic='sleep rest connection'
    return {'basis':f'Based only on your latest recorded check-in: {score}/{scale}. You choose what feels useful.',
            'latest_checkin':{'score':score,'scale_max':scale,'created_at':entry.created_at},'steps':steps,'topic':topic}
@router.get('/suggestions')
def recommendations(response:Response,user:AccountResponse=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    if not user.wellness_consent_current:raise HTTPException(403,'Current wellness consent is required.')
    try:
        with Session(engine) as db:
            entry=db.scalar(select(MoodEntry).where(MoodEntry.user_id==user.user_id).order_by(MoodEntry.created_at.desc(),MoodEntry.mood_id.desc()).limit(1))
            result=suggest(entry)
        topic=result.pop('topic');result['resources']=retrieve(topic)
        result['explanation']='Suggestions are selectable wellbeing starting points, not an assessment, diagnosis or risk prediction. Journal contents and mood notes are not sent to the AI.'
        return result
    except SQLAlchemyError:raise HTTPException(503,'Suggestions are temporarily unavailable. Your saved check-ins are unchanged.') from None
