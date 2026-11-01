import uuid
from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints, model_validator

from app.core.base_schemas import BaseResponse, BaseSchema
from app.core.enums import Category, Status
from app.core.types import HexColor

Text256 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
Text100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Remarks = Annotated[str, StringConstraints(max_length=2000)]


class BaggageCreate(BaseSchema):
    name: Text256
    category: Category = Category.general
    color: HexColor
    brand: Text256 | None = None
    remarks: Remarks | None = None


class BaggageUpdate(BaseSchema):
    name: Text256 | None = None
    category: Category | None = None
    color: HexColor | None = None
    brand: Text256 | None = None
    status: Status | None = None
    remarks: Remarks | None = None

    @model_validator(mode="after")
    def _check(self) -> "BaggageUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        # brand/remarks are nullable columns (null clears them); the rest are required.
        for field in ("name", "category", "color", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class BaggageStatusUpdate(BaseSchema):
    status: Status


class BaggageResponse(BaseResponse):
    id: uuid.UUID
    user_id: uuid.UUID
    token_id: str
    name: str
    category: Category
    color: HexColor
    brand: str | None = None
    status: Status
    remarks: str | None = None
    created_at: datetime
    updated_at: datetime
