"""Firebase as the real-time channel for chat.

Design: PostgreSQL stays the single source of truth for messages. Firestore only holds one
tiny "signal" document per conversation that this API rewrites after every change:

    conversations/{conversationId} = {ownerUid, baggageId, lastMessageId, lastMessageSender,
                                      closed, updatedAt}

Clients (the QR page and the mobile app) sign in to Firebase with a custom token minted here
and *listen* to that document. When it changes they fetch the new messages from this API with
their usual cursor request. No message text is stored in Firestore, clients can never write to
it (see firestore.rules), and a missed signal only costs a slower catch-up, never lost chat.
"""

import asyncio
import uuid
from functools import lru_cache
from typing import Any

from firebase_admin import auth, firestore
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.exceptions import AppException
from app.services.push_service import init_firebase
from app.utils.logger import get_logger

logger = get_logger(__name__)

COLLECTION = "conversations"
FIRESTORE_TIMEOUT_SECONDS = 5  # runs inside the request, so never let it hang


class RealtimeUnavailable(AppException):
    def __init__(self) -> None:
        super().__init__(
            code="REALTIME_UNAVAILABLE",
            message="Real-time chat is not available",
            status_code=503,
        )


def realtime_enabled() -> bool:
    return settings.realtime_enabled


# ── Sign-in tokens ──────────────────────────────────────────────────────────
def mint_owner_token(user_id: uuid.UUID) -> str:
    """The owner's Firebase uid is their user id, which the rules compare to `ownerUid`."""
    token = auth.create_custom_token(str(user_id), {"role": "owner"}, app=init_firebase())
    return token.decode()


def mint_finder_token(conversation_id: uuid.UUID) -> str:
    """Scoped to one conversation: the rules only let this uid read that one document."""
    claims = {"role": "finder", "conversationId": str(conversation_id)}
    token = auth.create_custom_token(f"finder_{conversation_id}", claims, app=init_firebase())
    return token.decode()


async def _mint(minter: Any, subject: uuid.UUID) -> str:
    try:
        return await run_in_threadpool(minter, subject)
    except Exception:
        # Misconfigured credentials: say "unavailable" so clients fall back to polling.
        logger.exception("Could not mint a Firebase sign-in token")
        raise RealtimeUnavailable() from None


async def finder_session(conversation_id: uuid.UUID) -> dict[str, str]:
    if not realtime_enabled():
        raise RealtimeUnavailable()
    token = await _mint(mint_finder_token, conversation_id)
    return {
        "custom_token": token,
        "project_id": settings.FIREBASE_PROJECT_ID or "",
        "api_key": settings.FIREBASE_WEB_API_KEY or "",
        "auth_domain": settings.firebase_auth_domain,
        "sdk_version": settings.FIREBASE_WEB_SDK_VERSION,
        "conversation_id": str(conversation_id),
    }


async def owner_session(user_id: uuid.UUID) -> dict[str, str]:
    if not realtime_enabled():
        raise RealtimeUnavailable()
    token = await _mint(mint_owner_token, user_id)
    return {
        "custom_token": token,
        "project_id": settings.FIREBASE_PROJECT_ID or "",
        "api_key": settings.FIREBASE_WEB_API_KEY or "",
        "auth_domain": settings.firebase_auth_domain,
        "owner_uid": str(user_id),
        "collection": COLLECTION,
    }


# ── Signal documents ────────────────────────────────────────────────────────
@lru_cache
def _firestore() -> Any:
    return firestore.client(app=init_firebase())


def _write_blocking(conversation_id: uuid.UUID, fields: dict[str, Any]) -> None:
    _firestore().collection(COLLECTION).document(str(conversation_id)).set(fields, merge=True)


def _delete_blocking(conversation_ids: list[uuid.UUID]) -> None:
    client = _firestore()
    for conversation_id in conversation_ids:
        client.collection(COLLECTION).document(str(conversation_id)).delete()


async def publish_conversation(
    conversation_id: uuid.UUID,
    owner_id: uuid.UUID,
    baggage_id: uuid.UUID,
    *,
    message_id: int | None = None,
    sender: str | None = None,
    closed: bool | None = None,
) -> None:
    """Touch the signal document so every listener wakes up. Best effort, never raises.

    Any write wakes the listeners and they simply fetch from their cursor, so it does not
    matter if two near-simultaneous writes land out of order.
    """
    if not realtime_enabled():
        return
    fields: dict[str, Any] = {
        "ownerUid": str(owner_id),
        "baggageId": str(baggage_id),
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }
    if message_id is not None:
        fields["lastMessageId"] = message_id
    if sender is not None:
        fields["lastMessageSender"] = sender
    if closed is not None:
        fields["closed"] = closed  # only written on close, so a later message can't reopen it
    try:
        await asyncio.wait_for(
            run_in_threadpool(_write_blocking, conversation_id, fields),
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning(
            "Realtime publish failed",
            extra={"conversation_id": str(conversation_id)},
            exc_info=True,
        )


async def delete_conversations(conversation_ids: list[uuid.UUID]) -> None:
    """Remove signal documents of deleted bags (best effort)."""
    if not conversation_ids or not realtime_enabled():
        return
    try:
        await asyncio.wait_for(
            run_in_threadpool(_delete_blocking, conversation_ids),
            timeout=FIRESTORE_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning("Realtime cleanup failed", exc_info=True)
