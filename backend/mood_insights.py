"""Private descriptive summaries. Separate scales; no diagnosis or causation."""
from collections import Counter,defaultdict
from datetime import datetime,time,timedelta,timezone
from fastapi import APIRouter,Depends,Response,Query,HTTPException
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from authentication import AccountResponse
from database import engine
from models import MoodEntry
from mood_context_models import MoodContext,CONTEXTS
from moods import require_mood_consent

router=APIRouter(prefix='/moods',tags=['Mood insights'])
EAT=timezone(timedelta(hours=3))

@router.get('/context-options')
def options(response:Response,user:AccountResponse=Depends(require_mood_consent)):
    response.headers['Cache-Control']='no-store'
    return {'maximum':6,'options':[{'key':k,'label':v[0],'emoji':v[1]} for k,v in CONTEXTS.items()]}

@router.get('/insights')
def insights(response:Response,days:int=Query(30,ge=7,le=90),user:AccountResponse=Depends(require_mood_consent)):
    response.headers['Cache-Control']='no-store'
    if days not in (7,30,90):raise HTTPException(422,'Choose a 7, 30 or 90 day window.')
    with Session(engine) as db:
        now=db.scalar(select(func.clock_timestamp()));today=now.astimezone(EAT).date()
        start=today-timedelta(days=days-1);boundary=datetime.combine(start,time.min,tzinfo=EAT)
        rows=db.execute(select(MoodEntry.mood_id,MoodEntry.mood_score,MoodEntry.scale_max,MoodEntry.created_at).where(
            MoodEntry.user_id==user.user_id,MoodEntry.created_at>=boundary,MoodEntry.created_at<=now)).all()
        tags=db.execute(select(MoodContext.mood_id,MoodContext.context_key).join(MoodEntry,MoodEntry.mood_id==MoodContext.mood_id).where(
            MoodEntry.user_id==user.user_id,MoodEntry.created_at>=boundary,MoodEntry.created_at<=now)).all()
    by_scale=defaultdict(list);day_counts=Counter();times=Counter();weekdays=Counter()
    for row in rows:
        local=row.created_at.astimezone(EAT);by_scale[row.scale_max].append(row.mood_score)
        day_counts[local.date().isoformat()]+=1;weekdays[local.weekday()]+=1
        times['night' if local.hour<6 else 'morning' if local.hour<12 else 'afternoon' if local.hour<18 else 'evening']+=1
    counts=Counter(key for _,key in tags);labelled={identifier for identifier,_ in tags}
    scores=[row.mood_score*10/row.scale_max for row in rows]
    return {'period_days':days,'timezone':'Africa/Nairobi (UTC+03:00)','start_date':start,'end_date':today,
        'total_checkins':len(rows),'days_with_checkins':len(day_counts),'unlabelled_checkins':len(rows)-len(labelled),
        'normalised_summary':{'scale_max':10,'count':len(scores),'average_score':round(sum(scores)/len(scores),1) if scores else None},
        'scale_summaries':[{'scale_max':scale,'count':len(scores),'average_score':round(sum(scores)/len(scores),1),'minimum':min(scores),'maximum':max(scores)} for scale,scores in sorted(by_scale.items(),reverse=True)],
        'contexts':[{'key':key,'label':CONTEXTS[key][0],'emoji':CONTEXTS[key][1],'count':count} for key,count in sorted(counts.items(),key=lambda x:(-x[1],x[0]))],
        'daily':[{'date':(start+timedelta(days=n)).isoformat(),'count':day_counts[(start+timedelta(days=n)).isoformat()]} for n in range(days)],
        'weekdays':[{'label':name,'count':weekdays[i]} for i,name in enumerate(('Mon','Tue','Wed','Thu','Fri','Sat','Sun'))],
        'times':[{'key':key,'label':label,'count':times[key]} for key,label in (('morning','Morning · 06:00–11:59'),('afternoon','Afternoon · 12:00–17:59'),('evening','Evening · 18:00–23:59'),('night','Night · 00:00–05:59'))],
        'explanation':'Only your saved check-ins are summarised. Multiple check-ins on one day each count. The display uses score divided by the recorded maximum, multiplied by ten; original records are retained. Factors are your selections, not causes or a mental-health assessment. Older notes are not analysed to invent factors.'}
