import uuid

from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import DashboardResponse


class DashboardService:
    def __init__(
        self,
        dashboard_repository: DashboardRepository,
    ) -> None:
        self.dashboard_repository = dashboard_repository

    async def get_dashboard(
        self,
        user_id: uuid.UUID,
    ) -> DashboardResponse:
        data = await self.dashboard_repository.get_dashboard_stats(
            user_id=user_id,
        )

        return DashboardResponse.model_validate(data)
