"""Add baggage_scan_events (QR page scans and finder reports)

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "baggage_scan_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("baggage_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("message", sa.String(length=280), nullable=True),
        sa.Column("contact", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["baggage_id"], ["baggages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scan_events_baggage_kind_created",
        "baggage_scan_events",
        ["baggage_id", "kind", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("baggage_scan_events")
