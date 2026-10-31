"""Every error leaves the API in one shape:
{"success": false, "error": {"code", "message", "details"}}"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException, ValidationError
from app.utils.logger import get_logger

logger = get_logger(__name__)

_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_ERROR",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    429: "RATE_LIMITED",
}


def _response(
    status_code: int,
    code: str,
    message: str,
    details: list[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "success": False,
            "error": {"code": code, "message": message, "details": details or []},
        },
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return _response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    code = _HTTP_CODES.get(exc.status_code, "ERROR")
    return _response(exc.status_code, code, message, headers=getattr(exc, "headers", None))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Only the field path and message are returned. FastAPI's default 422 body also
    # echoes the submitted `input`, which would send passwords back to the client.
    details = [
        {
            "field": ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path")),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    first = details[0] if details else {"field": "", "message": "Invalid request data"}
    message = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
    return _response(ValidationError.STATUS_CODE, "VALIDATION_ERROR", message, details)


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning(
        "Integrity error", extra={"path": request.url.path, "type": type(exc.orig).__name__}
    )
    return _response(409, "CONFLICT", "A record with these values already exists")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception",
        extra={"path": request.url.path, "request_id": getattr(request.state, "request_id", None)},
    )
    return _response(500, "INTERNAL_ERROR", "Something went wrong")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, integrity_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
