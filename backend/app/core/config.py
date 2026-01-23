from typing import Any, Literal

from pydantic import EmailStr, PostgresDsn, field_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Fallout Shelter API"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    ALGORITHM: str = "HS256"
    SECRET_KEY: str

    EMAIL_TEST_USER: EmailStr
    FIRST_SUPERUSER_USERNAME: str
    FIRST_SUPERUSER_EMAIL: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    USERS_OPEN_REGISTRATION: bool

    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    CELERY_DATABASE_NAME: str = "celery_schedule_jobs"
    REDIS_HOST: str
    REDIS_PORT: str
    DB_POOL_SIZE: int = 83
    WEB_CONCURRENCY: int = 9
    POOL_SIZE: int = max(DB_POOL_SIZE // WEB_CONCURRENCY, 5)
    ASYNC_DATABASE_URI: PostgresDsn | str = ""

    MINIO_HOSTNAME: str | None = None
    MINIO_PORT: str | None = None
    MINIO_ROOT_USER: str | None = None
    MINIO_ROOT_PASSWORD: str | None = None
    MINIO_DEFAULT_BUCKET: str | None = None
    MINIO_PUBLIC_URL: str | None = None
    MINIO_PUBLIC_BUCKET_WHITELIST: list[str] = [
        "dweller-images",
        "dweller-thumbnails",
        "dweller-audio",
        "chat-audio",
        "outfit-images",
        "weapon-images",
    ]

    @property
    def minio_enabled(self) -> bool:
        """Check if MinIO is configured and should be used."""
        return all(
            [
                self.MINIO_HOSTNAME,
                self.MINIO_PORT,
                self.MINIO_ROOT_USER,
                self.MINIO_ROOT_PASSWORD,
            ]
        )

    @property
    def minio_public_base_url(self) -> str:
        """Get the public-facing base URL for MinIO (without trailing slash)."""
        if self.MINIO_PUBLIC_URL:
            return self.MINIO_PUBLIC_URL.rstrip("/")
        # Fallback to internal hostname:port for local development
        return f"http://{self.MINIO_HOSTNAME}:{self.MINIO_PORT}"

    AI_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"
    AI_MODEL: str = "gpt-4o"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # Email Configuration
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025  # Mailpit default for local dev
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_TLS: bool = False
    SMTP_SSL: bool = False
    EMAIL_FROM_ADDRESS: str = "noreply@falloutshelter.com"
    EMAIL_FROM_NAME: str = "Fallout Shelter"
    FRONTEND_URL: str = "http://localhost:5173"  # For email links

    # Logging Configuration
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_JSON_FORMAT: bool = False  # True for production (JSON), False for development (human-readable)
    LOG_FILE_PATH: str | None = None  # Optional: "/var/log/fallout_shelter/app.log"

    # Security & Rate Limiting Configuration (fastapi-guard)
    ENABLE_RATE_LIMITING: bool = True  # Enable/disable rate limiting
    RATE_LIMIT_REQUESTS: int = 100  # Requests per window per IP
    RATE_LIMIT_WINDOW: int = 60  # Time window in seconds
    AUTO_BAN_THRESHOLD: int = 10  # Number of blocked requests before auto-ban
    AUTO_BAN_DURATION: int = 3600  # Ban duration in seconds (1 hour)
    IPINFO_TOKEN: str | None = None  # Optional: IPInfo API token for geolocation
    SECURITY_WHITELIST_IPS: list[str] = []  # IPs to whitelist (bypass rate limiting)
    SECURITY_BLACKLIST_IPS: list[str] = []  # IPs to block completely

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @field_validator("ASYNC_DATABASE_URI", mode="after")
    def assemble_db_connection(cls, v: str | None, info: FieldValidationInfo) -> Any:
        if isinstance(v, str) and not v:
            return PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=info.data["POSTGRES_USER"],
                password=info.data["POSTGRES_PASSWORD"],
                host=info.data["POSTGRES_SERVER"],
                path=info.data["POSTGRES_DB"],
            )
        return v

    SYNC_CELERY_DATABASE_URI: PostgresDsn | str = ""

    @field_validator("SYNC_CELERY_DATABASE_URI", mode="after")
    def assemble_celery_db_connection(cls, v: str | None, info: FieldValidationInfo) -> Any:
        if isinstance(v, str) and not v:
            # Return raw string for Celery SQLAlchemy backend (needs db+postgresql scheme)
            return f"db+postgresql://{info.data['POSTGRES_USER']}:{info.data['POSTGRES_PASSWORD']}@{info.data['POSTGRES_SERVER']}/{info.data['POSTGRES_DB']}"
        return v

    SYNC_CELERY_BEAT_DATABASE_URI: PostgresDsn | str = ""

    @field_validator("SYNC_CELERY_BEAT_DATABASE_URI", mode="after")
    def assemble_celery_beat_db_connection(cls, v: str | None, info: FieldValidationInfo) -> Any:
        if isinstance(v, str) and not v:
            return PostgresDsn.build(
                scheme="postgresql+psycopg2",
                username=info.data["POSTGRES_USER"],
                password=info.data["POSTGRES_PASSWORD"],
                host=info.data["POSTGRES_SERVER"],
                path=info.data["POSTGRES_DB"],
            )
        return v

    ASYNC_CELERY_BEAT_DATABASE_URI: PostgresDsn | str = ""

    @field_validator("ASYNC_CELERY_BEAT_DATABASE_URI", mode="after")
    def assemble_async_celery_beat_db_connection(cls, v: str | None, info: FieldValidationInfo) -> Any:
        if isinstance(v, str) and not v:
            return PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=info.data["POSTGRES_USER"],
                password=info.data["POSTGRES_PASSWORD"],
                host=info.data["POSTGRES_SERVER"],
                path=info.data["POSTGRES_DB"],
            )
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
