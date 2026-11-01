import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Category, Status
from app.core.exceptions import NotFoundError
from app.models.baggage import Baggage
from app.models.user import User
from app.repositories.baggage_repository import BaggageRepository
from app.repositories.scan_event_repository import ScanEventRepository
from app.schemas.baggage import BaggageCreate, BaggageResponse, BaggageUpdate
from app.schemas.common import Page
from app.schemas.public import ScanEventResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate_token_id() -> str:
    """Unguessable tracking token (safe to print in a QR code)."""
    return "bag_" + secrets.token_urlsafe(24)


class BaggageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = BaggageRepository(db)
        self.events = ScanEventRepository(db)

    async def _get_owned(self, user: User, baggage_id: uuid.UUID) -> Baggage:
        baggage = await self.repo.get_owned(baggage_id, user.id)
        if baggage is None:
            raise NotFoundError("Baggage", str(baggage_id))
        return baggage

    async def create(self, user: User, payload: BaggageCreate) -> BaggageResponse:
        baggage = await self.repo.create(
            user_id=user.id,  # always the authenticated user, never client-supplied
            token_id=generate_token_id(),
            name=payload.name,
            category=payload.category,
            color=payload.color,
            brand=payload.brand,
            status=Status.active,
            remarks=payload.remarks,
        )
        await self.db.commit()
        logger.info("Baggage created", extra={"baggage_id": str(baggage.id)})
        return BaggageResponse.model_validate(baggage)

    async def list_for_user(
        self,
        user: User,
        *,
        page: int,
        limit: int,
        status: Status | None,
        category: Category | None,
    ) -> Page[BaggageResponse]:
        items, total = await self.repo.list_for_user(
            user.id, page=page, limit=limit, status=status, category=category
        )
        return Page[BaggageResponse](
            items=[BaggageResponse.model_validate(i) for i in items],
            page=page,
            limit=limit,
            total=total,
        )

    async def get(self, user: User, baggage_id: uuid.UUID) -> BaggageResponse:
        return BaggageResponse.model_validate(await self._get_owned(user, baggage_id))

    async def update(
        self, user: User, baggage_id: uuid.UUID, payload: BaggageUpdate
    ) -> BaggageResponse:
        baggage = await self._get_owned(user, baggage_id)
        changes = payload.model_dump(exclude_unset=True)
        await self.repo.update(baggage, **changes)
        await self.db.commit()
        logger.info(
            "Baggage updated", extra={"baggage_id": str(baggage.id), "fields": list(changes)}
        )
        return BaggageResponse.model_validate(baggage)

    async def change_status(
        self, user: User, baggage_id: uuid.UUID, status: Status
    ) -> BaggageResponse:
        baggage = await self._get_owned(user, baggage_id)
        await self.repo.update(baggage, status=status)
        await self.db.commit()
        logger.info(
            "Baggage status changed", extra={"baggage_id": str(baggage.id), "status": status}
        )
        return BaggageResponse.model_validate(baggage)

    async def delete(self, user: User, baggage_id: uuid.UUID) -> None:
        baggage = await self._get_owned(user, baggage_id)
        await self.repo.delete(baggage)
        await self.db.commit()
        logger.info("Baggage deleted", extra={"baggage_id": str(baggage_id)})

    async def list_events(
        self, user: User, baggage_id: uuid.UUID, limit: int
    ) -> list[ScanEventResponse]:
        """Scans and finder reports (with locations) for one of your bags, newest first."""
        baggage = await self._get_owned(user, baggage_id)
        events = await self.events.list_for_baggage(baggage.id, limit)
        return [ScanEventResponse.model_validate(e) for e in events]
