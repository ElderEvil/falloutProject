"""Reward service for granting rewards when quests and objectives are completed.

Thin facade over the ``app.services.rewards`` domain package. ``RewardService``
keeps the public surface — and the ``reward_service`` singleton — stable for its
diverse callers (quest progression, objective evaluators, combat incident round,
and the storage/objective endpoints), delegating each entry point to the
role-named collaborators: ``items`` (item/dweller grants), ``resources``
(caps/resource/experience/medication grants), ``lunchbox`` (mint/roll/open),
and ``settlement`` (quest/objective settlement and reward dispatch).
"""

from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.objective import Objective
from app.models.quest import Quest
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.rewards import items, lunchbox, pet_carrier, resources, settlement


class RewardService:
    """Service for processing and granting quest/objective rewards."""

    async def grant_caps(
        self, db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = True
    ) -> dict[str, Any]:
        return await resources.grant_caps(db_session, vault_id, amount, emit_event=emit_event)

    async def grant_item(
        self, db_session: AsyncSession, vault_id: UUID4, item_data: dict[str, Any], *, emit_event: bool = True
    ) -> dict[str, Any]:
        return await items.grant_item(db_session, vault_id, item_data, emit_event=emit_event)

    async def grant_dweller(
        self, db_session: AsyncSession, vault_id: UUID4, dweller_template: dict[str, Any]
    ) -> dict[str, Any]:
        return await items.grant_dweller(db_session, vault_id, dweller_template)

    async def grant_resource(
        self, db_session: AsyncSession, vault_id: UUID4, resource_type: str, amount: int
    ) -> dict[str, Any]:
        return await resources.grant_resource(db_session, vault_id, resource_type, amount)

    async def grant_experience(self, db_session: AsyncSession, dweller_ids: list[UUID4], amount: int) -> dict[str, Any]:
        return await resources.grant_experience(db_session, dweller_ids, amount)

    async def grant_stimpak(
        self, db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = True
    ) -> dict[str, Any]:
        """Grant stimpaks to random dweller in vault."""
        return await resources.grant_stimpak(db_session, vault_id, amount, emit_event=emit_event)

    async def grant_radaway(
        self, db_session: AsyncSession, vault_id: UUID4, amount: int, *, emit_event: bool = False
    ) -> dict[str, Any]:
        """Grant radaways to random dweller in vault."""
        return await resources.grant_radaway(db_session, vault_id, amount, emit_event=emit_event)

    async def grant_lunchbox(self, db_session: AsyncSession, vault_id: UUID4, amount: int = 1) -> dict[str, Any]:
        """Mint unopened lunchbox Items; contents roll when the player opens each one."""
        return await lunchbox.grant_lunchbox(db_session, vault_id, amount)

    async def open_lunchbox(self, db_session: AsyncSession, vault_id: UUID4, item_id: UUID4) -> dict[str, Any]:
        """Consume one unopened lunchbox and roll its contents."""
        return await lunchbox.open_lunchbox(db_session, vault_id, item_id)

    async def grant_pet_carrier(self, db_session: AsyncSession, vault_id: UUID4, amount: int = 1) -> dict[str, Any]:
        """Mint unopened pet carriers; the pet rolls only when the player opens one."""
        return await pet_carrier.grant_pet_carrier(db_session, vault_id, amount)

    async def open_pet_carrier(self, db_session: AsyncSession, vault_id: UUID4, item_id: UUID4) -> dict[str, Any]:
        """Consume one unopened pet carrier and add its pet to storage."""
        return await pet_carrier.open_pet_carrier(db_session, vault_id, item_id)

    async def process_quest_rewards(
        self, db_session: AsyncSession, vault_id: UUID4, quest: Quest
    ) -> list[dict[str, Any]]:
        return await settlement.process_quest_rewards(db_session, vault_id, quest)

    async def process_objective_reward(
        self, db_session: AsyncSession, vault_id: UUID4, objective: VaultObjectiveProgressLink
    ) -> dict[str, Any]:
        return await settlement.process_objective_reward(db_session, vault_id, objective)

    async def claim_objective_reward(
        self, db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4
    ) -> VaultObjectiveProgressLink:
        """Claim an assigned, earned reward atomically and reject repeat claims."""
        return await settlement.claim_objective_reward(db_session, objective_id, vault_id)

    async def settle_objective_completion(
        self, db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4
    ) -> Objective:
        """Mark an objective complete for a vault and deliver its reward in one transaction."""
        return await settlement.settle_objective_completion(db_session, objective_id, vault_id)

    async def settle_objective_progress(
        self, db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4, progress: int
    ) -> VaultObjectiveProgressLink:
        """Update earned progress without paying the reward; owners claim separately."""
        return await settlement.settle_objective_progress(db_session, objective_id, vault_id, progress)


reward_service = RewardService()
