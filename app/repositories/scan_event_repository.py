import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ScanKind
from app.models.scan_event import BaggageScanEvent
from app.utils.helpers import utcnow


class ScanEventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, **kwargs: object) -> BaggageScanEvent:
        event = BaggageScanEvent(**kwargs)
        self.db.add(event)
        await self.db.flush()
        return event

    async def recent_exists(
        self, baggage_id: uuid.UUID, kind: ScanKind, within_seconds: int
    ) -> bool:
        since = utcnow() - timedelta(seconds=within_seconds)
        result = await self.db.execute(
            select(BaggageScanEvent.id)
            .where(
                BaggageScanEvent.baggage_id == baggage_id,
                BaggageScanEvent.kind == kind.value,
                BaggageScanEvent.created_at >= since,
            )
            .limit(1)
        )
        return result.first() is not None

    async def list_for_baggage(self, baggage_id: uuid.UUID, limit: int) -> list[BaggageScanEvent]:
        result = await self.db.execute(
            select(BaggageScanEvent)
            .where(BaggageScanEvent.baggage_id == baggage_id)
            .order_by(BaggageScanEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
