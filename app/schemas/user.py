import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BeforeValidator,
    EmailStr,
    StringConstraints,
    model_validator,
)

from app.core.base_schemas import BaseResponse, BaseSchema
from app.utils.validations import PHONE_PATTERN, check_password_bytes, normalize_email

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Email = Annotated[EmailStr, BeforeValidator(normalize_email)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=PHONE_PATTERN)]
NewPassword = Annotated[
    str,
    StringConstraints(min_length=8, max_length=72),
    AfterValidator(check_password_bytes),
]
FcmToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]


class UserCreate(BaseSchema):
    name: Name
    email: Email
    phone: Phone | None = None
    password: NewPassword
    fcm_token: FcmToken | None = None


class UserUpdate(BaseSchema):
    name: Name | None = None
    email: Email | None = None
    phone: Phone | None = None
    fcm_token: FcmToken | None = None  # null clears the token

    @model_validator(mode="after")
    def _check(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in ("name", "email"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class UserResponse(BaseResponse):
    id: uuid.UUID
    name: str
    email: EmailStr
    phone: str | None = None
    fcm_token: str | None = None
    created_at: datetime
    updated_at: datetime
