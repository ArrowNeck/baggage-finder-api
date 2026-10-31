from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.database.base import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)

DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DB,
) -> User:
    """The user always comes from the validated access token, never from client input."""
    if credentials is None:
        raise AuthenticationError("Missing or invalid authentication")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AuthenticationError("Missing or invalid authentication")

    user = await UserRepository(db).get_by_id(user_id)  # excludes soft-deleted users
    if user is None:
        raise AuthenticationError("Missing or invalid authentication")
    return user


# Convenience type alias for endpoints
CurrentUser = Annotated[User, Depends(get_current_user)]
