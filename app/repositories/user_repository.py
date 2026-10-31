import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Active (not soft-deleted) user only."""
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str, exclude_id: uuid.UUID | None = None) -> bool:
        """Includes soft-deleted users: their email stays reserved."""
        query = select(User.id).where(User.email == email)
        if exclude_id:
            query = query.where(User.id != exclude_id)
        result = await self.db.execute(query)
        return result.first() is not None

    async def create(self, **kwargs: object) -> User:
        user = User(**kwargs)
        self.db.add(user)
        await self.db.flush()
        return user

    async def update(self, user: User, **changes: object) -> User:
        for field, value in changes.items():
            setattr(user, field, value)
        await self.db.flush()
        return user

    async def soft_delete(self, user: User) -> None:
        user.is_deleted = True
        user.fcm_token = None  # stop push notifications to a closed account
        await self.db.flush()

    async def assign_fcm_token(self, user: User, token: str) -> None:
        """Store the device token on `user` and remove it from any other account."""
        await self.db.execute(
            update(User).where(User.fcm_token == token, User.id != user.id).values(fcm_token=None)
        )
        user.fcm_token = token
        await self.db.flush()
