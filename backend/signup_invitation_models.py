"""Explicit signup email choice; separate from historical contact-testing consent."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime,ForeignKey,String,Text,func
from sqlalchemy.orm import Mapped,mapped_column
from models import Base

class SignupInvitationChoice(Base):
    __tablename__='signup_invitation_choices'
    user_id:Mapped[UUID]=mapped_column(ForeignKey('users.user_id'),primary_key=True)
    request_id:Mapped[UUID]=mapped_column(unique=True)
    notice_version:Mapped[str]=mapped_column(String(40))
    notice_text:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(32),default='requested')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.clock_timestamp())
