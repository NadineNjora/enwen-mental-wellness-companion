"""Explicitly shared community content; no relationship to private journals."""
from datetime import datetime
from uuid import UUID,uuid4
from sqlalchemy import Boolean,CheckConstraint,DateTime,ForeignKey,Integer,String,Text,UniqueConstraint,func
from sqlalchemy.orm import Mapped,mapped_column
from models import Base

class CommunityModerator(Base):
    __tablename__='community_moderators'
    user_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),primary_key=True)
    granted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())

class SharedFields:
    author_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),index=True)
    request_id:Mapped[UUID]=mapped_column()
    content:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(20),default='pending')
    support_flag:Mapped[bool]=mapped_column(Boolean,default=False)
    privacy_flag:Mapped[bool]=mapped_column(Boolean,default=False)
    revision:Mapped[int]=mapped_column(Integer,default=1)
    notice_version:Mapped[str]=mapped_column(String(40))
    notice_text:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())
    published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    review_reason:Mapped[str|None]=mapped_column(String(30))

class CommunityPost(SharedFields,Base):
    __tablename__='community_posts'
    __table_args__=(UniqueConstraint('author_id','request_id',name='uq_community_post_request'),CheckConstraint("status IN ('pending','published','rejected','withdrawn','flagged')",name='ck_community_post_status'),CheckConstraint('length(content) BETWEEN 1 AND 2000',name='ck_community_post_length'))
    post_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    title:Mapped[str]=mapped_column(String(120))

class CommunityFeedback(SharedFields,Base):
    __tablename__='community_feedback'
    __table_args__=(UniqueConstraint('author_id','request_id',name='uq_community_feedback_request'),CheckConstraint("status IN ('pending','published','rejected','withdrawn','flagged')",name='ck_community_feedback_status'),CheckConstraint('length(content) BETWEEN 1 AND 500',name='ck_community_feedback_length'))
    feedback_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    post_id:Mapped[UUID]=mapped_column(ForeignKey('community_posts.post_id'),index=True)

class CommunityReport(Base):
    __tablename__='community_reports'
    __table_args__=(UniqueConstraint('reporter_id','kind','target_id',name='uq_community_report'),CheckConstraint("kind IN ('post','feedback')",name='ck_community_report_kind'))
    report_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    reporter_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),index=True)
    kind:Mapped[str]=mapped_column(String(12))
    target_id:Mapped[UUID]=mapped_column(index=True)
    reason:Mapped[str]=mapped_column(String(30))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())
    resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class CommunityReplyRead(Base):
    """Only a reflection's owner can acknowledge its published replies."""
    __tablename__='community_reply_reads'
    feedback_id:Mapped[UUID]=mapped_column(ForeignKey('community_feedback.feedback_id'),primary_key=True)
    read_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())

class CommunityReview(Base):
    __tablename__='community_reviews'
    review_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    moderator_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),index=True)
    kind:Mapped[str]=mapped_column(String(12))
    target_id:Mapped[UUID]=mapped_column(index=True)
    action:Mapped[str]=mapped_column(String(20))
    reason:Mapped[str]=mapped_column(String(30))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())
