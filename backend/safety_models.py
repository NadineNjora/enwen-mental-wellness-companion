"""Durable local support-flow outbox; contains no chat content or phone numbers."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models import Base
from trusted_contact_models import TrustedContact


class SafetyAlert(Base):
    __tablename__ = "safety_alerts"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_safety_alert_user_request"),
        CheckConstraint(
            "status IN ('dispatching', 'local_test_captured', 'blocked_no_contact', "
            "'blocked_unconfirmed', 'blocked_consent', 'blocked_live_not_configured', "
            "'blocked_cooldown', 'uncertain')",
            name="ck_safety_alert_status",
        ),
        CheckConstraint("delivery_mode = 'local_test'", name="ck_safety_alert_local_only"),
        Index("ix_safety_alert_contact_created", "contact_id", "created_at"),
    )

    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    # No cross-module dependency on the optional chat-history implementation.
    conversation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    contact_id: Mapped[UUID | None] = mapped_column(ForeignKey("trusted_contacts.contact_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="local_test")
    demonstration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
