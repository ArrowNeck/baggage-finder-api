import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.core.enums import ConversationStatus
from app.core.routes import ChatRoutes
from app.schemas.chat import (
    ChatMessageResponse,
    ChatPageResponse,
    ChatSendRequest,
    ConversationResponse,
)
from app.services.chat_service import OwnerChatService

router = APIRouter(prefix=ChatRoutes.PREFIX, tags=["Chat (owner)"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: CurrentUser,
    db: DB,
    baggage_id: uuid.UUID | None = None,
    status: ConversationStatus | None = None,
) -> list[ConversationResponse]:
    """Your inbox: every finder conversation, newest activity first, with unread counts."""
    return await OwnerChatService(db).list_conversations(current_user, baggage_id, status)


@router.get(ChatRoutes.MESSAGES, response_model=ChatPageResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> ChatPageResponse:
    """Messages with id > `after` (oldest first). Poll with the last id you have."""
    return await OwnerChatService(db).messages(current_user, conversation_id, after, limit)


@router.post(
    ChatRoutes.MESSAGES, response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED
)
async def send_message(
    conversation_id: uuid.UUID, payload: ChatSendRequest, current_user: CurrentUser, db: DB
) -> ChatMessageResponse:
    return await OwnerChatService(db).send(current_user, conversation_id, payload.message)


@router.post(ChatRoutes.READ, status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def mark_read(conversation_id: uuid.UUID, current_user: CurrentUser, db: DB) -> Response:
    """Mark everything received so far as read (clears the unread badge)."""
    await OwnerChatService(db).mark_read(current_user, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(ChatRoutes.CLOSE, status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def close_conversation(
    conversation_id: uuid.UUID, current_user: CurrentUser, db: DB
) -> Response:
    """Close the conversation; the finder can no longer send messages."""
    await OwnerChatService(db).close(current_user, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
