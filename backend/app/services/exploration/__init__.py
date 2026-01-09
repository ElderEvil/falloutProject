"""Exploration services module."""

from app.services.exploration.coordinator import ExplorationCoordinator

# Create singleton instance
exploration_coordinator = ExplorationCoordinator()

__all__ = ["ExplorationCoordinator", "exploration_coordinator"]
