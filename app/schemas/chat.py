import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.core.base_schemas import BaseResponse, BaseSchema
from app.core.enums import ChatSender, ConversationStatus

MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class ChatSendRequest(BaseSchema):
    message: MessageText


class ChatMessageResponse(BaseResponse):
    id: int
    sender: ChatSender
    body: str
    created_at: datetime


class ChatPageResponse(BaseModel):
    messages: list[ChatMessageResponse]
    closed: bool  # no more messages can be sent (owner closed it, or the bag was recovered)


class FinderSendResponse(BaseModel):
    chat_token: str | None = None  # only on the first message; the browser must keep it
    message: ChatMessageResponse


class ConversationResponse(BaseModel):
    id: uuid.UUID
    baggage_id: uuid.UUID
    baggage_name: str
    status: ConversationStatus
    last_message: str | None = None
    last_message_sender: ChatSender | None = None
    last_message_at: datetime | None = None
    unread_count: int
    created_at: datetime


class FinderRealtimeSession(BaseModel):
    """Everything the QR page needs to listen to its conversation in Firebase."""

    custom_token: str
    project_id: str
    api_key: str
    auth_domain: str
    sdk_version: str
    conversation_id: str


class OwnerRealtimeSession(BaseModel):
    custom_token: str
    project_id: str
    api_key: str
    auth_domain: str
    owner_uid: str  # the Firestore field `ownerUid` to filter conversations by
    collection: str
