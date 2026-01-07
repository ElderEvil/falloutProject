"""Game state model for tracking vault game loop sessions."""

from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class GameStateBase(SQLModel):
    """Base model for game state tracking."""

    last_tick_time: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True, description="Whether the vault game loop is active")
    is_paused: bool = Field(default=False, description="Whether the vault is manually paused by player")
    total_game_time: int = Field(default=0, ge=0, description="Total seconds the vault has been active")
    paused_at: datetime | None = Field(default=None, description="When the vault was last paused")
    resumed_at: datetime | None = Field(default=None, description="When the vault was last resumed")


class GameState(BaseUUIDModel, GameStateBase, TimeStampMixin, table=True):
    """Game state model linked to a specific vault."""

    vault_id: UUID4 = Field(foreign_key="vault.id", unique=True, index=True, ondelete="CASCADE")

    def calculate_offline_time(self) -> int:
        """Calculate seconds since last tick."""
        return int((datetime.utcnow() - self.last_tick_time).total_seconds())

    def pause(self) -> None:
        """Pause the game state."""
        self.is_paused = True
        self.paused_at = datetime.utcnow()

    def resume(self) -> None:
        """Resume the game state."""
        self.is_paused = False
        self.resumed_at = datetime.utcnow()

    def update_tick(self, seconds_passed: int) -> None:
        """Update the game state after a tick."""
        self.last_tick_time = datetime.utcnow()
        self.total_game_time += seconds_passed
