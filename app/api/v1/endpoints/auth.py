from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from app.api.deps import DB, CurrentUser
from app.core.rate_limit import RateLimit
from app.core.routes import AuthRoutes
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService
from app.utils.notifications import deliver_reset_token

router = APIRouter(tags=["Auth"])


@router.post(
    AuthRoutes.SIGN_UP,
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit("signup"))],
)
async def sign_up(payload: UserCreate, db: DB) -> AuthResponse:
    """Register a new account and sign it in."""
    return await AuthService(db).register(payload)


@router.post(
    AuthRoutes.LOGIN,
    response_model=AuthResponse,
    dependencies=[Depends(RateLimit("login"))],
)
async def login(payload: LoginRequest, db: DB) -> AuthResponse:
    """Authenticate and receive the user plus an access/refresh token pair."""
    return await AuthService(db).login(payload)


@router.post(AuthRoutes.REFRESH, response_model=TokenResponse)
async def refresh_tokens(payload: RefreshRequest, db: DB) -> TokenResponse:
    """Exchange a refresh token for a new pair. The old refresh token is revoked."""
    return await AuthService(db).refresh(payload.refresh_token)


@router.post(AuthRoutes.LOGOUT, status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    current_user: CurrentUser, db: DB, payload: LogoutRequest | None = None
) -> Response:
    """Revoke the given refresh token, or all of the user's sessions if none is sent.

    Access tokens are stateless and remain valid until they expire.
    """
    await AuthService(db).logout(current_user, payload.refresh_token if payload else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    AuthRoutes.RESET_REQUEST,
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    dependencies=[Depends(RateLimit("reset-request"))],
)
async def request_password_reset(
    payload: PasswordResetRequest, db: DB, background: BackgroundTasks
) -> MessageResponse:
    """Always answers the same way, whether or not the email is registered."""
    issued = await AuthService(db).request_password_reset(payload.email)
    if issued:
        background.add_task(deliver_reset_token, *issued)
    return MessageResponse(message="If the email is registered, reset instructions have been sent")


@router.post(
    AuthRoutes.RESET,
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(RateLimit("reset"))],
)
async def reset_password(payload: PasswordResetConfirm, db: DB) -> Response:
    await AuthService(db).reset_password(payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
