import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.core.enums import Category, Status
from app.core.routes import BaggageRoutes
from app.schemas.baggage import (
    BaggageCreate,
    BaggageResponse,
    BaggageStatusUpdate,
    BaggageUpdate,
)
from app.schemas.common import Page
from app.schemas.public import ScanEventResponse
from app.services.baggage_service import BaggageService

router = APIRouter(prefix=BaggageRoutes.PREFIX, tags=["Baggage"])


@router.post("", response_model=BaggageResponse, status_code=status.HTTP_201_CREATED)
async def create_baggage(
    payload: BaggageCreate, current_user: CurrentUser, db: DB
) -> BaggageResponse:
    """Create baggage owned by the authenticated user (token_id is generated server-side)."""
    return await BaggageService(db).create(current_user, payload)


@router.get("", response_model=Page[BaggageResponse])
async def list_baggage(
    current_user: CurrentUser,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Status | None = None,
    category: Category | None = None,
) -> Page[BaggageResponse]:
    """List your baggage, newest first. Optional filters: status, category."""
    return await BaggageService(db).list_for_user(
        current_user, page=page, limit=limit, status=status, category=category
    )


@router.get(BaggageRoutes.BY_ID, response_model=BaggageResponse)
async def get_baggage(baggage_id: uuid.UUID, current_user: CurrentUser, db: DB) -> BaggageResponse:
    return await BaggageService(db).get(current_user, baggage_id)


@router.patch(BaggageRoutes.BY_ID, response_model=BaggageResponse)
async def update_baggage(
    baggage_id: uuid.UUID, payload: BaggageUpdate, current_user: CurrentUser, db: DB
) -> BaggageResponse:
    """Partial update: only the fields sent are changed."""
    return await BaggageService(db).update(current_user, baggage_id, payload)


@router.patch(BaggageRoutes.STATUS, response_model=BaggageResponse)
async def change_baggage_status(
    baggage_id: uuid.UUID, payload: BaggageStatusUpdate, current_user: CurrentUser, db: DB
) -> BaggageResponse:
    return await BaggageService(db).change_status(current_user, baggage_id, payload.status)


@router.delete(BaggageRoutes.BY_ID, status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_baggage(baggage_id: uuid.UUID, current_user: CurrentUser, db: DB) -> Response:
    await BaggageService(db).delete(current_user, baggage_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(BaggageRoutes.EVENTS, response_model=list[ScanEventResponse])
async def list_baggage_events(
    baggage_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ScanEventResponse]:
    """When your tag was scanned and where finders reported it (newest first)."""
    return await BaggageService(db).list_events(current_user, baggage_id, limit)
