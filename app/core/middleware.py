import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.logger import get_logger

logger = get_logger(__name__)

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration.

    Only the path is logged (no query string, headers or body), so tokens and
    passwords can't end up in logs. A well-formed inbound X-Request-ID is reused
    so one id can be followed across API Management and the app.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        start = time.perf_counter()

        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "HTTP request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response
