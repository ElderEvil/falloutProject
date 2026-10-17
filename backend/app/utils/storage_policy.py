"""Space-free admission policy for vault storage.

Nuka-Cola bottles are deliberately storage-space free (game-design mutation,
documented in ``docs/backend/GAME_MECHANICS.md``). The rule has to hold on both
sides of the storage ledger: counting stored rows (``crud.storage``) excludes
them, and granting new bottles (``rewards.items``) skips the capacity check.
Both sides import the predicate from here so the policy cannot drift.
"""

import re

from app.core.enums import ItemTypeEnum

NUKA_COLA_LIKE = "%nuka%"
_NUKA_COLA_RE = re.compile(r"nuka", re.IGNORECASE)


def is_nuka_cola_consumable(item_type: str | None, name: str | None) -> bool:
    """True for consumable items named like Nuka-Cola — the space-free rule."""
    is_consumable = (item_type or "").lower() == ItemTypeEnum.CONSUMABLE.value.lower()
    return is_consumable and _NUKA_COLA_RE.search(name or "") is not None
