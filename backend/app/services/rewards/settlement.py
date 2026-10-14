"""Quest and objective reward settlement.

Processing quest/objective rewards rolls each reward's chance, dispatches the
parsed reward to the grant collaborators (``items``, ``resources``,
``lunchbox``), and settles objective completion inside a single deferred
transaction. ``_parse_objective_reward`` turns the objective reward string into
a ``(RewardType, data)`` payload. Public entry points are called through the
facade in ``app.services.reward_service``.
"""

import logging
import random
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.crud.objective import objective_crud
from app.crud.vault import vault as vault_crud
from app.models.objective import Objective
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.guidance import current_state_progress
from app.services.rewards import items, lunchbox, resources
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException
from app.utils.reward_delivery import defer_reward_delivery

logger = logging.getLogger(__name__)


async def process_quest_rewards(db_session: AsyncSession, vault_id: UUID4, quest: Quest) -> list[dict[str, Any]]:
    granted_rewards: list[dict[str, Any]] = []

    rewards: list[QuestReward] = quest.quest_rewards
    if not rewards:
        logger.info(f"Quest '{quest.title}' has no rewards to process")
        return granted_rewards

    for reward in rewards:
        if reward.reward_chance < 1.0 and random.random() > reward.reward_chance:
            logger.debug(f"Reward roll failed for quest '{quest.title}' (chance={reward.reward_chance:.3f})")
            continue

        reward_data = reward.reward_data | (reward.item_data or {})
        result = await _process_single_reward(db_session, vault_id, reward.reward_type, reward_data)
        granted_rewards.append(result)

    logger.info(f"Processed {len(granted_rewards)}/{len(rewards)} rewards for quest '{quest.title}'")
    return granted_rewards


async def process_objective_reward(
    db_session: AsyncSession, vault_id: UUID4, objective: VaultObjectiveProgressLink
) -> dict[str, Any]:
    objective_obj = await objective_crud.get(db_session, id=objective.objective_id)
    reward_str = objective.reward_snapshot or objective_obj.reward

    reward_type, reward_data = _parse_objective_reward(reward_str)
    result = await _process_single_reward(db_session, vault_id, reward_type, reward_data, emit_event=False)
    logger.info(f"Processed objective reward '{reward_str}' for vault {vault_id}")
    return result


async def claim_objective_reward(
    db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4
) -> VaultObjectiveProgressLink:
    """Claim an assigned, earned reward atomically and reject repeat claims."""
    await vault_crud.lock_for_update(db_session, vault_id)
    link = await objective_crud.get_link_for_update(db_session, objective_id, vault_id)
    if link is None:
        raise ResourceNotFoundException(Objective, objective_id)
    if link.is_completed:
        raise ResourceConflictException("Objective reward already claimed")
    objective = await objective_crud.get(db_session, objective_id)
    progress = link.progress
    if objective.category == ObjectiveCategoryEnum.STARTER:
        if await objective_crud.get_current_starter_id(db_session, vault_id) != objective_id:
            raise ValidationException("Claim the current guided objective before moving to the next step")
        progress = max(progress, await current_state_progress(db_session, vault_id, objective))
    if progress < link.total:
        raise ValidationException("Complete the objective before claiming its reward")
    link.progress = max(link.progress, min(progress, link.total))
    try:
        await _settle_objective_link(db_session, vault_id, link)
    except Exception:
        await db_session.rollback()
        raise
    return link


async def settle_objective_completion(db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4) -> Objective:
    """Mark an objective complete for a vault and deliver its reward in one transaction."""
    await vault_crud.lock_for_update(db_session, vault_id)
    objective = await objective_crud.get(db_session, objective_id)
    link = await objective_crud.get_link_for_update(db_session, objective_id, vault_id)
    if not link:
        link = VaultObjectiveProgressLink(vault_id=vault_id, objective_id=objective_id, progress=0, total=1)
        db_session.add(link)
    elif link.is_completed:
        raise ResourceConflictException("Already completed")

    link.progress = link.total
    await _settle_objective_link(db_session, vault_id, link)
    return objective


