import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.security import hash_password_async, verify_password_async
from app.models.user import User
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import PasswordChangeRequest
from app.schemas.user import UserResponse, UserUpdate
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = TokenRepository(db)

    @staticmethod
    def _require_self(current_user: User, user_id: uuid.UUID) -> None:
        # Any other user's account is reported as missing (no existence leak).
        if user_id != current_user.id:
            raise NotFoundError("User", str(user_id))

    async def get_user(self, current_user: User, user_id: uuid.UUID) -> UserResponse:
        self._require_self(current_user, user_id)
        return UserResponse.model_validate(current_user)

    async def update_user(
        self, current_user: User, user_id: uuid.UUID, payload: UserUpdate
    ) -> UserResponse:
        self._require_self(current_user, user_id)
        changes = payload.model_dump(exclude_unset=True)

        new_email = changes.get("email")
        if new_email and new_email != current_user.email:
            if await self.users.email_exists(new_email, exclude_id=current_user.id):
                raise ConflictError(
                    "An account with this email already exists", code="EMAIL_EXISTS"
                )

        user = await self.users.update(current_user, **changes)
        await self.db.commit()
        logger.info("User updated", extra={"user_id": str(user.id), "fields": list(changes)})
        return UserResponse.model_validate(user)

    async def delete_user(self, current_user: User, user_id: uuid.UUID) -> None:
        """Soft delete: account disabled and sessions revoked; baggage rows are retained."""
        self._require_self(current_user, user_id)
        await self.users.soft_delete(current_user)
        await self.tokens.revoke_all_refresh(current_user.id)
        await self.db.commit()
        logger.info("User deleted", extra={"user_id": str(user_id)})

    async def change_password(self, current_user: User, payload: PasswordChangeRequest) -> None:
        if not await verify_password_async(payload.current_password, current_user.hashed_password):
            raise BadRequestError("Current password is incorrect", code="INVALID_CURRENT_PASSWORD")
        await self.users.update(
            current_user, hashed_password=await hash_password_async(payload.new_password)
        )
        await self.tokens.revoke_all_refresh(current_user.id)  # client must sign in again
        await self.db.commit()
        logger.info("Password changed", extra={"user_id": str(current_user.id)})
