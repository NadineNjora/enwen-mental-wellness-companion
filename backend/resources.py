from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AccountResponse, get_current_user
from database import engine
from resource_models import ResourceBookmark, WellnessResource

router = APIRouter(prefix="/resources", tags=["Wellness resources"])
Category = Literal["stress", "studies", "rest", "connection", "human-support"]


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resource_id: str
    title: str
    publisher: str
    category: str
    summary: str
    url: str
    audience_note: str
    source_checked_on: date
    saved: bool


def require_resource_consent(current_user: AccountResponse = Depends(get_current_user)):
    if not current_user.wellness_consent_current:
        raise HTTPException(403, "Current wellness consent is required.")
    return current_user


@router.get("", response_model=list[ResourceResponse])
def list_resources(
    response: Response,
    category: Category | None = None,
    q: str = Query(default="", max_length=100),
    saved_only: bool = False,
    current_user: AccountResponse = Depends(require_resource_consent),
):
    resource = WellnessResource
    bookmark = ResourceBookmark
    statement = select(
        resource.resource_id, resource.title, resource.publisher, resource.category,
        resource.summary, resource.url, resource.audience_note, resource.source_checked_on,
        bookmark.resource_id.is_not(None).label("saved"),
    ).outerjoin(bookmark, (bookmark.resource_id == resource.resource_id) & (bookmark.user_id == current_user.user_id)).where(resource.active.is_(True))
    if category:
        statement = statement.where(resource.category == category)
    if q.strip():
        term = q.strip().lower()
        statement = statement.where(or_(
            func.lower(resource.title).contains(term, autoescape=True),
            func.lower(resource.summary).contains(term, autoescape=True),
            func.lower(resource.publisher).contains(term, autoescape=True),
        ))
    if saved_only:
        statement = statement.where(bookmark.resource_id.is_not(None))
    try:
        with Session(engine) as session:
            result = [ResourceResponse.model_validate(row) for row in session.execute(statement.order_by(resource.title)).all()]
    except SQLAlchemyError:
        raise HTTPException(503, "The resource library is temporarily unavailable.") from None
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/{resource_id}/bookmark", status_code=204, response_class=Response)
def save_resource(resource_id: str, current_user: AccountResponse = Depends(require_resource_consent)):
    try:
        with Session(engine) as session, session.begin():
            row=session.get(WellnessResource, resource_id)
            if row is None or not row.active:
                raise HTTPException(404, "Resource not found.")
            session.execute(insert(ResourceBookmark).values(user_id=current_user.user_id, resource_id=resource_id).on_conflict_do_nothing())
    except SQLAlchemyError:
        raise HTTPException(503, "We could not confirm that this resource was saved. Refresh the library before trying again.") from None
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.delete("/{resource_id}/bookmark", status_code=204, response_class=Response)
def unsave_resource(resource_id: str, current_user: AccountResponse = Depends(get_current_user)):
    try:
        with Session(engine) as session, session.begin():
            if session.get(WellnessResource, resource_id) is None:
                raise HTTPException(404, "Resource not found.")
            session.execute(delete(ResourceBookmark).where(ResourceBookmark.user_id == current_user.user_id, ResourceBookmark.resource_id == resource_id))
    except SQLAlchemyError:
        raise HTTPException(503, "We could not confirm the change. Refresh the library before trying again.") from None
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
