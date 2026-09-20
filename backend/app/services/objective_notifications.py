"""Compatibility facade — canonical implementation: ``app.services.progression.objectives.notifications``."""

from app.services.progression.objectives.notifications import (
    handle_objective_completed,
    register_objective_event_handlers,
)

__all__ = ["handle_objective_completed", "register_objective_event_handlers"]
