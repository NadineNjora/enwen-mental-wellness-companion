"""Private, account-owned conversations and idempotent chat turns."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    conversation_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(80), nullable=False)
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    safety_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ChatTurn(Base):
    __tablename__ = "chat_turns"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_chat_turn_user_request"),
        CheckConstraint("status IN ('pending', 'complete', 'crisis', 'failed')", name="ck_chat_turn_status"),
        CheckConstraint("length(user_text) BETWEEN 1 AND 2000", name="ck_chat_turn_user_length"),
        CheckConstraint("assistant_text IS NULL OR length(assistant_text) BETWEEN 1 AND 12000", name="ck_chat_turn_assistant_length"),
    )

    turn_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("chat_conversations.conversation_id"), nullable=False, index=True)
    user_text: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    safety_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
