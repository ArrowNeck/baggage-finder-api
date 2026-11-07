import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "baggage-finder-api"
    APP_VERSION: str = "1.0.0"
    DESCRIPTION: str = "Baggage Finder FastAPI Service"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    API_PREFIX: str = "/api"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str

    DATABASE_SSL: bool = True
    DATABASE_ECHO: bool = False

    # Application database connection pool settings
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 5
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    # JWT / tokens
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Abuse protection
    RATE_LIMIT_PER_MINUTE: int = 10

    # CORS (browsers only; native mobile apps are unaffected)
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = []

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "text"

    # Firebase Cloud Messaging (push notifications)
    FIREBASE_ENABLED: bool = False
    FIREBASE_CREDENTIALS_FILE: str | None = None  # path to the service-account JSON (local/dev)
    FIREBASE_CREDENTIALS_JSON: str | None = None  # the JSON itself (Azure App Settings / Key Vault)

    # Public QR page (finder side)
    QR_SCAN_PUSH_COOLDOWN_SECONDS: int = 600  # max one "tag scanned" push per bag per window
    QR_FOUND_COOLDOWN_SECONDS: int = 60  # max one "I found it" report per bag per window
    QR_REVEAL_PHONE_WHEN_LOST: bool = False  # show the owner's phone to finders while status=lost

    FIREBASE_PROJECT_ID: str | None = None
    FIREBASE_WEB_API_KEY: str | None = None  # public web key: Project settings > General
    FIREBASE_AUTH_DOMAIN: str | None = None  # defaults to <project id>.firebaseapp.com
    FIREBASE_WEB_SDK_VERSION: str = "10.14.1"  # loaded by the QR page from gstatic.com
    PUSH_CHAT_DATA_ONLY: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def realtime_enabled(self) -> bool:
        return bool(
            self.FIREBASE_ENABLED and self.FIREBASE_PROJECT_ID and self.FIREBASE_WEB_API_KEY
        )

    @property
    def firebase_auth_domain(self) -> str:
        return self.FIREBASE_AUTH_DOMAIN or f"{self.FIREBASE_PROJECT_ID}.firebaseapp.com"

    @model_validator(mode="after")
    def check_firebase_credentials(self) -> "Settings":
        if self.FIREBASE_ENABLED and not (
            self.FIREBASE_CREDENTIALS_FILE or self.FIREBASE_CREDENTIALS_JSON
        ):
            raise ValueError(
                "FIREBASE_ENABLED=true needs FIREBASE_CREDENTIALS_FILE or FIREBASE_CREDENTIALS_JSON"
            )
        return self

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("API_PREFIX")
    @classmethod
    def normalize_prefix(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        return v if not v or v.startswith("/") else f"/{v}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
