from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class WellnessResource(Base):
    __tablename__ = "wellness_resources"

    resource_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    publisher: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    audience_note: Mapped[str] = mapped_column(String(300), nullable=False)
    source_checked_on: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResourceBookmark(Base):
    __tablename__ = "resource_bookmarks"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("wellness_resources.resource_id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
