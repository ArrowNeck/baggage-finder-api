import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ChatSender, ConversationStatus
from app.models.baggage import Baggage
from app.models.chat import ChatMessage, Conversation
from app.utils.helpers import utcnow


class ChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Finder side ─────────────────────────────────────────────────────────
    async def get_by_finder_hash(self, token_hash: str) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation).where(Conversation.finder_token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def create_conversation(
        self, baggage_id: uuid.UUID, finder_token_hash: str
    ) -> Conversation:
        conversation = Conversation(
            baggage_id=baggage_id,
            finder_token_hash=finder_token_hash,
            status=ConversationStatus.open.value,
        )
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def count_new_conversations(self, baggage_id: uuid.UUID, within_seconds: int) -> int:
        since = utcnow() - timedelta(seconds=within_seconds)
        result = await self.db.execute(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.baggage_id == baggage_id, Conversation.created_at >= since)
        )
        return result.scalar_one()

    async def count_recent_finder_messages(
        self, conversation_id: uuid.UUID, within_seconds: int
    ) -> int:
        since = utcnow() - timedelta(seconds=within_seconds)
        result = await self.db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.conversation_id == conversation_id,
                ChatMessage.sender == ChatSender.finder.value,
                ChatMessage.created_at >= since,
            )
        )
        return result.scalar_one()

    # ── Shared ──────────────────────────────────────────────────────────────
    async def add_message(
        self, conversation: Conversation, sender: ChatSender, body: str
    ) -> ChatMessage:
        # Lock the conversation row first. Concurrent senders then commit in id order, so a
        # reader that has seen message N can never miss a message with a smaller id.
        await self.db.execute(
            select(Conversation.id).where(Conversation.id == conversation.id).with_for_update()
        )
        message = ChatMessage(conversation_id=conversation.id, sender=sender.value, body=body)
        self.db.add(message)
        conversation.last_message_at = utcnow()
        conversation.last_message_preview = body[:100]
        conversation.last_message_sender = sender.value
        await self.db.flush()
        return message

    async def list_messages(
        self, conversation_id: uuid.UUID, after: int, limit: int
    ) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id, ChatMessage.id > after)
            .order_by(ChatMessage.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Owner side ──────────────────────────────────────────────────────────
    async def get_owned(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Conversation, Baggage] | None:
        """Ownership comes from the bag: other users' conversations are 'not found'."""
        result = await self.db.execute(
            select(Conversation, Baggage)
            .join(Baggage, Baggage.id == Conversation.baggage_id)
            .where(Conversation.id == conversation_id, Baggage.user_id == user_id)
        )
        row = result.first()
        return (row[0], row[1]) if row else None

    async def list_for_owner(
        self,
        user_id: uuid.UUID,
        baggage_id: uuid.UUID | None,
        status: ConversationStatus | None,
    ) -> list[tuple[Conversation, str, int]]:
        unread = (
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.conversation_id == Conversation.id,
                ChatMessage.sender == ChatSender.finder.value,
                ChatMessage.id > Conversation.owner_read_upto_id,
            )
            .correlate(Conversation)
            .scalar_subquery()
        )
        query = (
            select(Conversation, Baggage.name, unread)
            .join(Baggage, Baggage.id == Conversation.baggage_id)
            .where(Baggage.user_id == user_id)
            .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
        )
        if baggage_id is not None:
            query = query.where(Conversation.baggage_id == baggage_id)
        if status is not None:
            query = query.where(Conversation.status == status.value)
        rows = await self.db.execute(query)
        return [(c, name, count) for c, name, count in rows.all()]

    async def list_ids_for_baggage(self, baggage_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self.db.execute(
            select(Conversation.id).where(Conversation.baggage_id == baggage_id)
        )
        return list(result.scalars().all())

    async def mark_read(self, conversation: Conversation) -> None:
        latest = (
            await self.db.execute(
                select(func.max(ChatMessage.id)).where(
                    ChatMessage.conversation_id == conversation.id
                )
            )
        ).scalar_one_or_none() or 0
        conversation.owner_read_upto_id = max(conversation.owner_read_upto_id, latest)
        await self.db.flush()

    async def set_status(self, conversation: Conversation, status: ConversationStatus) -> None:
        conversation.status = status.value
        await self.db.flush()
