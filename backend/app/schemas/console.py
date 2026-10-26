"""Typed contracts for the superuser console and its allowlisted commands."""

from typing import Any

from pydantic import UUID4, BaseModel, ConfigDict, Field


class ConsoleArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HelpArgs(ConsoleArgs):
    command: str | None = None


class VaultArgs(ConsoleArgs):
    vault_id: UUID4


class ExpeditionSetupArgs(VaultArgs):
    dweller_id: UUID4
    site_id: str = Field(min_length=1, max_length=64)
    duration_hours: int = Field(default=8, ge=1, le=24)


class CapsCheatArgs(VaultArgs):
    amount: int = Field(default=500, ge=1, le=999_999)


class ConsoleRequest(ConsoleArgs):
    command: str = Field(min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict, max_length=10)


class ConsoleLink(BaseModel):
    label: str
    to: str


class ConsoleResult(BaseModel):
    ok: bool = True
    lines: list[str]
    links: list[ConsoleLink] = Field(default_factory=list)


class ConsoleCommand(BaseModel):
    name: str
    description: str
    mutates: bool = False
    args_schema: dict[str, Any]


class ConsoleSite(BaseModel):
    id: str
    name: str
    min_level: int


class ConsoleManifest(BaseModel):
    commands: list[ConsoleCommand]
    sites: list[ConsoleSite]
