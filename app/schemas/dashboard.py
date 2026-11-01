from datetime import datetime
from uuid import UUID

from app.core.base_schemas import BaseResponse
from app.core.enums import Category, Status
from app.core.types import HexColor


class DashboardBaggageResponse(BaseResponse):
    id: UUID
    name: str
    brand: str | None = None
    category: Category
    color: HexColor
    status: Status
    created_at: datetime


class DashboardResponse(BaseResponse):
    active: int
    lost: int
    recovered: int
    recent: list[DashboardBaggageResponse]
