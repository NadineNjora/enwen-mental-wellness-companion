"""Owner-only chat history and request-id based turn lifecycle helpers.

The AI endpoint calls claim_turn before any generation or alert, then finish_turn
once. Replayed completed turns return the stored result; uncertain pending or
failed turns never automatically invoke a provider again.
"""
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AccountResponse, get_current_user
from chat_history_models import ChatConversation, ChatTurn, DeletedChatRequest
from database import engine
from models import User

router = APIRouter(prefix="/chat/conversations", tags=["Private chat history"])


def require_history_consent(user: AccountResponse = Depends(get_current_user)):
    if not user.wellness_consent_current:
        raise HTTPException(403, "Current wellness consent is required to use chat history.")
    return user


def _uuid(value):
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, "A valid conversation/request identifier is required.") from None


def _summary(row):
    return {"conversation_id":str(row.conversation_id), "title":row.title,
            "created_at":row.created_at, "updated_at":row.updated_at,
            "safety_paused":row.safety_paused}


def _turn_result(row, replayed):
    return {"conversation_id":str(row.conversation_id), "turn_id":str(row.turn_id),
            "status":row.status, "replayed":replayed, "reply":row.assistant_text,
            "sources":row.sources or [], "safety":row.safety_payload, "started_at":row.created_at}


def _owner_conversation(session, user_id, conversation_id, *, lock=False):
    query = select(ChatConversation).where(ChatConversation.conversation_id == conversation_id,
                                           ChatConversation.user_id == user_id)
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        # Deliberately indistinguishable from an unknown identifier.
        raise HTTPException(404, "Conversation not found.")
    return row


def _text(value, maximum, label):
    if not isinstance(value, str) or not value.strip() or "\x00" in value or len(value) > maximum:
        raise HTTPException(422, f"{label} must be non-blank text within {maximum} characters.")
    return value


def claim_turn(user_id, request_id, user_text, conversation_id=None, *,
               consent_version=None, consent_text=None, provider=None, safety_event=False):
    """Claim ONE generation/alert attempt; return stored context or a replay.

    Holding the user's row lock serializes simultaneous first-message requests
    as well as requests against different conversations. No provider work runs
    while the transaction or row lock is held.
    """
    user_id, request_id = _uuid(user_id), _uuid(request_id)
    conversation_id = _uuid(conversation_id) if conversation_id else None
    user_text = _text(user_text, 2000, "Your message")
    try:
        with Session(engine) as session:
            with session.begin():
                if session.scalar(select(User.user_id).where(User.user_id == user_id).with_for_update()) is None:
                    raise HTTPException(401, "Please log in again.")
                if session.get(DeletedChatRequest, (user_id, request_id)) is not None:
                    raise HTTPException(410, "This message belonged to a deleted conversation. It was not sent again. Start a new conversation if you choose to write a new message.")
                previous = session.scalar(select(ChatTurn).where(ChatTurn.user_id == user_id,
                                                                  ChatTurn.request_id == request_id))
                if previous is not None:
                    if previous.user_text != user_text or (conversation_id and previous.conversation_id != conversation_id):
                        raise HTTPException(409, "This request identifier belongs to a different message.")
                    if previous.status == "pending":
                        raise HTTPException(409, "This message is already being processed. Refresh chat history before retrying.")
                    if previous.status == "failed":
                        raise HTTPException(503, "The previous attempt did not complete. It was not automatically retried; review history before sending a new message.")
                    return {**_turn_result(previous, True), "context":[]}

                if conversation_id:
                    conversation = _owner_conversation(session, user_id, conversation_id, lock=True)
                    if conversation.safety_paused:
                        raise HTTPException(409, "This conversation is paused for safety. Review the support options shown with its last response.")
                    if not safety_event and session.scalar(select(ChatTurn.turn_id).where(ChatTurn.conversation_id == conversation_id,
                                                                       ChatTurn.status == "pending").limit(1)):
                        raise HTTPException(409, "A reply is already being prepared in this conversation.")
                else:
                    title = " ".join(user_text.split())[:80]
                    conversation = ChatConversation(user_id=user_id, title=title,
                        consent_version=_text(consent_version, 80, "The consent version"),
                        consent_text=_text(consent_text, 20000, "The consent notice"),
                        provider=_text(provider, 80, "The AI processor"))
                    session.add(conversation)
                    session.flush()

                past = session.scalars(select(ChatTurn).where(ChatTurn.conversation_id == conversation.conversation_id,
                                                              ChatTurn.status == "complete")
                                       .order_by(ChatTurn.created_at.desc(), ChatTurn.turn_id.desc()).limit(3)).all()
                context = []
                # This budget leaves room for the system prompt and resource summaries.
                for turn in reversed(past):
                    context.extend([{"role":"user", "content":turn.user_text[:2000]},
                                    {"role":"assistant", "content":(turn.assistant_text or "")[:2000]}])
                while context and sum(len(item["content"]) for item in context) + len(user_text) > 6000:
                    context = context[2:]
                turn = ChatTurn(user_id=user_id, request_id=request_id,
                                conversation_id=conversation.conversation_id, user_text=user_text,
                                status="pending", sources=[])
                session.add(turn)
                if safety_event:
                    conversation.safety_paused = True
                conversation.updated_at = datetime.now(timezone.utc)
                session.flush()
                return {**_turn_result(turn, False), "context":context}
    except SQLAlchemyError:
        raise HTTPException(503, "Chat history could not be prepared. No automatic provider retry was made.") from None


