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
    DATABASE_ECHO: bool = False
    DATABASE_SSL: bool = False

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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
