import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.core.base_schemas import BaseResponse, BaseSchema
from app.core.enums import Category, ScanKind, Status

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
AccuracyM = Annotated[float, Field(ge=0, le=1_000_000, allow_inf_nan=False)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=280)]
Contact = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class PublicOwner(BaseModel):
    first_name: str
    phone: str | None = None  # only while the bag is marked lost, and only if enabled in settings


class PublicBaggageResponse(BaseModel):
    """What a stranger holding the tag may see. No ids, remarks, email or token."""

    name: str
    category: Category
    color: str
    brand: str | None = None
    status: Status
    owner: PublicOwner


class FoundRequest(BaseSchema):
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    accuracy: AccuracyM | None = None
    message: Note | None = None
    contact: Contact | None = None

    @model_validator(mode="after")
    def _location_is_a_pair(self) -> "FoundRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be sent together")
        return self


class PublicActionResponse(BaseModel):
    message: str


class ScanEventResponse(BaseResponse):
    id: uuid.UUID
    kind: ScanKind
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    message: str | None = None
    contact: str | None = None
    created_at: datetime
