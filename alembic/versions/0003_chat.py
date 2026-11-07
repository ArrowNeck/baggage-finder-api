"""Add finder <-> owner chat (conversations and messages)

Revision ID: 0003
Revises: fe366634041e
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "fe366634041e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "baggage_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("baggage_id", sa.Uuid(), nullable=False),
        sa.Column("finder_token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("owner_read_upto_id", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_preview", sa.String(length=100), nullable=True),
        sa.Column("last_message_sender", sa.String(length=6), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["baggage_id"], ["baggages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_baggage_conversations_baggage_id"), "baggage_conversations", ["baggage_id"]
    )
    op.create_index(
        op.f("ix_baggage_conversations_finder_token_hash"),
        "baggage_conversations",
        ["finder_token_hash"],
        unique=True,
    )

    op.create_table(
        "baggage_chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender", sa.String(length=6), nullable=False),
        sa.Column("body", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["baggage_conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_conv_id", "baggage_chat_messages", ["conversation_id", "id"])


def downgrade() -> None:
    op.drop_table("baggage_chat_messages")
    op.drop_table("baggage_conversations")
