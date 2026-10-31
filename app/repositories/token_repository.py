import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_token import PasswordResetToken, RefreshToken
from app.utils.helpers import utcnow


class TokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Refresh tokens ──────────────────────────────────────────────────────
    async def create_refresh(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_refresh_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def claim_refresh(self, token_id: uuid.UUID) -> bool:
        """Atomically revoke + mark as rotated. Only one concurrent caller can win."""
        now = utcnow()
        result = cast(
            CursorResult,
            await self.db.execute(
                update(RefreshToken)
                .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now, rotated_at=now)
            ),
        )
        return result.rowcount == 1

    async def revoke_refresh_by_hash(self, user_id: uuid.UUID, token_hash: str) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )

    async def revoke_all_refresh(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )

    # ── Password reset tokens ───────────────────────────────────────────────
    async def create_reset(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        await self.db.flush()
        return token

    async def invalidate_unused_resets(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=utcnow())
        )

    async def get_reset_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def claim_reset(self, token_id: uuid.UUID) -> bool:
        result = cast(
            CursorResult,
            await self.db.execute(
                update(PasswordResetToken)
                .where(PasswordResetToken.id == token_id, PasswordResetToken.used_at.is_(None))
                .values(used_at=utcnow())
            ),
        )
        return result.rowcount == 1
