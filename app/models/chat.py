import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.types import UTCDateTime
from app.utils.helpers import utcnow


class Conversation(Base):
    """One finder <-> owner chat about one bag.

    The finder has no account. Their only credential is a random chat token kept in
    their browser; only its SHA-256 digest is stored here.
    """

    __tablename__ = "baggage_conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    baggage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("baggages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    finder_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(10), default="open", nullable=False)

    # Highest message id the owner has read (unread = finder messages with a larger id).
    owner_read_upto_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Denormalised for the inbox list, so listing needs no per-conversation query.
    last_message_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_message_preview: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_message_sender: Mapped[str | None] = mapped_column(String(6), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, server_default=func.now(), nullable=False
    )


class ChatMessage(Base):
    __tablename__ = "baggage_chat_messages"
    __table_args__ = (Index("ix_chat_messages_conv_id", "conversation_id", "id"),)

    # Sequential ids double as the polling cursor ("give me messages after id N").
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("baggage_conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender: Mapped[str] = mapped_column(String(6), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, server_default=func.now(), nullable=False
    )
