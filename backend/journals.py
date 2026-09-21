from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AccountResponse, get_current_user
from database import engine
from journal_models import JournalEntry

router = APIRouter(prefix="/journals", tags=["Journaling"])


class JournalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=150)
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("title", "content")
    @classmethod
    def reject_blank_text(cls, value: str):
        if "\x00" in value:
            raise ValueError("Null characters are not allowed.")
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        return value


class JournalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    journal_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class JournalResponse(JournalSummary):
    content: str


def require_journal_consent(
    current_user: AccountResponse = Depends(get_current_user),
):
    if not current_user.wellness_consent_current:
        raise HTTPException(403, "Current wellness consent is required.")
    return current_user


@router.post("", response_model=JournalResponse, status_code=201)
def create_journal(
    data: JournalCreate,
    response: Response,
    current_user: AccountResponse = Depends(require_journal_consent),
):
    try:
        with Session(engine) as session:
            with session.begin():
                entry = JournalEntry(
                    user_id=current_user.user_id,
                    title=data.title,
                    content=data.content,
                )
                session.add(entry)
                session.flush()
                result = JournalResponse.model_validate(entry)
    except SQLAlchemyError:
        raise HTTPException(503, "Journal entry could not be saved.") from None

    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("", response_model=list[JournalSummary])
def list_my_journals(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AccountResponse = Depends(require_journal_consent),
):
    try:
        with Session(engine) as session:
            rows = session.execute(
                select(
                    JournalEntry.journal_id,
                    JournalEntry.title,
                    JournalEntry.created_at,
                    JournalEntry.updated_at,
                )
                .where(JournalEntry.user_id == current_user.user_id)
                .order_by(JournalEntry.created_at.desc(), JournalEntry.journal_id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            result = [JournalSummary.model_validate(row) for row in rows]
    except SQLAlchemyError:
        raise HTTPException(503, "Journal history is temporarily unavailable.") from None

    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{journal_id}", response_model=JournalResponse)
def read_my_journal(
    journal_id: UUID,
    response: Response,
    current_user: AccountResponse = Depends(require_journal_consent),
):
    try:
        with Session(engine) as session:
            entry = session.scalar(
                select(JournalEntry).where(
                    JournalEntry.journal_id == journal_id,
                    JournalEntry.user_id == current_user.user_id,
                )
            )
            if entry is None:
                raise HTTPException(404, "Journal entry not found.")
            result = JournalResponse.model_validate(entry)
    except SQLAlchemyError:
        raise HTTPException(503, "Journal entry is temporarily unavailable.") from None

    response.headers["Cache-Control"] = "no-store"
    return result