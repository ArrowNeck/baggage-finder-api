from datetime import datetime

from sqlalchemy import false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.types import UTCDateTime
from app.utils.helpers import utcnow


class TimestampMixin:
    """created_at / updated_at, always timezone-aware UTC.

    Values are set Python-side so they exist on the instance right after flush
    (a server-side default would need a refresh, which async sessions can't lazy-load);
    server_default is kept as a safety net for rows inserted outside the app.
    """

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, server_default=func.now()
    )


class SoftDeleteMixin:
    """Adds is_deleted flag — rows are never physically removed."""

    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())
