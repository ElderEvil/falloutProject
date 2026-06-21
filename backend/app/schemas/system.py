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


class InfoResponse(BaseModel):
    """Application information response schema."""

    app_version: str
    api_version: str
    environment: str
    python_version: str
    build_date: str


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
