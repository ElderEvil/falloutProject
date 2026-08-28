from sqlmodel import Field

from app.models.base import BaseUUIDModel, TimeStampMixin


class AISettings(BaseUUIDModel, TimeStampMixin, table=True):
    __tablename__ = "ai_settings"

    # Plain VARCHAR columns — NOT a PG enum (avoids the enum-drift migration trap).
    # Secrets (API keys) are never stored here; they come from .env only.
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    gateway_route: str | None = Field(default=None, max_length=200)
