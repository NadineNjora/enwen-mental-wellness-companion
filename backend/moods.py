from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AccountResponse, get_current_user
from database import engine
from models import MoodEntry

router = APIRouter(prefix="/moods", tags=["Mood check-ins"])


class MoodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mood_score: int = Field(strict=True, ge=1, le=5)
    note: str | None = Field(default=None, max_length=1000)


class MoodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mood_id: UUID
    mood_score: int
    note: str | None
    created_at: datetime


def require_mood_consent(
    current_user: AccountResponse = Depends(get_current_user),
):
    if not current_user.wellness_consent_current:
        raise HTTPException(403, "Current wellness consent is required.")
    return current_user


@router.post("", response_model=MoodResponse, status_code=201)
def create_mood(
    data: MoodCreate,
    response: Response,
    current_user: AccountResponse = Depends(require_mood_consent),
):
    try:
        with Session(engine) as session:
            with session.begin():
                entry = MoodEntry(
                    user_id=current_user.user_id,
                    mood_score=data.mood_score,
                    note=data.note,
                )
                session.add(entry)
                session.flush()
                result = MoodResponse.model_validate(entry)

    except SQLAlchemyError:
        raise HTTPException(503, "Mood check-in could not be saved.") from None

    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("", response_model=list[MoodResponse])
def list_my_moods(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AccountResponse = Depends(require_mood_consent),
):
    try:
        with Session(engine) as session:
            entries = session.scalars(
                select(MoodEntry)
                .where(MoodEntry.user_id == current_user.user_id)
                .order_by(MoodEntry.created_at.desc(), MoodEntry.mood_id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            result = [MoodResponse.model_validate(entry) for entry in entries]

    except SQLAlchemyError:
        raise HTTPException(503, "Mood history is temporarily unavailable.") from None

    response.headers["Cache-Control"] = "no-store"
    return result