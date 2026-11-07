import secrets
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.core.routes import WebRoutes

_TEMPLATE = (Path(__file__).resolve().parent.parent / "web" / "qr.html").read_text(encoding="utf-8")

# Served at the site root (https://<domain>/qr/<token>), not under API_PREFIX.
router = APIRouter(include_in_schema=False)


@router.get(WebRoutes.QR, response_class=HTMLResponse)
async def qr_page(token_id: str) -> HTMLResponse:
    """Static landing page; it loads its data from /public/qr/{token} with JavaScript."""
    nonce = secrets.token_urlsafe(16)
    script_src = f"'nonce-{nonce}'"
    connect_src = "'self'"
    if settings.realtime_enabled:
        # The Firebase web SDK (loaded lazily by the page) and its sign-in / Firestore calls.
        script_src += " https://www.gstatic.com"
        connect_src += (
            " https://firestore.googleapis.com"
            " https://identitytoolkit.googleapis.com"
            " https://securetoken.googleapis.com"
        )
    html = _TEMPLATE.replace("__NONCE__", nonce).replace("__API_PREFIX__", settings.API_PREFIX)
    return HTMLResponse(
        html,
        headers={
            # No third-party requests at all; only our own scripts and API.
            "Content-Security-Policy": (
                "default-src 'none'; "
                f"script-src {script_src}; style-src 'nonce-{nonce}'; "
                f"img-src 'self' data:; connect-src {connect_src}; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",  # the token is in the URL
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow",
            "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
            "Cache-Control": "no-store",
        },
    )
