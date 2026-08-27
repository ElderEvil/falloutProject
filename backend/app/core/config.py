from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import AliasChoices, EmailStr, Field, PostgresDsn, field_validator, model_validator
from pydantic_core.core_schema import FieldValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIProfileProtocol(Protocol):
    """Minimal profile shape for effective-config resolution (DB-backed AISettings or None)."""

    provider: str | None
    model: str | None
    base_url: str | None
    gateway_route: str | None


class Settings(BaseSettings):
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Fallout Shelter API"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://fallout.evillab.tech",
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
    RUSTFS_DEFAULT_BUCKET: str = Field(
        default="fallout-shelter",
        validation_alias=AliasChoices("RUSTFS_DEFAULT_BUCKET", "RUSTFS_BUCKET"),
    )
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
    PYDANTIC_AI_GATEWAY_ROUTE: str | None = None
    PYDANTIC_AI_GATEWAY_BASE_URL: str | None = None

    # Legacy direct provider API keys (deprecated, use Gateway instead)
    AI_PROVIDER: Literal["openai", "anthropic", "ollama", "lmstudio"] = "openai"
    AI_MODEL: str = "gpt-4o"
    AI_IMAGE_MODEL: str = "gpt-image-1"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"

    @property
    def ai_provider_mode(self) -> Literal["gateway", "direct", "ollama", "lmstudio", "disabled"]:
        """Determine which AI provider mode to use.

        Priority:
        1. Pydantic AI Gateway (recommended)
        2. Direct provider API keys (deprecated)
        3. Ollama local
        4. LM Studio local
        5. Disabled
        """
        if self.PYDANTIC_AI_GATEWAY_API_KEY:
            return "gateway"
        if self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY:
            return "direct"
        if self.AI_PROVIDER == "ollama" and self.OLLAMA_BASE_URL:
            return "ollama"
        if self.AI_PROVIDER == "lmstudio" and self.LMSTUDIO_BASE_URL:
            return "lmstudio"
        return "disabled"

    # Effective AI config resolution: DB profile overrides .env.
    # Secrets (API keys) are NEVER stored in DB — they come from .env only.

    def effective_ai_provider(self, profile: AIProfileProtocol | None) -> str:
        if profile and profile.provider:
            return profile.provider
        return self.AI_PROVIDER

    def effective_ai_model(self, profile: AIProfileProtocol | None) -> str:
        if profile and profile.model:
            return profile.model
        return self.AI_MODEL

    def effective_ai_base_url(self, profile: AIProfileProtocol | None) -> str | None:
        if profile and profile.base_url:
            return profile.base_url
        eff_provider = self.effective_ai_provider(profile)
        if eff_provider == "ollama":
            return self.OLLAMA_BASE_URL
        if eff_provider == "lmstudio":
            return self.LMSTUDIO_BASE_URL
        return None

    def effective_ai_gateway_route(self, profile: AIProfileProtocol | None) -> str | None:
        if profile and profile.gateway_route:
            return profile.gateway_route
        return self.PYDANTIC_AI_GATEWAY_ROUTE

    def effective_ai_mode(self, profile: AIProfileProtocol | None) -> str:
        """Effective mode from profile-forced provider + env keys.

        A profile-forced local provider (lmstudio/ollama with a base URL)
        wins over gateway/direct env modes; otherwise env secrets decide.
        """
        eff_provider = self.effective_ai_provider(profile)
        eff_base_url = self.effective_ai_base_url(profile)
        if eff_provider == "ollama" and eff_base_url:
            return "ollama"
        if eff_provider == "lmstudio" and eff_base_url:
            return "lmstudio"
        if self.PYDANTIC_AI_GATEWAY_API_KEY:
            return "gateway"
        if self.OPENAI_API_KEY or self.ANTHROPIC_API_KEY:
            return "direct"
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

    # SSE Configuration
    SSE_HEARTBEAT_INTERVAL: int = Field(
        default=30,
        description="Default heartbeat interval (seconds) for SSE stream keep-alive. "
        "Individual streams (e.g. game ticks) may override with their own cadence.",
        ge=5,
        le=300,
    )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def log_file_path(self) -> str | None:
        """Return the configured log path, with a persistent production default."""
        if self.LOG_FILE_PATH:
            return self.LOG_FILE_PATH
        if self.ENVIRONMENT == "production":
            return "/var/log/fallout_shelter/app.log"
        return None

    @property
    def project_root(self) -> Path:
        """Get the project root directory (where CHANGELOG.md is located)."""
        # Go up from backend/app/core/config.py to project root
        return Path(__file__).parent.parent.parent.parent

    @field_validator("ASYNC_DATABASE_URI", mode="after")
    @classmethod
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
    def ensure_frontend_origin(self) -> "Settings":
        if self.FRONTEND_URL and self.FRONTEND_URL not in self.BACKEND_CORS_ORIGINS:
            self.BACKEND_CORS_ORIGINS.append(self.FRONTEND_URL)
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
