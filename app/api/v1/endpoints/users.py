import uuid

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import DB, CurrentUser
from app.core.exceptions import BadRequestError
from app.core.rate_limit import RateLimit
from app.core.routes import UserRoutes
from app.schemas.auth import PasswordChangeRequest
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse, UserUpdate
from app.services.push_service import send_push
from app.services.user_service import UserService

router = APIRouter(tags=["Users"])


@router.get(f"{UserRoutes.PREFIX}{UserRoutes.BY_ID}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, current_user: CurrentUser, db: DB) -> UserResponse:
    """Read your own profile (other users' ids return 404)."""
    return await UserService(db).get_user(current_user, user_id)


@router.patch(f"{UserRoutes.PREFIX}{UserRoutes.BY_ID}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, current_user: CurrentUser, db: DB
) -> UserResponse:
    """Update name, email, phone and/or fcm_token."""
    return await UserService(db).update_user(current_user, user_id, payload)


@router.delete(
    f"{UserRoutes.PREFIX}{UserRoutes.BY_ID}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_user(user_id: uuid.UUID, current_user: CurrentUser, db: DB) -> Response:
    """Soft-delete your account and revoke all sessions."""
    await UserService(db).delete_user(current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(UserRoutes.PASSWORD, status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def change_password(
    payload: PasswordChangeRequest, current_user: CurrentUser, db: DB
) -> Response:
    """Change password. All refresh tokens are revoked, so sign in again afterwards."""
    await UserService(db).change_password(current_user, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    UserRoutes.PUSH_TEST,
    response_model=MessageResponse,
    dependencies=[Depends(RateLimit("push-test"))],
)
async def send_test_push(current_user: CurrentUser) -> MessageResponse:
    """Send a test notification to your own device (uses your stored fcm_token)."""
    if not current_user.fcm_token:
        raise BadRequestError("No FCM token stored for this account", code="NO_FCM_TOKEN")
    sent = await send_push(
        current_user.id,
        current_user.fcm_token,
        "Baggage Finder",
        "Push notifications are working",
        {"type": "test"},
    )
    return MessageResponse(
        message="Test notification sent" if sent else "Could not send (check server logs)"
    )
