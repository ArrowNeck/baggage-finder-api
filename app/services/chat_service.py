import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ChatSender, ConversationStatus, Status
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)
from app.core.security import generate_opaque_token, hash_token
from app.models.baggage import Baggage
from app.models.chat import ChatMessage, Conversation
from app.models.user import User
from app.repositories.baggage_repository import BaggageRepository
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import ChatMessageResponse, ChatPageResponse, ConversationResponse
from app.services import realtime_service
from app.services.public_service import PushJob
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Anonymous finders can't be trusted not to spam, so the limits live in the database.
FINDER_MESSAGES_PER_MINUTE = 10
NEW_CONVERSATIONS_PER_BAG_PER_HOUR = 10
PAGE_SIZE = 100


def _closed_error() -> ConflictError:
    return ConflictError("This conversation is closed", code="CHAT_CLOSED")


def _is_closed(conversation: Conversation, bag: Baggage) -> bool:
    return conversation.status == ConversationStatus.closed.value or bag.status == Status.recovered


def _page(messages: list[ChatMessage], closed: bool) -> ChatPageResponse:
    return ChatPageResponse(
        messages=[ChatMessageResponse.model_validate(m) for m in messages], closed=closed
    )


class FinderChatService:
    """Chat as seen by the anonymous finder. Credential: the X-Chat-Token header."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.baggage = BaggageRepository(db)
        self.chats = ChatRepository(db)

    async def _resolve_bag(self, token_id: str) -> tuple[Baggage, User]:
        found = await self.baggage.get_public_by_token(token_id)
        if found is None:
            raise NotFoundError("Baggage tag")
        return found

    async def _conversation_for(self, bag: Baggage, chat_token: str) -> Conversation:
        conversation = await self.chats.get_by_finder_hash(hash_token(chat_token))
        # The token must belong to *this* bag: it can't be replayed on another tag.
        if conversation is None or conversation.baggage_id != bag.id:
            raise AuthenticationError("Invalid chat session", code="INVALID_CHAT_TOKEN")
        return conversation

    async def authenticate(self, token_id: str, chat_token: str) -> uuid.UUID:
        """Conversation id for a valid (tag, chat token) pair; raises otherwise."""
        bag, _ = await self._resolve_bag(token_id)
        conversation = await self._conversation_for(bag, chat_token)
        return conversation.id

    async def realtime_session(self, token_id: str, chat_token: str | None) -> dict[str, str]:
        """Firebase sign-in details, only for someone who owns this conversation's chat token."""
        if not chat_token:
            raise AuthenticationError("Invalid chat session", code="INVALID_CHAT_TOKEN")
        if not realtime_service.realtime_enabled():
            raise realtime_service.RealtimeUnavailable()
        conversation_id = await self.authenticate(token_id, chat_token)
        return await realtime_service.finder_session(conversation_id)

    async def send(
        self, token_id: str, chat_token: str | None, text: str
    ) -> tuple[ChatMessage, str | None, PushJob]:
        """Returns (message, new_chat_token_or_None, push_for_owner)."""
        bag, owner = await self._resolve_bag(token_id)
        if bag.status == Status.recovered:
            raise _closed_error()

        new_token: str | None = None
        if chat_token:
            conversation = await self._conversation_for(bag, chat_token)
            if conversation.status == ConversationStatus.closed.value:
                raise _closed_error()
        else:
            recent = await self.chats.count_new_conversations(bag.id, 3600)
            if recent >= NEW_CONVERSATIONS_PER_BAG_PER_HOUR:
                raise RateLimitError(retry_after=3600)
            new_token, digest = generate_opaque_token()
            conversation = await self.chats.create_conversation(bag.id, digest)

        sent_last_minute = await self.chats.count_recent_finder_messages(conversation.id, 60)
        if sent_last_minute >= FINDER_MESSAGES_PER_MINUTE:
            raise RateLimitError(retry_after=60)

        message = await self.chats.add_message(conversation, ChatSender.finder, text)
        await self.db.commit()
        logger.info("Finder chat message", extra={"conversation_id": str(conversation.id)})
        await realtime_service.publish_conversation(
            conversation.id, owner.id, bag.id, message_id=message.id, sender="finder"
        )

        # Every finder message pushes. The push is only a wake-up: the app then loads what it
        # is missing from the server, so a lost, late or duplicated push can't corrupt the chat.
        push = PushJob(
            user_id=owner.id,
            token=owner.fcm_token,
            title=f"Message about \u201c{bag.name}\u201d",
            body=text[:100],
            data={
                "type": "chat_message",
                "conversation_id": str(conversation.id),
                "baggage_id": str(bag.id),
                "message_id": str(message.id),
                "sender": "finder",
                "preview": text[:100],
            },
            thread=str(conversation.id),  # groups the notifications of one conversation
            data_only=settings.PUSH_CHAT_DATA_ONLY,
        )
        return message, new_token, push

    async def messages(self, token_id: str, chat_token: str | None, after: int) -> ChatPageResponse:
        bag, _ = await self._resolve_bag(token_id)
        if not chat_token:
            raise AuthenticationError("Invalid chat session", code="INVALID_CHAT_TOKEN")
        conversation = await self._conversation_for(bag, chat_token)
        messages = await self.chats.list_messages(conversation.id, after, PAGE_SIZE)
        return _page(messages, _is_closed(conversation, bag))


