from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel import Field, SQLModel


class VaultQuestCompletionLink(SQLModel, table=True):
    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    quest_id: UUID4 = Field(foreign_key="quest.id", primary_key=True)
    is_completed: bool = Field(default=False)
    is_reward_ready: bool = Field(default=False)
    is_visible: bool = Field(default=False)
    started_at: datetime | None = Field(default=None)
    duration_minutes: int | None = Field(default=None)

    # Return leg: set when the finished party starts travelling home; NULL means
    # the party is not travelling (either still questing or already home).
    return_started_at: datetime | None = Field(default=None)
    return_completes_at: datetime | None = Field(default=None)

    def is_returning(self) -> bool:
        """Whether the party is on the way home and has not arrived yet."""
        return self.return_completes_at is not None and not self.is_reward_ready and not self.is_completed

    def return_time_remaining_seconds(self) -> int:
        """Seconds until the party arrives home; 0 unless travelling."""
        if not self.is_returning() or self.return_completes_at is None:
            return 0
        return max(0, int((self.return_completes_at - datetime.utcnow()).total_seconds()))

    def start_return(self, return_minutes: int) -> None:
        """Begin the trip home, arriving in ``return_minutes``."""
        now = datetime.utcnow()
        self.return_started_at = now
        self.return_completes_at = now + timedelta(minutes=return_minutes)
