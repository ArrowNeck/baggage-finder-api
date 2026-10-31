from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.utils.mixin import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.baggage import Baggage


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Stored lower-cased; unique so concurrent sign-ups can't create duplicates.
    # Soft-deleted users keep their row, so their email stays reserved.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    fcm_token: Mapped[str | None] = mapped_column(String(512), nullable=True)

    baggages: Mapped[list[Baggage]] = relationship(
        foreign_keys="Baggage.user_id",
        back_populates="user",
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
