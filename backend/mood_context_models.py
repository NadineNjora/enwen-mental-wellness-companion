"""Student-chosen context; never inferred from private notes or AI."""
from uuid import UUID
from sqlalchemy import ForeignKey,String,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from models import Base

CONTEXTS={
    'coursework':('Coursework','📚'), 'exams':('Exams','📝'),
    'finances':('Money matters','💸'), 'relationships':('Friendships & relationships','🫂'),
    'family':('Family','🏡'), 'sleep':('Sleep','🌙'), 'health':('My health','🌿'),
    'commute':('Commute & getting to class','🚌'), 'weather':('The weather','🌦️'),
    'loneliness':('Feeling disconnected','🫶'), 'celebration':('A special occasion','🎉'),
    'rest':('Rest & things I enjoy','🎧'),
}

class MoodContext(Base):
    __tablename__='mood_contexts'
    __table_args__=(CheckConstraint('context_key IN ('+', '.join(repr(k) for k in CONTEXTS)+')',name='ck_mood_context_key'),)
    mood_id:Mapped[UUID]=mapped_column(ForeignKey('mood_entries.mood_id',ondelete='CASCADE'),primary_key=True)
    context_key:Mapped[str]=mapped_column(String(30),primary_key=True)
