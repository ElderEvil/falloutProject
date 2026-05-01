from pathlib import Path
from typing import Any, Literal

from pydantic import EmailStr, Field, PostgresDsn, field_validator, model_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Fallout Shelter API"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://fallout.evillab.dev",
    ]

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
    REDIS_HOST: str
    REDIS_PORT: str
    DB_POOL_SIZE: int = 83
    WEB_CONCURRENCY: int = 9
    POOL_SIZE: int = max(DB_POOL_SIZE // WEB_CONCURRENCY, 5)
    ASYNC_DATABASE_URI: PostgresDsn | str = ""

    # Storage Provider - RustFS (S3-compatible)
    RUSTFS_HOSTNAME: str | None = None
    RUSTFS_PORT: str | None = None
    RUSTFS_USE_HTTPS: bool = True
    RUSTFS_ACCESS_KEY: str | None = None
    RUSTFS_SECRET_KEY: str | None = None
    RUSTFS_DEFAULT_BUCKET: str = "fallout-shelter"
    RUSTFS_PUBLIC_URL: str | None = None
    RUSTFS_PUBLIC_BUCKET_WHITELIST: list[str] = [
        "fallout-shelter",
        "dweller-images",
        "dweller-thumbnails",
        "dweller-audio",
        "chat-audio",
        "outfit-images",
        "weapon-images",
        "room-images",
    ]

    # AI Configuration
    PYDANTIC_AI_GATEWAY_API_KEY: str | None = None

    # Legacy direct provider API keys (deprecated, use Gateway instead)
    AI_PROVIDER: Literal["openai", "anthropic", "ollama"] = "openai"
    AI_MODEL: str = "gpt-4o"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    @property
    def ai_provider_mode(self) -> Literal["gateway", "direct", "ollama", "disabled"]:
        """Determine which AI provider mode to use.

        Priority:
        1. Pydantic AI Gateway (recommended)
        2. Direct provider API keys (deprecated)
        3. Ollama local
        4. Disabled
        """
        if self.PYDANTIC_AI_GATEWAY_API_KEY:
            return "gateway"
        if self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY:
            return "direct"
        if self.AI_PROVIDER == "ollama" and self.OLLAMA_BASE_URL:
            return "ollama"
        return "disabled"

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
    LOG_FILE_RETENTION_DAYS: int = 14  # Number of days to retain log files

    INCIDENT_RETENTION_DAYS: int = Field(default=7, ge=1)
    NOTIFICATION_RETENTION_DAYS: int = Field(default=30, ge=1)
    CLEANUP_BATCH_SIZE: int = Field(default=500, ge=1, le=10_000)

    # Logfire Observability (optional)
    LOGFIRE_TOKEN: str | None = None  # Get token from https://logfire.pydantic.dev

    @property
    def logfire_enabled(self) -> bool:
        """Check if Logfire observability is configured."""
        return bool(self.LOGFIRE_TOKEN)

    # Security & Rate Limiting Configuration (fastapi-guard)
    ENABLE_RATE_LIMITING: bool = True  # Enable/disable rate limiting
    RATE_LIMIT_REQUESTS: int = 100  # Requests per window per IP
    RATE_LIMIT_WINDOW: int = 60  # Time window in seconds
    AUTO_BAN_THRESHOLD: int = 10  # Number of blocked requests before auto-ban
    AUTO_BAN_DURATION: int = 3600  # Ban duration in seconds (1 hour)
    IPINFO_TOKEN: str | None = None  # Optional: IPInfo API token for geolocation
    SECURITY_WHITELIST_IPS: list[str] = []  # IPs to whitelist (bypass rate limiting)
    SECURITY_BLACKLIST_IPS: list[str] = []  # IPs to block completely

    # Quota Configuration
    QUOTA_DISABLED: bool = False  # Disable token quotas (useful for local dev/testing)

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def project_root(self) -> Path:
        """Get the project root directory (where CHANGELOG.md is located)."""
        # Go up from backend/app/core/config.py to project root
        return Path(__file__).parent.parent.parent.parent

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

    @model_validator(mode="after")
    def validate_rustfs_config(self) -> "Settings":
        if not self.RUSTFS_HOSTNAME or not self.RUSTFS_PORT:
            msg = "RUSTFS_HOSTNAME and/or RUSTFS_PORT are not set. Configure RustFS settings."
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def ensure_frontend_origin(self) -> "Settings":
        if self.FRONTEND_URL and self.FRONTEND_URL not in self.BACKEND_CORS_ORIGINS:
            self.BACKEND_CORS_ORIGINS.append(self.FRONTEND_URL)
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
