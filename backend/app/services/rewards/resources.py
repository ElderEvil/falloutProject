"""Cap, resource, experience, and medication grants for reward settlement.

Each grant is one transaction owner: caps and resources deposit into the vault,
experience levels dwellers, and stimpak/radaway medication rides the dweller
stock path so it stays usable for treatment. Deferred delivery defers the
commit (see ``app.utils.reward_delivery``). Public entry points are called
through the facade in ``app.services.reward_service``.
"""

import logging
import random
from typing import Any
from uuid import UUID

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RewardType
from app.core.event_bus import GameEvent, event_bus
from app.crud.storage import storage as storage_crud
from app.models.storage import Storage
from app.options.races import can_use_radaway
from app.services.user_service import user_service
from app.utils.reward_delivery import persist_reward_change, reward_delivery_is_deferred

logger = logging.getLogger(__name__)


async def grant_caps(
    db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = True
) -> dict[str, Any]:
    from app.crud.vault import vault as vault_crud
    from app.services.vault_service import vault_service

    vault_obj = await vault_crud.get(db_session, id=vault_id)
    if reward_delivery_is_deferred(db_session):
        credited = min(vault_obj.bottle_caps + amount, 999_999) - vault_obj.bottle_caps
        vault_obj.bottle_caps += credited
        await persist_reward_change(db_session, vault_obj)
        await user_service.record_vault_statistic(db_session, vault_id, "total_caps_earned", credited, commit=False)
    else:
        await vault_service.deposit_caps(
            db_session=db_session, vault_obj=vault_obj, amount=amount, emit_event=emit_event
        )

    logger.info(f"Granted {amount} caps to vault {vault_id}")
    return {"reward_type": RewardType.CAPS, "amount": amount}


async def grant_resource(db_session: AsyncSession, vault_id: UUID4, resource_type: str, amount: int) -> dict[str, Any]:
    from app.crud.vault import vault as vault_crud

    vault_obj = await vault_crud.get(db_session, id=vault_id)
    deferred = reward_delivery_is_deferred(db_session)

    match resource_type.lower():
        case "food":
            new_value = min(vault_obj.food + amount, vault_obj.food_max)
            field = "food"
        case "water":
            new_value = min(vault_obj.water + amount, vault_obj.water_max)
            field = "water"
        case "power":
            new_value = min(vault_obj.power + amount, vault_obj.power_max)
            field = "power"
        case _:
            msg = f"Invalid resource_type: {resource_type}. Must be 'food', 'water', or 'power'"
            raise ValueError(msg)

    if deferred:
        setattr(vault_obj, field, new_value)
        await persist_reward_change(db_session, vault_obj)
    else:
        await vault_crud.update(db_session, id=vault_id, obj_in={field: new_value})

    logger.info(f"Granted {amount} {resource_type} to vault {vault_id}")
    return {"reward_type": RewardType.RESOURCE, "resource_type": resource_type, "amount": amount}


async def grant_experience(db_session: AsyncSession, dweller_ids: list[UUID4], amount: int) -> dict[str, Any]:
    from app.crud.dweller import dweller as dweller_crud
    from app.services.dweller_service import dweller_service

    leveled_up: list[str] = []
    granted_to: list[str] = []

    for raw_id in dweller_ids:
        dweller_id = UUID(raw_id) if isinstance(raw_id, str) else raw_id
        dweller_obj = await dweller_crud.get(db_session, id=dweller_id)
        old_level = dweller_obj.level
        await dweller_service.add_experience(db_session, dweller_obj, amount)
        granted_to.append(str(dweller_id))

        await db_session.refresh(dweller_obj)
        if dweller_obj.level > old_level:
            leveled_up.append(str(dweller_id))

    logger.info(f"Granted {amount} XP to {len(granted_to)} dweller(s), {len(leveled_up)} leveled up")
    return {
        "reward_type": RewardType.EXPERIENCE,
        "amount": amount,
        "dweller_ids": granted_to,
        "leveled_up": leveled_up,
    }


async def grant_stimpak(
    db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = True
) -> dict[str, Any]:
    """Grant stimpaks to random dweller in vault."""
    return await _grant_medication(db_session, vault_id, amount, RewardType.STIMPAK, "stimpack", emit_event=emit_event)


async def grant_radaway(
    db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = False
) -> dict[str, Any]:
    """Grant radaways to random dweller in vault."""
    return await _grant_medication(db_session, vault_id, amount, RewardType.RADAWAY, "radaway", emit_event=emit_event)


async def _grant_medication(
    db_session: AsyncSession,
    vault_id: UUID4,
    amount: int,
    reward_type: RewardType,
    stock_field: str,
    *,
    emit_event: bool = False,
) -> dict[str, Any]:
    from app.crud.dweller import dweller as dweller_crud

    dwellers = await dweller_crud.get_multi_by_vault(db_session, vault_id=vault_id, skip=0, limit=100)
    if not dwellers:
        logger.warning(f"No dwellers found in vault {vault_id} to grant {reward_type}s")
        return {"reward_type": reward_type, "amount": 0, "message": "No dwellers found"}

    if stock_field == "radaway":
        dwellers = [dweller for dweller in dwellers if can_use_radaway(dweller)]

    if dwellers:
        recipient = random.choice(dwellers)
        setattr(recipient, stock_field, (getattr(recipient, stock_field) or 0) + amount)
        result = {"reward_type": reward_type, "amount": amount, "dweller_id": str(recipient.id)}
    else:
        recipient = await storage_crud.get_by_vault(db_session, vault_id) or Storage(vault_id=vault_id)
        recipient.radaway = (recipient.radaway or 0) + amount
        result = {"reward_type": reward_type, "amount": amount, "vault_id": str(vault_id)}

    await persist_reward_change(db_session, recipient)
    if emit_event and not reward_delivery_is_deferred(db_session):
        await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": reward_type, "amount": amount})

    logger.info("Granted %s %ss in vault %s", amount, reward_type, vault_id)
    return result


def _medication_kind(name: str) -> str | None:
    """Map a medication item name to its stock kind; None for non-medication."""
    normalized = name.lower()
    if "radaway" in normalized or "rad-away" in normalized or "rad away" in normalized:
        return "radaway"
    if "stimpak" in normalized:
        return "stimpak"
    return None
