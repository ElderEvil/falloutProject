"""Pet carrier minting and opening.

A sealed carrier holds exactly one pet. Opening rolls the pet before the carrier
is deleted, so an empty catalog cannot consume the item. The carrier frees one
storage slot and the pet takes one, so a full vault never blocks the reveal.
"""

import logging
import random
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RarityEnum
from app.core.game_config import game_config
from app.models.item import Item
from app.schemas.pet import PetRead
from app.services import catalog_service
from app.services.rewards import items
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.item_factory import build_pet
from app.utils.reward_delivery import defer_reward_delivery, persist_reward_change

logger = logging.getLogger(__name__)

PET_CARRIER_ITEM_TYPE = "pet_carrier"
PET_CARRIER_NAME = "Pet Carrier"
_RARITY_ORDER = (RarityEnum.LEGENDARY, RarityEnum.RARE, RarityEnum.COMMON)


def _pool_for(rarity: RarityEnum) -> list[dict]:
    return [pet for pet in catalog_service.load_pets() if str(pet.get("rarity", "")).lower() == rarity.value]


def _roll_pet() -> dict:
    weights = game_config.container.pet_carrier
    rarities = [RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY]
    chosen = random.choices(rarities, weights=[weights.common, weights.rare, weights.legendary], k=1)[0]
    for rarity in _RARITY_ORDER[_RARITY_ORDER.index(chosen) :]:
        pool = _pool_for(rarity)
        if pool:
            return random.choice(pool)
    raise ValidationException("No pets are available in the carrier pool")


async def grant_pet_carrier(db_session: AsyncSession, vault_id: UUID4, amount: int = 1) -> dict[str, Any]:
    """Mint unopened pet carriers; the pet rolls only when the player opens one."""
    return await items.grant_item(
        db_session,
        vault_id,
        {"item_type": PET_CARRIER_ITEM_TYPE, "name": PET_CARRIER_NAME, "rarity": "common", "amount": amount},
    )


async def open_pet_carrier(db_session: AsyncSession, vault_id: UUID4, item_id: UUID4) -> dict[str, Any]:
    """Consume one pet carrier and add its rolled pet to storage."""
    from app.crud.storage import get_unopened_container

    item = await get_unopened_container(db_session, item_id, vault_id, item_type=PET_CARRIER_ITEM_TYPE)
    if item is None:
        raise ResourceNotFoundException(Item, item_id)
    pet_data = _roll_pet()
    storage_obj = await items._ensure_storage(db_session, vault_id, 0)
    async with defer_reward_delivery(db_session):
        await db_session.delete(item)
        pet = build_pet(pet_data, pet_data["rarity"], storage_obj.id)
        db_session.add(pet)
        await persist_reward_change(db_session)
        await db_session.commit()
    await db_session.refresh(pet)
    logger.info("Opened pet carrier %s in vault %s: %s (%s)", item_id, vault_id, pet.name, pet.rarity.value)
    return {"reward_type": PET_CARRIER_ITEM_TYPE, "pet": PetRead.model_validate(pet)}
