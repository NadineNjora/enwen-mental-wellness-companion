"""Database-backed BM25 retrieval over attributed, curated resource summaries.

No embeddings or full publisher documents are claimed. Queries are transient;
this store contains public resources only, never student journals or chat text.
"""
import json,math,re
from collections import Counter
from pathlib import Path
from sqlalchemy import Boolean,String,Text,select
from sqlalchemy.orm import Mapped,mapped_column,Session
from models import Base
from database import engine
from resource_models import WellnessResource

class KnowledgePassage(Base):
    __tablename__="knowledge_passages"
    resource_id: Mapped[str]=mapped_column(String(100),primary_key=True)
    title: Mapped[str]=mapped_column(String(300))
    publisher: Mapped[str]=mapped_column(String(200))
    category: Mapped[str]=mapped_column(String(50))
    summary: Mapped[str]=mapped_column(Text)
    url: Mapped[str]=mapped_column(String(1500))
    audience_note: Mapped[str]=mapped_column(Text)
    source_checked_on: Mapped[str]=mapped_column(String(20))
    active: Mapped[bool]=mapped_column(Boolean,default=True)

FIELDS=("resource_id","title","publisher","category","summary","url","audience_note","source_checked_on")
STOP=set("the and this that have with for feel feeling about what how can you my your are was from into".split())
EXPAND={"exams":"coursework studies academic stress", "exam":"coursework studies academic stress", "fees":"money financial worries", "rent":"money financial worries", "sleeping":"sleep rest", "insomnia":"sleep rest", "lonely":"loneliness connection", "alone":"loneliness connection", "overwhelmed":"stress grounding", "counsellor":"counselling support", "counselor":"counselling support", "masomo":"coursework studies academic stress", "pesa":"money financial worries", "usingizi":"sleep rest"}
def tokens(text):return [w for w in re.findall(r"[a-z]{3,}",text.lower()) if w not in STOP]
def rank(query,rows,limit=3):
    words=tokens(query);words+=tokens(" ".join(EXPAND.get(w,"") for w in words));terms=set(words)
    if not terms or not rows:return []
    documents=[tokens(" ".join(str(row[k]) for k in ("title","category","summary","publisher"))) for row in rows]
    counts=[Counter(doc) for doc in documents];average=sum(map(len,documents))/len(documents) or 1
    frequency={term:sum(term in c for c in counts) for term in terms};scored=[]
    for row,doc,counter in zip(rows,documents,counts):
        score=0.0
        for term in terms:
            tf=counter[term]
            if tf:score+=math.log(1+(len(rows)-frequency[term]+.5)/(frequency[term]+.5))*tf*2.2/(tf+1.2*(.25+.75*len(doc)/average))
        if score>0:scored.append((score,row))
    scored.sort(key=lambda pair:(-pair[0],pair[1]['resource_id']))
    return [dict(row,retrieval_method="BM25 over curated database summaries") for _,row in scored[:limit]]
def retrieve(query):
    with Session(engine) as db:
        passages=db.scalars(select(KnowledgePassage).join(WellnessResource,WellnessResource.resource_id==KnowledgePassage.resource_id).where(KnowledgePassage.active.is_(True),WellnessResource.active.is_(True)).limit(1000)).all()
        return rank(query,[{key:getattr(row,key) for key in FIELDS} for row in passages])
def seed():
    KnowledgePassage.__table__.create(bind=engine,checkfirst=True)
    rows=json.loads(Path(__file__).with_name('resources_catalog.json').read_text(encoding='utf-8-sig'))
    with Session(engine) as db,db.begin():
        for row in rows:
            if db.get(KnowledgePassage,row['resource_id']) is None:db.add(KnowledgePassage(**{key:row[key] for key in FIELDS}))
    print('Knowledge summaries ready; existing reviewed entries preserved. No student data indexed.')
if __name__=='__main__':seed()
