"""Wire contracts for Vault Radio Hour broadcasts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.utils.serialize_types import UTCDateTimeJSON


class BroadcastRead(BaseModel):
    id: UUID
    title: str
    script: str
    audio_url: str | None
    trigger: Literal["daily", "manual"]
    created_at: UTCDateTimeJSON
