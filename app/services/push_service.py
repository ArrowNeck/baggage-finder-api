import asyncio
import json
import uuid
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, messaging
from firebase_admin import exceptions as fb_exceptions
from sqlalchemy import update
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.database.base import AsyncSessionLocal
from app.models.user import User
from app.utils.logger import get_logger

logger = get_logger(__name__)

PUSH_TIMEOUT_SECONDS = 8  # push is awaited inside the request, so never let it hang


@lru_cache
def init_firebase() -> firebase_admin.App | None:
    """Initialise the Admin SDK once. Returns None when push is disabled."""
    if not settings.FIREBASE_ENABLED:
        return None
    if settings.FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
    else:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)
    return firebase_admin.initialize_app(cred)


def _send_blocking(
    app: firebase_admin.App,
    token: str,
    title: str,
    body: str,
    data: dict[str, str],
    thread: str | None = None,
    data_only: bool = False,
) -> str:
    if data_only:
        # No `notification` block: on Android the app receives the data and decides whether to
        # show anything (for example nothing while the user is already in that chat), using a
        # local notification when it wants a popup. iOS silent pushes are throttled and are not
        # delivered to force-quit apps, so iOS still gets a normal alert (the app can suppress
        # it in the foreground with the presentation options).
        message = messaging.Message(
            token=token,
            data={**data, "title": title, "body": body},
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(title=title, body=body),
                        sound="default",
                        thread_id=thread,
                    )
                )
            ),
        )
        return messaging.send(message, app=app)
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
        data=data,  # values must be strings (e.g. ids for deep links in the app)
        android=messaging.AndroidConfig(
            priority="high",
            # same tag = the new notification replaces the old one instead of piling up
            notification=messaging.AndroidNotification(tag=thread) if thread else None,
        ),
        apns=messaging.APNSConfig(
            # same thread id = iOS stacks them in one group
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default", thread_id=thread))
        ),
    )
    return messaging.send(message, app=app)


async def _clear_token(user_id: uuid.UUID, token: str) -> None:
    # Own session: this also runs from background tasks, after the request session is gone.
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User).where(User.id == user_id, User.fcm_token == token).values(fcm_token=None)
        )
        await db.commit()


async def send_push(
    user_id: uuid.UUID,
    token: str | None,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    thread: str | None = None,
    data_only: bool = False,
) -> bool:
    """Best-effort push to one device. Never raises: a failed push must not fail an API call.

    Usable directly or as a background task:
        background.add_task(send_push, owner.id, owner.fcm_token, "Title", "Body", {"type": "x"})
    """
    try:
        app = init_firebase()
    except Exception:
        # Bad credentials must never turn a scan or a chat message into a 500.
        logger.exception("Firebase initialisation failed")
        return False
    if app is None:
        logger.info("Push skipped: Firebase disabled")
        return False
    if not token:
        return False

    payload = {key: str(value) for key, value in (data or {}).items()}
    try:
        await asyncio.wait_for(
            run_in_threadpool(_send_blocking, app, token, title, body, payload, thread, data_only),
            timeout=PUSH_TIMEOUT_SECONDS,
        )
        return True
    except TimeoutError:
        logger.warning("Push timed out", extra={"user_id": str(user_id)})
    except messaging.UnregisteredError:
        # App uninstalled or token expired: stop using it until the app registers a new one.
        await _clear_token(user_id, token)
        logger.info("Stale FCM token removed", extra={"user_id": str(user_id)})
    except messaging.SenderIdMismatchError:
        logger.error("FCM sender mismatch: service account is from a different Firebase project")
    except fb_exceptions.FirebaseError as exc:
        logger.warning("Push failed", extra={"user_id": str(user_id), "code": exc.code})
    except Exception:
        logger.exception("Unexpected push error", extra={"user_id": str(user_id)})
    return False
