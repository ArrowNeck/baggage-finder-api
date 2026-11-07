from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Response, status

from app.api.deps import DB
from app.core.rate_limit import RateLimit
from app.core.routes import PublicRoutes
from app.schemas.chat import (
    ChatMessageResponse,
    ChatPageResponse,
    ChatSendRequest,
    FinderRealtimeSession,
    FinderSendResponse,
)
from app.schemas.public import FoundRequest, PublicActionResponse, PublicBaggageResponse
from app.services.chat_service import FinderChatService
from app.services.public_service import PublicBaggageService
from app.services.push_service import send_push

# No authentication: the unguessable token in the QR code is the only credential,
# and it only unlocks the limited view defined in PublicBaggageResponse.
router = APIRouter(prefix=PublicRoutes.PREFIX, tags=["Public QR"])

TokenId = Annotated[str, Path(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_\-]+$")]
# Credential of an anonymous finder's chat session (returned with their first message).
ChatToken = Annotated[str | None, Header(alias="X-Chat-Token", max_length=256)]


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
async def record_scan(token_id: TokenId, db: DB) -> PublicActionResponse:
    """Called by the page's JavaScript on load (not by the HTML GET, so link-preview
    bots and crawlers don't trigger it). Notifies the owner, at most once per cooldown."""
    job = await PublicBaggageService(db).record_scan(token_id)
    if job and job.token:
        # Awaited *before* responding. Serverless hosts (Vercel) may freeze the process as
        # soon as the response is sent, which silently drops a BackgroundTasks push.
        await send_push(
            job.user_id,
            job.token,
            job.title,
            job.body,
            job.data,
            thread=job.thread,
            data_only=job.data_only,
        )
    return PublicActionResponse(message="Recorded")


@router.post(
    PublicRoutes.FOUND,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PublicActionResponse,
    dependencies=[Depends(RateLimit("qr-found", per_minute=10))],
)
async def report_found(token_id: TokenId, payload: FoundRequest, db: DB) -> PublicActionResponse:
    """The finder pressed "Notify owner" (location, note and contact are all optional)."""
    job = await PublicBaggageService(db).report_found(token_id, payload)
    if job and job.token:
        await send_push(
            job.user_id,
            job.token,
            job.title,
            job.body,
            job.data,
            thread=job.thread,
            data_only=job.data_only,
        )
    return PublicActionResponse(message="The owner has been notified")


@router.post(
    PublicRoutes.CHAT_MESSAGES,
    status_code=status.HTTP_201_CREATED,
    response_model=FinderSendResponse,
    dependencies=[Depends(RateLimit("qr-chat-send", per_minute=30))],
)
async def finder_send_message(
    token_id: TokenId,
    payload: ChatSendRequest,
    db: DB,
    chat_token: ChatToken = None,
) -> FinderSendResponse:
    """Finder -> owner. Without X-Chat-Token this starts a conversation and returns a
    `chat_token` that the browser must keep and send with every later request."""
    message, new_token, job = await FinderChatService(db).send(
        token_id, chat_token, payload.message
    )
    if job and job.token:
        await send_push(
            job.user_id,
            job.token,
            job.title,
            job.body,
            job.data,
            thread=job.thread,
            data_only=job.data_only,
        )
    return FinderSendResponse(
        chat_token=new_token, message=ChatMessageResponse.model_validate(message)
    )


@router.get(
    PublicRoutes.CHAT_MESSAGES,
    response_model=ChatPageResponse,
    dependencies=[Depends(RateLimit("qr-chat-poll", per_minute=90))],
)
async def finder_list_messages(
    token_id: TokenId,
    response: Response,
    db: DB,
    chat_token: ChatToken = None,
    after: Annotated[int, Query(ge=0)] = 0,
) -> ChatPageResponse:
    """Messages with id > `after`. The page polls this every few seconds."""
    response.headers["Cache-Control"] = "no-store"
    return await FinderChatService(db).messages(token_id, chat_token, after)


@router.post(
    PublicRoutes.CHAT_REALTIME,
    response_model=FinderRealtimeSession,
    dependencies=[Depends(RateLimit("qr-chat-rt", per_minute=20))],
)
async def finder_realtime_session(
    token_id: TokenId, response: Response, db: DB, chat_token: ChatToken = None
) -> FinderRealtimeSession:
    """Firebase sign-in for the page: a token that can only read this one conversation's
    signal document. The page then gets live updates without polling."""
    response.headers["Cache-Control"] = "no-store"
    session = await FinderChatService(db).realtime_session(token_id, chat_token)
    return FinderRealtimeSession(**session)
