"""Settings endpoints for exposing game configuration."""

from typing import Any

from fastapi import APIRouter

from app.core.game_config import game_config
from app.models.incident import IncidentType

router = APIRouter()


@router.get("/game-balance")
async def get_game_balance_settings() -> dict[str, Any]:
    """
    Get current game balance configuration (read-only).

    This endpoint exposes all game balance constants that can be tuned via
    environment variables. Useful for debugging and future admin panels.

    Returns:
        Dictionary containing all game balance settings organized by category
    """
    return {
        "game_loop": game_config.game_loop.model_dump(),
        "incident": {
            **game_config.incident.model_dump(),
            "difficulty_ranges": {
                incident_type.value: game_config.incident.get_difficulty_range(incident_type)
                for incident_type in IncidentType
            },
            "spawn_weights": {
                incident_type.value: weight
                for incident_type, weight in game_config.incident.get_spawn_weights().items()
            },
        },
        "combat": game_config.combat.model_dump(),
        "health": game_config.health.model_dump(),
        "happiness": game_config.happiness.model_dump(),
        "training": game_config.training.model_dump(),
        "resource": game_config.resource.model_dump(),
        "relationship": game_config.relationship.model_dump(),
        "breeding": game_config.breeding.model_dump(),
        "leveling": game_config.leveling.model_dump(),
        "radio": game_config.radio.model_dump(),
    }
