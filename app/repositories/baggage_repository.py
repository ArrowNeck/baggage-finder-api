import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Category, Status
from app.models.baggage import Baggage


class BaggageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_owned(self, baggage_id: uuid.UUID, user_id: uuid.UUID) -> Baggage | None:
        """Ownership is part of the query, so another user's record is simply 'not found'."""
        result = await self.db.execute(
            select(Baggage).where(Baggage.id == baggage_id, Baggage.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        page: int,
        limit: int,
        status: Status | None = None,
        category: Category | None = None,
    ) -> tuple[list[Baggage], int]:
        conditions = [Baggage.user_id == user_id]
        if status is not None:
            conditions.append(Baggage.status == status)
        if category is not None:
            conditions.append(Baggage.category == category)

        total = (
            await self.db.execute(select(func.count()).select_from(Baggage).where(*conditions))
        ).scalar_one()
        rows = await self.db.execute(
            select(Baggage)
            .where(*conditions)
            .order_by(Baggage.created_at.desc(), Baggage.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(rows.scalars().all()), total

    async def create(self, **kwargs: object) -> Baggage:
        baggage = Baggage(**kwargs)
        self.db.add(baggage)
        await self.db.flush()
        return baggage

    async def update(self, baggage: Baggage, **changes: object) -> Baggage:
        for field, value in changes.items():
            setattr(baggage, field, value)
        await self.db.flush()
        return baggage

    async def delete(self, baggage: Baggage) -> None:
        await self.db.delete(baggage)
        await self.db.flush()
