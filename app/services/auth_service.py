from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BadRequestError, ConflictError
from app.core.security import (
    burn_password_check,
    create_access_token,
    generate_opaque_token,
    hash_password_async,
    hash_token,
    verify_password_async,
)
from app.models.user import User
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    PasswordResetConfirm,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserResponse
from app.utils.helpers import utcnow
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.tokens = TokenRepository(db)

    async def _issue_tokens(self, user_id: UUID) -> tuple[str, str]:
        raw, digest = generate_opaque_token()
        await self.tokens.create_refresh(
            user_id, digest, utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        return create_access_token(user_id), raw

    async def _auth_response(self, user: User) -> AuthResponse:
        access, refresh = await self._issue_tokens(user.id)
        await self.db.commit()
        return AuthResponse(
            user=UserResponse.model_validate(user),
            access_token=access,
            refresh_token=refresh,
        )

    async def register(self, payload: UserCreate) -> AuthResponse:
        if await self.users.email_exists(payload.email):
            raise ConflictError("An account with this email already exists", code="EMAIL_EXISTS")

        user = await self.users.create(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            hashed_password=await hash_password_async(payload.password),
        )
        if payload.fcm_token:
            await self.users.assign_fcm_token(user, payload.fcm_token)
        response = await self._auth_response(user)  # commits
        logger.info("User registered", extra={"user_id": str(user.id)})
        return response

    async def login(self, payload: LoginRequest) -> AuthResponse:
        invalid = AuthenticationError("Invalid email or password", code="INVALID_CREDENTIALS")
        user = await self.users.get_by_email(payload.email)

        if user is None:
            await burn_password_check(payload.password)
            raise invalid
        if not await verify_password_async(payload.password, user.hashed_password):
            logger.warning("Failed login attempt", extra={"user_id": str(user.id)})
            raise invalid
        if payload.fcm_token and payload.fcm_token != user.fcm_token:
            await self.users.assign_fcm_token(user, payload.fcm_token)

        response = await self._auth_response(user)
        logger.info("User logged in", extra={"user_id": str(user.id)})
        return response

    async def refresh(self, refresh_token: str) -> TokenResponse:
        invalid = AuthenticationError(
            "Invalid or expired refresh token", code="INVALID_REFRESH_TOKEN"
        )
        token = await self.tokens.get_refresh_by_hash(hash_token(refresh_token))
        if token is None:
            raise invalid

        if not await self.tokens.claim_refresh(token.id):
            if token.rotated_at is not None:
                # A token that was already exchanged is being replayed: assume it leaked
                # and end every session. (Logged-out / password-changed tokens just fail.)
                await self.tokens.revoke_all_refresh(token.user_id)
                await self.db.commit()
                logger.warning(
                    "Refresh token reuse detected", extra={"user_id": str(token.user_id)}
                )
            raise invalid

        user = await self.users.get_by_id(token.user_id)
        if user is None or token.expires_at <= utcnow():
            await self.db.commit()  # keep the revocation
            raise invalid

        access, new_refresh = await self._issue_tokens(user.id)
        await self.db.commit()
        return TokenResponse(access_token=access, refresh_token=new_refresh)

    async def logout(self, user: User, refresh_token: str | None) -> None:
        if refresh_token:
            await self.tokens.revoke_refresh_by_hash(user.id, hash_token(refresh_token))
        else:
            await self.tokens.revoke_all_refresh(user.id)
        await self.db.commit()

    async def request_password_reset(self, email: str) -> tuple[str, str] | None:
        """Returns (email, raw_token) to deliver, or None if the account doesn't exist.

        The endpoint answers identically either way so it can't be used to find accounts.
        """
        user = await self.users.get_by_email(email)
        if user is None:
            return None
        await self.tokens.invalidate_unused_resets(user.id)  # only the newest token works
        raw, digest = generate_opaque_token()
        await self.tokens.create_reset(
            user.id, digest, utcnow() + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
        )
        await self.db.commit()
        return user.email, raw

    async def reset_password(self, payload: PasswordResetConfirm) -> None:
        invalid = BadRequestError(
            "Reset token is invalid, expired, or already used", code="INVALID_RESET_TOKEN"
        )
        token = await self.tokens.get_reset_by_hash(hash_token(payload.reset_token))
        if token is None or token.used_at is not None or token.expires_at <= utcnow():
            raise invalid
        if not await self.tokens.claim_reset(token.id):
            raise invalid

        user = await self.users.get_by_id(token.user_id)
        if user is None:
            await self.db.commit()
            raise invalid

        await self.users.update(
            user, hashed_password=await hash_password_async(payload.new_password)
        )
        await self.tokens.revoke_all_refresh(user.id)
        await self.db.commit()
        logger.info("Password reset", extra={"user_id": str(user.id)})