async def settle_objective_progress(
    db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4, progress: int
) -> VaultObjectiveProgressLink:
    """Update earned progress without paying the reward; owners claim separately."""
    link = await objective_crud.get_link_for_update(db_session, objective_id, vault_id)
    if not link:
        objective = await objective_crud.get(db_session, objective_id)
        link = VaultObjectiveProgressLink(
            vault_id=vault_id,
            objective_id=objective_id,
            progress=progress,
            total=objective.target_amount if objective else 1,
        )
        db_session.add(link)
    elif link.is_completed:
        return link

    link.progress = progress
    if link.progress >= link.total and link.reward_snapshot is None:
        objective = await objective_crud.get(db_session, objective_id)
        link.reward_snapshot = objective.reward
    await db_session.commit()
    await db_session.refresh(link)
    return link


async def _settle_objective_link(db_session: AsyncSession, vault_id: UUID4, link: VaultObjectiveProgressLink) -> None:
    """Complete the link and deliver its reward inside a single deferred transaction."""
    link.is_completed = True
    async with defer_reward_delivery(db_session):
        await process_objective_reward(db_session, vault_id, link)
        await db_session.commit()


async def _process_single_reward(
    db_session: AsyncSession,
    vault_id: UUID4,
    reward_type: RewardType | str,
    reward_data: dict[str, Any],
    *,
    emit_event: bool = True,
) -> dict[str, Any]:
    reward_type_str = reward_type.value if isinstance(reward_type, RewardType) else reward_type

    match reward_type_str:
        case RewardType.CAPS:
            return await resources.grant_caps(db_session, vault_id, reward_data.get("amount", 0), emit_event=emit_event)
        case RewardType.ITEM:
            return await items.grant_item(db_session, vault_id, reward_data, emit_event=emit_event)
        case RewardType.DWELLER:
            return await items.grant_dweller(db_session, vault_id, reward_data)
        case RewardType.RESOURCE:
            return await resources.grant_resource(
                db_session, vault_id, reward_data.get("resource_type", "food"), reward_data.get("amount", 0)
            )
        case RewardType.EXPERIENCE:
            return await resources.grant_experience(
                db_session, reward_data.get("dweller_ids", []), reward_data.get("amount", 0)
            )
        case RewardType.STIMPAK:
            return await resources.grant_stimpak(
                db_session, vault_id, reward_data.get("amount", 1), emit_event=emit_event
            )
        case RewardType.RADAWAY:
            return await resources.grant_radaway(
                db_session, vault_id, reward_data.get("amount", 1), emit_event=emit_event
            )
        case RewardType.LUNCHBOX:
            return await lunchbox.grant_lunchbox(db_session, vault_id, reward_data.get("amount", 1))
        case _:
            msg = f"Unknown reward type: {reward_type_str}"
            raise ValueError(msg)


def _parse_objective_reward(reward_str: str) -> tuple[RewardType, dict[str, Any]]:
    """Parse objective reward string into (RewardType, data).

    Formats: "100 caps", "50 food", "200 xp", "weapon:Laser Pistol", "outfit:Vault Suit", "dweller:Wanderer"
    """
    reward_str = reward_str.strip()

    parts = reward_str.split(maxsplit=1)
    if len(parts) == 2 and parts[0].isdigit():
        amount = int(parts[0])
        reward_name = parts[1].lower().strip()

        if reward_name == "caps":
            return RewardType.CAPS, {"amount": amount}
        if reward_name in ("food", "water", "power"):
            return RewardType.RESOURCE, {"resource_type": reward_name, "amount": amount}
        if reward_name in ("xp", "experience"):
            return RewardType.EXPERIENCE, {"amount": amount, "dweller_ids": []}
        if reward_name in ("lunchbox", "lunchboxes"):
            return RewardType.LUNCHBOX, {"amount": amount}

    if ":" in reward_str:
        prefix, value = reward_str.split(":", 1)
        prefix = prefix.lower().strip()
        value = value.strip()

        if prefix == "weapon":
            return RewardType.ITEM, {"item_type": "weapon", "name": value, "rarity": "common"}
        if prefix == "outfit":
            return RewardType.ITEM, {"item_type": "outfit", "name": value, "rarity": "common"}
        if prefix == "dweller":
            return RewardType.DWELLER, {"first_name": value, "rarity": "common"}

    msg = f"Cannot parse objective reward string: '{reward_str}'"
    raise ValueError(msg)
