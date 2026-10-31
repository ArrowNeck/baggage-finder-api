from app.utils.logger import get_logger

logger = get_logger(__name__)


async def deliver_reset_token(email: str, raw_token: str) -> None:
    """Hook that delivers the password-reset link/code to the user.

    No email provider is wired up yet. Plug one in here (Azure Communication Services,
    SendGrid, ...) and put `raw_token` in the link or code. Never log the token or email.
    """
    logger.info("Password reset issued; delivery provider not configured")
