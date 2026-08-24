from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel, Field

ALLOWED_AI_PROVIDERS = {"openai", "anthropic", "ollama", "lmstudio"}


class AISettingsProfile(BaseModel):
    id: UUID4
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    gateway_route: str | None = None
    updated_at: datetime | None = None


class AISettingsEffective(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    gateway_route: str | None = None
    mode: str


class AISettingsRead(BaseModel):
    profile: AISettingsProfile | None = None
    effective: AISettingsEffective


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
