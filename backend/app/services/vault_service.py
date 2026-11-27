"""Vault facade: owns the creation transaction, delegates seeding/economy/reads."""

import logging
from collections.abc import Sequence
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.core.game_data import get_static_game_data
from app.crud.broadcast import get_audio_keys_for_vault
from app.crud.storage import storage as storage_crud
from app.crud.vault import vault as vault_crud
from app.models.vault import Vault
from app.schemas.vault import (
    MedicalTransferResponse,
    VaultCreate,
    VaultNumber,
    VaultReadWithNumbers,
    VaultUpdate,
)
from app.services.broadcast_service import delete_audio_keys
from app.services.resource_manager_service import compute_medical_capacity
from app.services.rewards.starter_residents import starter_reward_overrides
from app.services.vault import economy, reads, seeding
from app.services.vault.scenario_service import vault_scenario_service


class VaultService:
    """Service for vault initialization and management."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def list_vaults(self, db_session: AsyncSession, *, skip: int = 0, limit: int = 100) -> Sequence[Vault]:
        return await vault_crud.get_multi(db_session, skip=skip, limit=limit)

    async def update_vault(self, db_session: AsyncSession, vault_id: UUID, vault_data: VaultUpdate) -> Vault:
        """Update a vault; the service owns the commit."""
        vault = await vault_crud.update(db_session, vault_id, vault_data, commit=False)
        await db_session.commit()
        return vault

    async def initiate_vault(
        self,
        db_session: AsyncSession,
        obj_in: VaultNumber,
        user_id: UUID,
        is_boosted: bool = False,
    ) -> Vault:
        """Create a vault with its rooms and dwellers; is_boosted seeds the full build.

        Boosted adds radio/office/response station/arena, all seven training rooms, both crafting workshops,
        extra storage with junk stock, and a 36-dweller roster. Expedition test starts add living capacity
        and skip starter objectives. Player experiments use the standard layout with changed starting
        supplies or demographics.

        This is the operation's only transaction boundary: the vault row, its slot, storage, rooms,
        dwellers, training rows, objectives, themes and items are staged by CRUD with ``commit=False``
        and committed once here, so a late failure leaves no vault behind. Expedition scenario seeding
        runs after that commit as an explicitly multi-stage step: its vault survives a failed scenario
        setup, matching the expedition service's own durable-stage contract.
        """
        scenario = vault_scenario_service.resolve(obj_in.scenario, obj_in.number)
        expedition_start = scenario is not None and scenario.expedition
        is_boosted = is_boosted and (scenario is None or expedition_start)
        ration_divisor = scenario.ration_divisor if scenario else 1
        majority_gender = scenario.majority_gender if scenario else None
        reward_overrides = starter_reward_overrides(majority_gender)

        from app.crud.objective import objective_crud
        from app.services.progression.objectives.assignment import ObjectiveAssignmentService
        from app.services.progression.objectives.notifications import notify_objectives_refreshed
        from app.services.progression.objectives.refresh_service import ensure_current_objectives

        try:
            vault_db_obj = await vault_crud.create_with_user_id(
                db_session=db_session,
                obj_in=obj_in,
                user_id=user_id,
                scenario_key=scenario.key if scenario else None,
            )
            await vault_crud.create_storage(db_session=db_session, vault_id=vault_db_obj.id, commit=False)
            await db_session.refresh(vault_db_obj)

            game_data_store = await get_static_game_data()
            rooms = game_data_store.rooms
            prepared = seeding.prepare_initial_rooms(
                rooms, vault_db_obj.id, is_boosted, scenario_start=expedition_start
            )

            vault_db_obj, created = await seeding.create_initial_rooms(db_session, vault_db_obj, prepared, commit=False)
            created_production_rooms = created.production
            created_training_rooms = created.training
            created_misc_rooms = created.misc
            created_capacity_rooms = created.capacity

            vault_start = game_config.vault_start
            initial_power = int(vault_db_obj.power_max * vault_start.initial_resource_pct)
            initial_food = int(vault_db_obj.food_max * vault_start.initial_resource_pct) // ration_divisor
            initial_water = int(vault_db_obj.water_max * vault_start.initial_resource_pct) // ration_divisor

            vault_db_obj = await vault_crud.update(
                db_session=db_session,
                id=vault_db_obj.id,
                obj_in=VaultUpdate(
                    bottle_caps=vault_start.boosted_initial_caps if is_boosted else vault_db_obj.bottle_caps,
                    power=initial_power,
                    food=initial_food,
                    water=initial_water,
                ),
                commit=False,
            )

            # Set initial medical supplies on Storage (computed from Medbay/Science Lab rooms)
            all_rooms = created_production_rooms + created_capacity_rooms + created_training_rooms + created_misc_rooms
            medical_capacity = compute_medical_capacity(all_rooms)
            initial_stimpack = min(vault_start.initial_stimpaks, medical_capacity.get("stimpack", 0))
            initial_radaway = min(vault_start.initial_radaways, medical_capacity.get("radaway", 0))
            if initial_stimpack > 0 or initial_radaway > 0:
                await storage_crud.set_medical_supplies(
                    db_session, vault_db_obj.id, initial_stimpack, initial_radaway, commit=False
                )

            await seeding.create_initial_dwellers(
                db_session,
                vault_db_obj.id,
                created_production_rooms,
                created_training_rooms,
                created_misc_rooms,
                created_capacity_rooms,
                is_boosted,
                created_crafting_rooms=created.crafting,
                majority_gender=majority_gender,
            )

            if is_boosted:
                await seeding.create_boosted_legendary_dwellers(db_session, vault_db_obj.id, commit=False)

            await seeding.start_training_sessions(
                db_session, vault_db_obj.id, created_training_rooms, is_boosted, commit=False
            )

            assigned = await objective_crud.assign_initial(
                db_session,
                vault_db_obj.id,
                is_boosted=is_boosted or expedition_start,
                starter_reward_overrides=reward_overrides,
                commit=False,
            )
            if assigned == 0:
                self.logger.warning("No objectives found for vault %s", vault_db_obj.id)

            refreshed = await ensure_current_objectives(db_session, vault_db_obj.id, commit=False)

            if is_boosted:
                await seeding.seed_boosted_theme_unlocks(db_session, vault_db_obj.id, commit=False)

            await seeding.create_initial_items(db_session, vault_db_obj.id, is_boosted, commit=False)

            await db_session.commit()
        except Exception:
            ObjectiveAssignmentService.discard_pending_completions(db_session)
            await db_session.rollback()
            raise
        await db_session.refresh(vault_db_obj)

        # Post-commit delivery: completion notices only describe rows this transaction made durable.
        await ObjectiveAssignmentService(db_session).notify_completions(vault_db_obj.id)
        if refreshed:
            await notify_objectives_refreshed(db_session, vault_db_obj.id, refreshed)

        if scenario is not None and scenario.expedition:
            await vault_scenario_service.seed(db_session, vault_db_obj, scenario)

        return vault_db_obj

    async def create_vault(self, *, db_session: AsyncSession, obj_in: VaultCreate, user_id: UUID) -> Vault:
        """Create a vault for an administrator and claim its atlas slot in one transaction."""
        try:
            vault = await vault_crud.create_with_user_id(db_session=db_session, obj_in=obj_in, user_id=user_id)
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise
        await db_session.refresh(vault)
        return vault

    async def delete_vault(self, db_session: AsyncSession, vault_id: UUID, *, soft: bool = True) -> Vault:
        """Delete a vault; hard deletion also removes its stored broadcast audio."""
        audio_keys = [] if soft else await get_audio_keys_for_vault(db_session, vault_id)
        vault = await vault_crud.delete(db_session, vault_id, soft=soft)
        if audio_keys:
            await delete_audio_keys(audio_keys)
        return vault

    async def update_vault_resources(self, db_session: AsyncSession, vault_id: UUID) -> Vault:
        return await economy.update_vault_resources(db_session, vault_id)

    async def transfer_medical_supplies(
        self,
        db_session: AsyncSession,
        vault: Vault,
        dweller_id: UUID,
        stimpaks: int,
        radaways: int,
    ) -> MedicalTransferResponse:
        """Transfer medical supplies from vault storage to a dweller's inventory.

        Dwellers can carry max 15 stimpaks and 15 radaways each.
        """
        return await economy.transfer_medical_supplies(db_session, vault, dweller_id, stimpaks, radaways)

    async def recalculate_vault_attributes(
        self,
        *,
        db_session: AsyncSession,
        vault_obj: Vault,
        room_obj,
        action,
        previous_capacity: int | None = None,
        commit: bool = True,
    ) -> Vault:
        """Recalculate the vault attributes based on the newly added or removed room."""
        return await economy.recalculate_vault_attributes(
            db_session=db_session,
            vault_obj=vault_obj,
            room_obj=room_obj,
            action=action,
            previous_capacity=previous_capacity,
            commit=commit,
        )

    async def is_enough_dwellers(
        self, *, db_session: AsyncSession, vault_id: UUID, population_required: int | None
    ) -> bool:
        return await economy.is_enough_dwellers(
            db_session=db_session, vault_id=vault_id, population_required=population_required
        )

    @staticmethod
    async def is_enough_population_space(*, db_session: AsyncSession, vault_id: UUID, space_required: int) -> bool:
        """Check if the vault has enough space to perform an operation.

        Only assigned dwellers occupy living space.
        """
        return await economy.is_enough_population_space(
            db_session=db_session, vault_id=vault_id, space_required=space_required
        )

    async def deposit_caps(
        self,
        *,
        db_session: AsyncSession,
        vault_obj: Vault,
        amount: int,
        commit: bool = True,
        emit_event: bool = True,
        track_earnings: bool = True,
    ) -> int:
        """Deposit the specified amount to the vault's bottle caps as part of a revenue operation.

        Returns the amount actually credited (less than requested when the cap is hit).
        """
        return await economy.deposit_caps(
            db_session=db_session,
            vault_obj=vault_obj,
            amount=amount,
            commit=commit,
            emit_event=emit_event,
            track_earnings=track_earnings,
        )

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int, commit: bool = True):
        """Withdraw the specified amount from the vault's bottle caps as part of a spending operation.

        Pass ``commit=False`` to compose the deduction with other writes into one transaction.
        """
        return await economy.withdraw_caps(db_session=db_session, vault_obj=vault_obj, amount=amount, commit=commit)

    async def get_vaults_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, user_id: UUID
    ) -> list[VaultReadWithNumbers]:
        return await reads.get_vaults_with_room_and_dweller_count(db_session=db_session, user_id=user_id)

    async def get_vault_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, vault_id: UUID
    ) -> VaultReadWithNumbers:
        """Fetch a single vault with room/dweller counts and resource warnings."""
        return await reads.get_vault_with_room_and_dweller_count(db_session=db_session, vault_id=vault_id)


vault_service = VaultService()
