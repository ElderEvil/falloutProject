"""Space-free admission policy for vault storage.

Nuka-Cola bottles are deliberately storage-space free (game-design mutation). Both
sides of the ledger import the predicate from here: crud.storage excludes them from
counting, rewards.items skips the capacity check when granting.
"""

import re

from app.core.enums import ItemTypeEnum

NUKA_COLA_LIKE = "%nuka%"
_NUKA_COLA_RE = re.compile(r"nuka", re.IGNORECASE)


def is_nuka_cola_consumable(item_type: str | None, name: str | None) -> bool:
    """True for consumable items named like Nuka-Cola — the space-free rule."""
    is_consumable = (item_type or "").lower() == ItemTypeEnum.CONSUMABLE.value.lower()
    return is_consumable and _NUKA_COLA_RE.search(name or "") is not None
