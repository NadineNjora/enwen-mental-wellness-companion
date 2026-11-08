"""Real email enrollment is separate from fictional contact-test decisions."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class LiveContactInvitation(Base):
    __tablename__ = "live_contact_invitations"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_live_invite_request"),
        CheckConstraint("delivery_status IN ('dispatching','provider_accepted','uncertain')", name="ck_live_invite_delivery"),
        CheckConstraint("decision IS NULL OR decision IN ('accepted','declined')", name="ck_live_invite_decision"),
        CheckConstraint("expires_at > created_at", name="ck_live_invite_expiry"),
    )
    invitation_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.user_id"), index=True)
    request_id: Mapped[UUID] = mapped_column()
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))
    shared_student_name: Mapped[str] = mapped_column(String(100))
    consent_version: Mapped[str] = mapped_column(String(40))
    consent_text: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    withdrawal_hash: Mapped[str] = mapped_column(String(64), unique=True)
    delivery_status: Mapped[str] = mapped_column(String(24), default="dispatching")
    provider_reference: Mapped[str | None] = mapped_column(String(512))
    decision: Mapped[str | None] = mapped_column(String(8))
    recipient_notice_version: Mapped[str | None] = mapped_column(String(40))
    recipient_notice_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
