import hashlib
import secrets
from datetime import timedelta
from functools import lru_cache
from uuid import UUID

import bcrypt as _bcrypt
import jwt
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.utils.helpers import utcnow

# ── Password ────────────────────────────────────────────────────────────────
# bcrypt only reads the first 72 bytes; schemas reject longer passwords up front.


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:  # e.g. password longer than 72 bytes, malformed hash
        return False


# bcrypt is CPU-bound; run it off the event loop so one login can't stall every request.
async def hash_password_async(plain: str) -> str:
    return await run_in_threadpool(hash_password, plain)


async def verify_password_async(plain: str, hashed: str) -> bool:
    return await run_in_threadpool(verify_password, plain, hashed)


@lru_cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


async def burn_password_check(plain: str) -> None:
    """Spend the same time as a real check so unknown emails aren't distinguishable."""
    await run_in_threadpool(verify_password, plain, _dummy_hash())


# ── Access tokens (JWT) ─────────────────────────────────────────────────────


def create_access_token(user_id: UUID) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> UUID | None:
    """Returns the user id, or None for any invalid/expired/non-access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        if payload.get("type") != "access":
            return None
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


# ── Opaque tokens (refresh, password reset) ─────────────────────────────────
# Random strings; only a SHA-256 digest is stored so a DB leak doesn't leak sessions.


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_opaque_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_digest)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)
