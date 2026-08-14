"""Pure resource-status helpers shared by read and tick flows."""

from collections.abc import Mapping

from app.core.game_config import game_config
from app.models.vault import Vault
from app.schemas.vault import ResourceLevelWarning


def get_resource_warnings(vault: Vault, resources: Mapping[str, float]) -> list[ResourceLevelWarning]:
    """Return player-facing warnings for the supplied primary resource levels."""
    warnings = []
    for resource, maximum, label in (
        ("power", vault.power_max, "Power"),
        ("food", vault.food_max, "Food"),
        ("water", vault.water_max, "Water"),
    ):
        if resources[resource] < maximum * game_config.resource.critical_threshold:
            warnings.append(ResourceLevelWarning(type=f"critical_{resource}", message=f"{label} critically low!"))
        elif resources[resource] < maximum * game_config.resource.low_threshold:
            warnings.append(ResourceLevelWarning(type=f"low_{resource}", message=f"{label} running low"))
    return warnings
