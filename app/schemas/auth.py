from typing import Annotated

from pydantic import AliasChoices, Field, StringConstraints

from app.core.base_schemas import CamelSchema
from app.schemas.user import Email, FcmToken, NewPassword, UserResponse

Opaque = Annotated[str, StringConstraints(min_length=1, max_length=512)]
# Existing passwords are only checked, never re-validated against the new-password policy.
AnyPassword = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class LoginRequest(CamelSchema):
    email: Email
    # The current mobile app sends the password under `passwordHash`; both keys are accepted.
    password: AnyPassword = Field(validation_alias=AliasChoices("password", "passwordHash"))
    fcm_token: FcmToken | None = None  # ← add (the app sends it as fcmToken)


class TokenResponse(CamelSchema):
    access_token: str
    refresh_token: str


class AuthResponse(TokenResponse):
    user: UserResponse


class RefreshRequest(CamelSchema):
    refresh_token: Opaque


class LogoutRequest(CamelSchema):
    """Optional body. Without a refresh token, every session of the user is revoked."""

    refresh_token: Opaque | None = None


class PasswordChangeRequest(CamelSchema):
    current_password: AnyPassword
    new_password: NewPassword


class PasswordResetRequest(CamelSchema):
    email: Email


class PasswordResetConfirm(CamelSchema):
    reset_token: Opaque
    new_password: NewPassword
