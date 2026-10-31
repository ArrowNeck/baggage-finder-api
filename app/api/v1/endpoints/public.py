from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Response, status

from app.api.deps import DB
from app.core.rate_limit import RateLimit
from app.core.routes import PublicRoutes
from app.schemas.public import FoundRequest, PublicActionResponse, PublicBaggageResponse
from app.services.public_service import PublicBaggageService
from app.services.push_service import send_push

# No authentication: the unguessable token in the QR code is the only credential,
# and it only unlocks the limited view defined in PublicBaggageResponse.
router = APIRouter(prefix=PublicRoutes.PREFIX, tags=["Public QR"])

TokenId = Annotated[str, Path(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_\-]+$")]


@router.get(
    PublicRoutes.BY_TOKEN,
    response_model=PublicBaggageResponse,
    dependencies=[Depends(RateLimit("qr-view", per_minute=60))],
)
async def view_tag(token_id: TokenId, response: Response, db: DB) -> PublicBaggageResponse:
    """Basic bag info and the owner's first name, for the QR landing page."""
    response.headers["Cache-Control"] = "no-store"
    return await PublicBaggageService(db).view(token_id)


@router.post(
    PublicRoutes.SCAN,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublicActionResponse,
    dependencies=[Depends(RateLimit("qr-scan", per_minute=30))],
)
async def record_scan(
    token_id: TokenId, background: BackgroundTasks, db: DB
) -> PublicActionResponse:
    """Called by the page's JavaScript on load (not by the HTML GET, so link-preview
    bots and crawlers don't trigger it). Notifies the owner, at most once per cooldown."""
    job = await PublicBaggageService(db).record_scan(token_id)
    if job and job.token:
        background.add_task(send_push, job.user_id, job.token, job.title, job.body, job.data)
    return PublicActionResponse(message="Recorded")


@router.post(
    PublicRoutes.FOUND,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublicActionResponse,
    dependencies=[Depends(RateLimit("qr-found", per_minute=10))],
)
async def report_found(
    token_id: TokenId, payload: FoundRequest, background: BackgroundTasks, db: DB
) -> PublicActionResponse:
    """The finder pressed "Notify owner" (location, note and contact are all optional)."""
    job = await PublicBaggageService(db).report_found(token_id, payload)
    if job and job.token:
        background.add_task(send_push, job.user_id, job.token, job.title, job.body, job.data)
    return PublicActionResponse(message="The owner has been notified")