def finish_turn(user_id, turn_id, reply, sources=None, status="complete", safety_payload=None):
    """Store a result exactly once; crisis results pause the conversation."""
    user_id, turn_id = _uuid(user_id), _uuid(turn_id)
    reply = _text(reply, 12000, "The reply")
    if status not in ("complete", "crisis"):
        raise ValueError("finish_turn status must be complete or crisis")
    if not isinstance(sources or [], list) or len(sources or []) > 10:
        raise ValueError("sources must be a bounded list")
    if safety_payload is not None and not isinstance(safety_payload, dict):
        raise ValueError("safety_payload must be a dictionary")
    if len(json.dumps({"sources":sources or [], "safety":safety_payload}, ensure_ascii=False)) > 20000:
        raise ValueError("Chat metadata is too large")
    try:
        with Session(engine) as session:
            with session.begin():
                turn = session.scalar(select(ChatTurn).where(ChatTurn.turn_id == turn_id,
                                                              ChatTurn.user_id == user_id).with_for_update())
                if turn is None:
                    raise HTTPException(404, "Chat message not found.")
                conversation = _owner_conversation(session, user_id, turn.conversation_id, lock=True)
                if turn.status in ("complete", "crisis"):
                    return _turn_result(turn, True)
                if turn.status != "pending":
                    raise HTTPException(409, "This message attempt has already ended.")
                if conversation.safety_paused and status == "complete":
                    # Caller can mark this attempt failed after handling the
                    # exception; never return the stale ordinary reply.
                    raise HTTPException(409, "The conversation was paused for safety while this reply was being prepared.")
                turn.assistant_text, turn.sources, turn.safety_payload = reply, sources or [], safety_payload
                turn.status = status
                turn.completed_at = datetime.now(timezone.utc)
                conversation.updated_at = turn.completed_at
                if status == "crisis":
                    conversation.safety_paused = True
                session.flush()
                return _turn_result(turn, False)
    except SQLAlchemyError:
        raise HTTPException(503, "The chat result could not be saved. Review history before retrying.") from None


def fail_turn(user_id, turn_id):
    """Record an unsuccessful attempt without saving provider exception details."""
    user_id, turn_id = _uuid(user_id), _uuid(turn_id)
    try:
        with Session(engine) as session:
            with session.begin():
                turn = session.scalar(select(ChatTurn).where(ChatTurn.turn_id == turn_id,
                                                              ChatTurn.user_id == user_id).with_for_update())
                if turn is None:
                    raise HTTPException(404, "Chat message not found.")
                if turn.status == "pending":
                    turn.status = "failed"
                    turn.completed_at = datetime.now(timezone.utc)
                return _turn_result(turn, turn.status != "failed")
    except SQLAlchemyError:
        raise HTTPException(503, "The chat attempt status could not be saved. Review history before retrying.") from None


def latest_support(user_id, conversation_id):
    """Read the latest saved crisis disposition, never another owner's data.

    This is read-only: it does not resume a paused conversation, generate a
    reply, change an alert disposition or send a duplicate notification.
    """
    user_id, conversation_id = _uuid(user_id), _uuid(conversation_id)
    try:
        with Session(engine) as session:
            _owner_conversation(session, user_id, conversation_id)
            turn = session.scalar(select(ChatTurn).where(
                ChatTurn.conversation_id == conversation_id,
                ChatTurn.user_id == user_id,
                ChatTurn.status == "crisis",
            ).order_by(ChatTurn.created_at.desc(), ChatTurn.turn_id.desc()).limit(1))
            return _turn_result(turn, True) if turn is not None else None
    except SQLAlchemyError:
        raise HTTPException(503, "The saved support response is temporarily unavailable.") from None


@router.get("")
def list_conversations(response: Response, limit: int = Query(20, ge=1, le=100),
                       offset: int = Query(0, ge=0), user: AccountResponse = Depends(require_history_consent)):
    try:
        with Session(engine) as session:
            rows = session.scalars(select(ChatConversation).where(ChatConversation.user_id == user.user_id)
                                   .order_by(ChatConversation.updated_at.desc(), ChatConversation.conversation_id.desc())
                                   .offset(offset).limit(limit)).all()
            result = [_summary(row) for row in rows]
    except SQLAlchemyError:
        raise HTTPException(503, "Chat history is temporarily unavailable.") from None
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{conversation_id}")
def read_conversation(conversation_id: UUID, response: Response,
                      limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0),
                      user: AccountResponse = Depends(require_history_consent)):
    try:
        with Session(engine) as session:
            conversation = _owner_conversation(session, user.user_id, conversation_id)
            turns = session.scalars(select(ChatTurn).where(ChatTurn.conversation_id == conversation_id,
                                                           ChatTurn.user_id == user.user_id)
                                    .order_by(ChatTurn.created_at, ChatTurn.turn_id).offset(offset).limit(limit+1)).all()
            has_more = len(turns) > limit
            turns = turns[:limit]
            messages = []
            for turn in turns:
                common = {"turn_id":str(turn.turn_id), "status":turn.status}
                messages.append({**common, "message_id":str(turn.turn_id)+"-user", "role":"user",
                                 "content":turn.user_text, "created_at":turn.created_at, "sources":[], "safety":None})
                if turn.assistant_text is not None:
                    messages.append({**common, "message_id":str(turn.turn_id)+"-assistant", "role":"assistant",
                                     "content":turn.assistant_text, "created_at":turn.completed_at,
                                     "sources":turn.sources or [], "safety":turn.safety_payload})
            result = {**_summary(conversation), "messages":messages,
                      "turn_limit":limit, "turn_offset":offset, "turn_count":len(turns), "has_more":has_more}
    except SQLAlchemyError:
        raise HTTPException(503, "This conversation is temporarily unavailable.") from None
    response.headers["Cache-Control"] = "no-store"
    return result
