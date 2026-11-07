from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from models import Base
from trusted_contact_models import TrustedContact


class TrustedContactInvitation(Base):
    __tablename__ = "trusted_contact_invitations"

    __table_args__ = (
        CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name="ck_contact_invitation_token_hash",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_contact_invitation_expiry",
        ),
        CheckConstraint(
            "decision IS NULL OR decision IN ('accepted', 'declined')",
            name="ck_contact_invitation_decision",
        ),
        CheckConstraint(
            "(decision IS NULL AND used_at IS NULL) OR "
            "(decision IS NOT NULL AND used_at IS NOT NULL)",
            name="ck_contact_invitation_response",
        ),
        CheckConstraint(
            "used_at IS NULL OR revoked_at IS NULL",
            name="ck_contact_invitation_not_revoked_and_used",
        ),
        CheckConstraint(
            "used_at IS NULL OR "
            "(used_at >= created_at AND used_at <= expires_at)",
            name="ck_contact_invitation_response_time",
        ),
        CheckConstraint(
            "delivery_mode = 'local_test'",
            name="ck_contact_invitation_test_only",
        ),
        Index(
            "uq_contact_invitation_open",
            "contact_id",
            unique=True,
            postgresql_where=text("used_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    invitation_id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4,
    )

    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("trusted_contacts.contact_id"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False,
    )

    delivery_mode: Mapped[str] = mapped_column(
        String(16),
        default="local_test",
        server_default=text("'local_test'"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    decision: Mapped[str | None] = mapped_column(
        String(8),
    )