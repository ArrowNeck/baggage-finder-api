from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.api import v1_router
from app.core.config import settings
from app.core.handlers import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware
from app.database.base import engine
from app.services.push_service import init_firebase
from app.utils.logger import configure_logging, get_logger

# ── Startup / Shutdown ───────────────────────────────────────────────────────
configure_logging()
logger = get_logger(__name__)
# Fails fast on bad credentials; a no-op when FIREBASE_ENABLED=false.
firebase_on = init_firebase() is not None
logger.info(
    "Starting application",
    extra={"app": settings.APP_NAME, "version": settings.APP_VERSION, "push": firebase_on},
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    configure_logging()
    logger = get_logger(__name__)
    logger.info(
        "Starting application",
        extra={"app": settings.APP_NAME, "version": settings.APP_VERSION},
    )
    yield
    logger.info("Shutting down — closing DB connections")
    await engine.dispose()


# ── Ops endpoints ────────────────────────────────────────────────────────────


async def health_check() -> dict[str, Any]:
    return {"status": "ok", "version": settings.APP_VERSION}


async def readiness_check() -> JSONResponse:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        get_logger(__name__).exception("Readiness check failed")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})


# ── App factory ──────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.DESCRIPTION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ── Middleware ───────────────────────────────────────────────────────────
    app.add_middleware(RequestLoggingMiddleware)
    if settings.ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.ALLOWED_ORIGINS,
            allow_credentials=False,  # bearer tokens only, no cookies
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    register_exception_handlers(app)

    # ── Routers ──────────────────────────────────────────────────────────────
    app.include_router(v1_router, prefix=settings.API_PREFIX)

    # ── Health / readiness ───────────────────────────────────────────────────
    app.get("/health", tags=["Health"], include_in_schema=False)(health_check)
    app.get("/ready", tags=["Health"], include_in_schema=False)(readiness_check)

    return app


app = create_app()
