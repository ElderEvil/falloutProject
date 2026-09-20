"""Compatibility facade — canonical implementation: ``app.services.progression.quests.service``."""

from app.services.progression.quests.availability import (
    CHAIN_LOCK_REASON,
    OFFICE_LOCK_REASON,
    OFFICE_ROOM_TYPE,
    REVEAL_MARGIN,
    QuestAvailability,
)
from app.services.progression.quests.service import QuestService, quest_service

__all__ = [
    "CHAIN_LOCK_REASON",
    "OFFICE_LOCK_REASON",
    "OFFICE_ROOM_TYPE",
    "REVEAL_MARGIN",
    "QuestAvailability",
    "QuestService",
    "quest_service",
]