class OwnerChatService:
    """Chat as seen by the authenticated owner (mobile app)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.chats = ChatRepository(db)

    async def _owned(self, user: User, conversation_id: uuid.UUID) -> tuple[Conversation, Baggage]:
        found = await self.chats.get_owned(conversation_id, user.id)
        if found is None:
            raise NotFoundError("Conversation", str(conversation_id))
        return found

    async def list_conversations(
        self,
        user: User,
        baggage_id: uuid.UUID | None,
        status: ConversationStatus | None,
    ) -> list[ConversationResponse]:
        rows = await self.chats.list_for_owner(user.id, baggage_id, status)
        return [
            ConversationResponse(
                id=c.id,
                baggage_id=c.baggage_id,
                baggage_name=name,
                status=c.status,
                last_message=c.last_message_preview,
                last_message_sender=c.last_message_sender,
                last_message_at=c.last_message_at,
                unread_count=unread,
                created_at=c.created_at,
            )
            for c, name, unread in rows
        ]

    async def messages(
        self, user: User, conversation_id: uuid.UUID, after: int, limit: int
    ) -> ChatPageResponse:
        conversation, bag = await self._owned(user, conversation_id)
        messages = await self.chats.list_messages(conversation.id, after, limit)
        return _page(messages, _is_closed(conversation, bag))

    async def send(self, user: User, conversation_id: uuid.UUID, text: str) -> ChatMessageResponse:
        conversation, bag = await self._owned(user, conversation_id)
        if _is_closed(conversation, bag):
            raise _closed_error()
        message = await self.chats.add_message(conversation, ChatSender.owner, text)
        await self.db.commit()
        await realtime_service.publish_conversation(
            conversation.id, user.id, bag.id, message_id=message.id, sender="owner"
        )
        return ChatMessageResponse.model_validate(message)

    async def mark_read(self, user: User, conversation_id: uuid.UUID) -> None:
        conversation, _ = await self._owned(user, conversation_id)
        await self.chats.mark_read(conversation)
        await self.db.commit()

    async def close(self, user: User, conversation_id: uuid.UUID) -> None:
        """Stops the finder from sending more (use against spam or when the bag is back)."""
        conversation, bag = await self._owned(user, conversation_id)
        await self.chats.set_status(conversation, ConversationStatus.closed)
        await self.db.commit()
        await realtime_service.publish_conversation(conversation.id, user.id, bag.id, closed=True)
