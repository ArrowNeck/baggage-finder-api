from typing import Any

from fastapi import status


class AppException(Exception):  # noqa: N818
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        self.headers = headers


class AuthenticationError(AppException):
    """401: missing/invalid/expired credentials."""

    def __init__(self, message: str = "Invalid token", code: str = "AUTHENTICATION_ERROR"):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(AppException):
    """403: authenticated but not allowed."""

    def __init__(self, message: str = "Not allowed"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource", resource_id: str | None = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"

        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists", code: str = "CONFLICT"):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class InternalServerError(AppException):
    def __init__(self, message: str = "Unexpected error occurred"):
        super().__init__(
            code="INTERNAL_ERROR",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ValidationError(AppException):
    # CRUD_API.md maps invalid values to 400. Change here to switch to 422.
    STATUS_CODE = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str = "Invalid request data", details: list[Any] | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=self.STATUS_CODE,
            details=details,
        )


class BadRequestError(AppException):
    def __init__(
        self,
        message: str = "Bad request",
        details: list[Any] | None = None,
        code: str = "BAD_REQUEST",
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class RateLimitError(AppException):
    def __init__(self, retry_after: int):
        super().__init__(
            code="RATE_LIMITED",
            message="Too many requests. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
        )
