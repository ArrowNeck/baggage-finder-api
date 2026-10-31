import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.types import UTCDateTime
from app.utils.helpers import utcnow


class BaggageScanEvent(Base):
    """One visit to a bag's QR page ("scan") or one finder report ("found").

    Also serves as the cooldown ledger, so throttling survives restarts and
    works across several app instances without Redis.
    """

    __tablename__ = "baggage_scan_events"
    __table_args__ = (
        Index("ix_scan_events_baggage_kind_created", "baggage_id", "kind", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    baggage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("baggages.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)

    # Only set on "found" reports where the finder chose to share their location.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    message: Mapped[str | None] = mapped_column(String(280), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, server_default=func.now(), nullable=False
    )
