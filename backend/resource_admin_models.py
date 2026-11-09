"""Public-source curation roles, immutable review drafts and revision audit."""
from datetime import datetime
from uuid import UUID,uuid4
from sqlalchemy import DateTime,ForeignKey,Integer,String,Text,UniqueConstraint,CheckConstraint,func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped,mapped_column
from models import Base
from resource_models import WellnessResource

class ResourceCurator(Base):
    __tablename__='resource_curators'
    user_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),primary_key=True)
    granted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())

class ResourceDraft(Base):
    __tablename__='resource_drafts'
    __table_args__=(UniqueConstraint('creator_id','request_id',name='uq_resource_draft_request'),CheckConstraint("status IN ('draft','published','discarded')",name='ck_resource_draft_status'))
    draft_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    creator_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),index=True)
    request_id:Mapped[UUID]=mapped_column()
    resource_id:Mapped[str]=mapped_column(String(60),index=True)
    base_revision:Mapped[int]=mapped_column(Integer)
    base_fingerprint:Mapped[str]=mapped_column(String(64))
    payload:Mapped[dict]=mapped_column(JSONB)
    status:Mapped[str]=mapped_column(String(20),default='draft')
    published_revision:Mapped[int|None]=mapped_column(Integer)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class ResourceAudit(Base):
    __tablename__='resource_audit'
    __table_args__=(UniqueConstraint('actor_id','request_id',name='uq_resource_audit_request'),UniqueConstraint('resource_id','revision',name='uq_resource_audit_revision'))
    audit_id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    actor_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),index=True)
    request_id:Mapped[UUID]=mapped_column()
    resource_id:Mapped[str]=mapped_column(ForeignKey('wellness_resources.resource_id'),index=True)
    revision:Mapped[int]=mapped_column(Integer)
    action:Mapped[str]=mapped_column(String(20))
    reason:Mapped[str]=mapped_column(Text)
    before:Mapped[dict|None]=mapped_column(JSONB)
    after:Mapped[dict]=mapped_column(JSONB)
    notice_version:Mapped[str]=mapped_column(String(40))
    notice_text:Mapped[str]=mapped_column(Text)
    recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())
