import uuid
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Status
from app.models.baggage import Baggage


class DashboardStats(TypedDict):
    active: int
    lost: int
    recovered: int
    recent: list[Baggage]


class DashboardRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard_stats(
        self,
        user_id: uuid.UUID,
        recent_limit: int = 5,
    ) -> DashboardStats:

        stats_query = select(
            func.count(Baggage.id).filter(Baggage.status == Status.active).label("active"),
            func.count(Baggage.id).filter(Baggage.status == Status.lost).label("lost"),
            func.count(Baggage.id).filter(Baggage.status == Status.recovered).label("recovered"),
        ).where(Baggage.user_id == user_id)

        stats_result = await self.db.execute(stats_query)
        stats = stats_result.one()

        recent_query = (
            select(Baggage)
            .where(Baggage.user_id == user_id)
            .order_by(
                Baggage.created_at.desc(),
                Baggage.id.desc(),
            )
            .limit(recent_limit)
        )

        recent_result = await self.db.execute(recent_query)

        recent: list[Baggage] = list(recent_result.scalars().all())

        return {
            "active": stats.active,
            "lost": stats.lost,
            "recovered": stats.recovered,
            "recent": recent,
        }
