"""Wire contracts for Vault Radio Hour broadcasts."""

from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel


class BroadcastRead(BaseModel):
    id: UUID4
    title: str
    script: str
    audio_url: str | None
    trigger: Literal["daily", "manual"]
    created_at: datetime
