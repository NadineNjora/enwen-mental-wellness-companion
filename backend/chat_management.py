"""Owner-only conversation names and deliberate removal from the active database.

No AI, email or SMS transport is called here. Content-free request identifiers
remain so a stale message retry cannot recreate deleted text or repeat an alert.
Existing notification dispositions are separate records and are preserved.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from authentication import AccountResponse, get_current_user
from chat_history import _owner_conversation, _summary, require_history_consent
from chat_history_models import ChatConversation, ChatTurn, DeletedChatRequest
from database import engine
from models import User

router = APIRouter(prefix="/chat/conversations", tags=["Private chat history"])


class ConversationName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: StrictStr = Field(min_length=1, max_length=80)


@router.patch("/{conversation_id}")
def rename_conversation(conversation_id: UUID, data: ConversationName, response: Response,
                        user: AccountResponse = Depends(require_history_consent)):
    title = " ".join(data.title.split())
    if not title or any(ord(character) < 32 or ord(character) == 127 for character in title):
        raise HTTPException(422, "Choose a conversation name between 1 and 80 characters.")
    try:
        with Session(engine) as session, session.begin():
            conversation = _owner_conversation(session, user.user_id, conversation_id, lock=True)
            conversation.title = title
            session.flush()
            result = _summary(conversation)
    except SQLAlchemyError:
        raise HTTPException(503, "The name could not be confirmed. Refresh history before trying again.") from None
    response.headers["Cache-Control"] = "no-store"
    return result


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, user: AccountResponse = Depends(get_current_user)):
    # Access to deletion does not depend on agreeing to further AI processing.
    try:
        with Session(engine) as session, session.begin():
            # claim_turn takes this same account lock before claiming any new
            # work. Lock turns before the conversation, matching finish_turn;
            # holding the conversation first could deadlock a finishing reply.
            if session.scalar(select(User.user_id).where(User.user_id == user.user_id).with_for_update()) is None:
                raise HTTPException(401, "Please log in again.")
            _owner_conversation(session, user.user_id, conversation_id)
            turns = session.scalars(select(ChatTurn).where(
                ChatTurn.conversation_id == conversation_id, ChatTurn.user_id == user.user_id,
            ).order_by(ChatTurn.turn_id).with_for_update()).all()
            conversation = _owner_conversation(session, user.user_id, conversation_id, lock=True)
            if any(turn.status == "pending" for turn in turns):
                raise HTTPException(409, "A message is still being processed. Refresh this conversation after it finishes before deleting it.")
            session.add_all(DeletedChatRequest(user_id=user.user_id, request_id=turn.request_id) for turn in turns)
            session.flush()
            session.execute(delete(ChatTurn).where(ChatTurn.conversation_id == conversation_id,
                                                   ChatTurn.user_id == user.user_id))
            session.delete(conversation)
    except SQLAlchemyError:
        raise HTTPException(503, "Deletion could not be confirmed. Refresh history before trying again; nothing was automatically retried.") from None
    return Response(status_code=204, headers={"Cache-Control":"no-store"})
