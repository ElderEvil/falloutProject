from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.utils.serialize_types import OptionalUTCDateTimeJSON

ALLOWED_AI_PROVIDERS = {"openai", "ollama", "lmstudio"}


class AISettingsProfile(BaseModel):
    id: UUID
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    gateway_route: str | None = None
    updated_at: OptionalUTCDateTimeJSON = None


class AISettingsEffective(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    gateway_route: str | None = None
    mode: str


class JevStatus(BaseModel):
    """Read-only Jev (TypeSafe) decision-model status; the key is env-only, never shown."""

    enabled: bool
    configured: bool
    model: str
    timeout_seconds: float


class AISettingsRead(BaseModel):
    profile: AISettingsProfile | None = None
    effective: AISettingsEffective
    jev: JevStatus


class AISettingsUpdate(BaseModel):
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    gateway_route: str | None = Field(default=None, max_length=200)


class AISettingsTestInput(BaseModel):
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    gateway_route: str | None = Field(default=None, max_length=200)


class AISettingsTestResult(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: int | None = None
    model: str | None = None
    message: str | None = None
