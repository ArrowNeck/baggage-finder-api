from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Category, Status
from app.database.base import Base
from app.utils.mixin import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


def _enum_column(enum_cls: type[enum.Enum]) -> SAEnum:
    """Enum stored as VARCHAR (no native PG enum type, no CHECK constraint).

    Adding a member later then needs no migration; only the Python enum changes.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=20,
        values_callable=lambda e: [member.value for member in e],
    )


class Baggage(Base, TimestampMixin):
    __tablename__ = "baggages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Owner. Users are soft-deleted, so rows are never orphaned; RESTRICT guards hard deletes.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    token_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(256), nullable=False)

    category: Mapped[Category] = mapped_column(
        _enum_column(Category), default=Category.general, index=True, nullable=False
    )

    color: Mapped[str] = mapped_column(String(100), nullable=False)

    brand: Mapped[str | None] = mapped_column(String(256), nullable=True)

    status: Mapped[Status] = mapped_column(
        _enum_column(Status), default=Status.active, index=True, nullable=False
    )

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(
        foreign_keys=[user_id],
        back_populates="baggages",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return (
            f"<Baggage id={self.id} "
            f"token_id={self.token_id!r} "
            f"status={self.status} "
            f"category={self.category}>"
        )
