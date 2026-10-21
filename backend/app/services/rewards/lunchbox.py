"""Lunchbox minting, rolling, and opening.

``grant_lunchbox`` mints unopened lunchbox Items; their contents only roll when
the player opens each one. Opening consumes the box, verifies storage space
first (a full storage fails cleanly without losing the box), and settles the
whole opening in one deferred transaction. Public entry points are called
through the facade in ``app.services.reward_service``.
"""

import logging
import random
from typing import Any
from uuid import UUID

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import GenderEnum, RarityEnum
from app.models.item import Item
from app.models.quest_reward import RewardType
from app.services.rewards import items
from app.utils.exceptions import ResourceNotFoundException
from app.utils.item_factory import build_outfit, build_weapon
from app.utils.reward_delivery import defer_reward_delivery, persist_reward_change

logger = logging.getLogger(__name__)

_LUNCHBOX_ITEM_COUNT = 3


def _lunchbox_common_dweller_data(level: int, rarity: RarityEnum) -> dict[str, Any]:
    """Build the procedural fallback used for common lunchbox dwellers."""
    from app.utils.dwellers import get_gender_based_name

    gender = random.choice([GenderEnum.MALE, GenderEnum.FEMALE])
    return {
        "first_name": get_gender_based_name(gender),
        "last_name": random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller"]),
        "rarity": rarity,
        "level": level,
        "gender": gender,
    }


async def grant_lunchbox(db_session: AsyncSession, vault_id: UUID4, amount: int = 1) -> dict[str, Any]:
    """Mint unopened lunchbox Items; contents roll when the player opens each one."""
    return await items.grant_item(
        db_session,
        vault_id,
        {"item_type": "lunchbox", "name": "Lunchbox", "rarity": "common", "amount": amount},
    )


async def open_lunchbox(db_session: AsyncSession, vault_id: UUID4, item_id: UUID4) -> dict[str, Any]:
    """Consume one unopened lunchbox and roll its contents.

    Space for the rolled items is verified before the lunchbox row is
    consumed, so a full storage fails cleanly without losing the box.
    The box itself frees one slot, so only the two net additional slots
    are required. The whole opening settles in one deferred transaction.

    Raises:
        ResourceNotFoundException: Unknown, foreign-vault, or non-lunchbox row.
        ResourceConflictException: Storage cannot fit the rolled contents.
    """
    from app.crud.storage import get_unopened_lunchbox

    item = await get_unopened_lunchbox(db_session, item_id, vault_id)
    if item is None:
        raise ResourceNotFoundException(Item, item_id)
    storage_obj = await items._ensure_storage(db_session, vault_id, _LUNCHBOX_ITEM_COUNT - 1)
    async with defer_reward_delivery(db_session):
        await db_session.delete(item)
        granted_items, granted_dweller = await _roll_lunchbox_contents(db_session, vault_id, storage_obj.id)
        await persist_reward_change(db_session)
        await db_session.commit()

    logger.info(f"Opened lunchbox {item_id} in vault {vault_id}: {len(granted_items)} items, 1 dweller")
    return {
        "reward_type": RewardType.LUNCHBOX,
        "items": granted_items,
        "dweller": granted_dweller,
    }


async def _roll_lunchbox_contents(
    db_session: AsyncSession, vault_id: UUID4, storage_id: UUID4
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Roll 3 random items and 1 dweller into storage for a lunchbox opening."""
    from app.crud.dweller import dweller as dweller_crud
    from app.services import catalog_service as data_loader

    catalogs = {"weapon": data_loader.load_weapons(), "outfit": data_loader.load_outfits()}

    granted_items = []
    for _ in range(_LUNCHBOX_ITEM_COUNT):
        kind = random.choice(("weapon", "outfit"))
        rarity = random.choices(
            [RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY],
            weights=[0.7, 0.2, 0.1],
        )[0]
        pool = [entry for entry in catalogs[kind] if RarityEnum(str(entry.get("rarity", ""))).value == rarity.value]
        if not pool:
            logger.warning(f"No {rarity.value} {kind} in the catalog; skipping a lunchbox roll")
            continue
        entry = random.choice(pool)
        item = build_weapon(entry, rarity, storage_id) if kind == "weapon" else build_outfit(entry, rarity, storage_id)
        db_session.add(item)
        granted_items.append({"name": item.name, "type": kind, "rarity": rarity.value, "image_url": item.image_url})

    lunchbox_rarity = random.choices(
        [RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY], weights=[0.7, 0.2, 0.1]
    )[0]
    if lunchbox_rarity in (RarityEnum.RARE, RarityEnum.LEGENDARY):
        from app.utils.static_data import game_data_store

        active_names = await dweller_crud.lock_vault_for_template(db_session, vault_id)
        template = game_data_store.pick_template(lunchbox_rarity.value, exclude_names=active_names or None)
        if template is not None:
            granted_dweller = await items.grant_dweller(
                db_session, vault_id, {"template_id": template.template_id, "level": random.randint(1, 5)}
            )
        else:
            dweller_data = _lunchbox_common_dweller_data(random.randint(1, 5), RarityEnum.COMMON)
            granted_dweller = await items.grant_dweller(db_session, vault_id, dweller_data)
    else:
        dweller_data = _lunchbox_common_dweller_data(random.randint(1, 5), lunchbox_rarity)
        granted_dweller = await items.grant_dweller(db_session, vault_id, dweller_data)
    dweller = await dweller_crud.get(db_session, UUID(granted_dweller["dweller_id"]))
    granted_dweller.update(
        rarity=dweller.rarity,
        image_url=dweller.image_url,
        thumbnail_url=dweller.thumbnail_url,
    )
    return granted_items, granted_dweller
