from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    __table_args__ = (
        CheckConstraint(
            "confirmation_status IN ('pending', 'confirmed', 'declined', 'revoked')",
            name="ck_trusted_contacts_confirmation_status",
        ),
        CheckConstraint(
            "confirmation_status <> 'confirmed' OR confirmed_at IS NOT NULL",
            name="ck_trusted_contacts_confirmation_time",
        ),
    )

    contact_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.user_id"),
        unique=True,
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    relationship_label: Mapped[str | None] = mapped_column(
        String(50),
    )

    email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
    )

    confirmation_status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default=text("'pending'"),
        nullable=False,
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )