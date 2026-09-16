from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Consent(Base):
    __tablename__ = "consents"

    __table_args__ = (
        CheckConstraint(
            "decision IN ('accepted', 'declined', 'withdrawn')",
            name="ck_consents_decision",
        ),
        CheckConstraint(
            "consent_type IN ('wellness_use', 'contact_alert')",
            name="ck_consents_type",
        ),
    )

    consent_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )
    consent_type: Mapped[str] = mapped_column(String(30))
    notice_version: Mapped[str] = mapped_column(String(30))
    notice_text: Mapped[str] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(20))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )