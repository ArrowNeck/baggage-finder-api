import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ScanKind, Status
from app.core.exceptions import NotFoundError, RateLimitError
from app.models.baggage import Baggage
from app.models.user import User
from app.repositories.baggage_repository import BaggageRepository
from app.repositories.scan_event_repository import ScanEventRepository
from app.schemas.public import FoundRequest, PublicBaggageResponse, PublicOwner
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PushJob:
    """A notification to send after the HTTP response (see `send_push`)."""

    user_id: uuid.UUID
    token: str | None
    title: str
    body: str
    data: dict[str, str]


class PublicBaggageService:
    """Everything an unauthenticated finder can do with a bag's QR token."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.baggage = BaggageRepository(db)
        self.events = ScanEventRepository(db)

    async def _resolve(self, token_id: str) -> tuple[Baggage, User]:
        found = await self.baggage.get_public_by_token(token_id)
        if found is None:
            raise NotFoundError("Baggage tag")
        return found

    async def view(self, token_id: str) -> PublicBaggageResponse:
        bag, owner = await self._resolve(token_id)
        first_name = (owner.name.split() or ["Owner"])[0][:50]
        reveal_phone = settings.QR_REVEAL_PHONE_WHEN_LOST and bag.status == Status.lost
        return PublicBaggageResponse(
            name=bag.name,
            category=bag.category,
            color=bag.color,
            brand=bag.brand,
            status=bag.status,
            owner=PublicOwner(first_name=first_name, phone=owner.phone if reveal_phone else None),
        )

    async def record_scan(self, token_id: str) -> PushJob | None:
        """The page was opened. At most one push per bag per cooldown window."""
        bag, owner = await self._resolve(token_id)
        if bag.status == Status.recovered:
            return None
        if await self.events.recent_exists(
            bag.id, ScanKind.scan, settings.QR_SCAN_PUSH_COOLDOWN_SECONDS
        ):
            return None

        await self.events.create(baggage_id=bag.id, kind=ScanKind.scan.value)
        await self.db.commit()
        logger.info("Baggage tag scanned", extra={"baggage_id": str(bag.id)})
        return PushJob(
            user_id=owner.id,
            token=owner.fcm_token,
            title="Someone found your bag?",
            body=f"The tag on \u201c{bag.name}\u201d was just scanned.",
            data={"type": "baggage_scanned", "baggage_id": str(bag.id)},
        )

    async def report_found(self, token_id: str, payload: FoundRequest) -> PushJob | None:
        """The finder pressed "Notify owner", optionally with location and a note."""
        bag, owner = await self._resolve(token_id)
        if bag.status == Status.recovered:
            return None
        if await self.events.recent_exists(
            bag.id, ScanKind.found, settings.QR_FOUND_COOLDOWN_SECONDS
        ):
            raise RateLimitError(retry_after=settings.QR_FOUND_COOLDOWN_SECONDS)

        has_location = payload.latitude is not None and payload.longitude is not None
        note = payload.message or None
        contact = payload.contact or None
        event = await self.events.create(
            baggage_id=bag.id,
            kind=ScanKind.found.value,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_m=payload.accuracy,
            message=note,
            contact=contact,
        )
        await self.db.commit()
        logger.info(
            "Baggage reported found",
            extra={"baggage_id": str(bag.id), "with_location": has_location},
        )

        body = f"Someone found \u201c{bag.name}\u201d"
        body += " and shared their location." if has_location else "."
        if note:
            body += f" Note: {note[:100]}"
        if contact:
            body += f" Contact: {contact}"

        data = {"type": "baggage_found", "baggage_id": str(bag.id), "event_id": str(event.id)}
        if has_location:
            data["latitude"] = f"{payload.latitude:.6f}"
            data["longitude"] = f"{payload.longitude:.6f}"
            data["maps_url"] = (
                f"https://www.google.com/maps?q={payload.latitude:.6f},{payload.longitude:.6f}"
            )
        return PushJob(owner.id, owner.fcm_token, "Your bag was found!", body, data)
