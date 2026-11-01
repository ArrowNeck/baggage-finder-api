from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.routes import DashboardRoutes
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix=DashboardRoutes.PREFIX, tags=["Dashboard"])


@router.get(DashboardRoutes.STATS, response_model=DashboardResponse)
async def get_dashboard(current_user: CurrentUser, db: DB) -> DashboardResponse:
    return await DashboardService(dashboard_repository=DashboardRepository(db)).get_dashboard(
        user_id=current_user.id
    )
