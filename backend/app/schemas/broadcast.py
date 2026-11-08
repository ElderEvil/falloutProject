"""Wire contracts for Vault Radio Hour broadcasts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class BroadcastRead(BaseModel):
    id: UUID
    title: str
    script: str
    audio_url: str | None
    trigger: Literal["daily", "manual"]
    created_at: datetime
