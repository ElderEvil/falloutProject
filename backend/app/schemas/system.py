from typing import Any

from pydantic import BaseModel


class GameBalanceResponse(BaseModel):
    """Game balance configuration settings response."""

    game_loop: dict[str, Any]
    incident: dict[str, Any]
    combat: dict[str, Any]
    health: dict[str, Any]
    happiness: dict[str, Any]
    training: dict[str, Any]
    resource: dict[str, Any]
    relationship: dict[str, Any]
    breeding: dict[str, Any]
    leveling: dict[str, Any]
    radio: dict[str, Any]
    death: dict[str, Any]
    dweller: dict[str, Any]
    exploration: dict[str, Any]
    rush: dict[str, Any]


class InfoResponse(BaseModel):
    """Application information response schema."""

    app_version: str
    api_version: str
    environment: str
    python_version: str
    build_date: str


class PresenceResponse(BaseModel):
    """Visibility-gated vault-view heartbeat confirmation."""

    vault_id: str
    last_presence_at: str | None


class GameStateResponse(BaseModel):
    """Current game-loop status for one vault."""

    vault_id: str
    is_active: bool
    is_paused: bool
    total_game_time: int
    last_tick_time: str
    offline_time: int


class VaultTickResponse(BaseModel):
    """Manual tick acknowledgement.

    A paused or duplicate tick short-circuits to ``status`` only; a processed
    tick carries ``vault_id``/``seconds_passed``/``updates``. ``updates`` stays an
    open map because the tick phases assemble per-phase diagnostics (including
    per-phase ``error`` keys) that are internal working contracts, not wire
    schemas.
    """

    message: str
    status: str | None = None
    vault_id: str | None = None
    seconds_passed: int | None = None
    updates: dict[str, Any] | None = None


class FeaturesResponse(BaseModel):
    """Feature switches clients use to hide what is switched off."""

    race_mechanics: bool
    faction_mechanics: bool
    world_events: bool
    pvp_duels: bool
    vault_diplomacy: bool
    combat_zone: bool


class ChangeEntry(BaseModel):
    """Individual change entry within a changelog version."""

    category: str
    description: str


class ChangelogEntry(BaseModel):
    """Changelog entry response schema."""

    version: str
    date: str
    date_display: str
    changes: list[ChangeEntry]
