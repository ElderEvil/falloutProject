"""Service for vault initialization and resource management.

Thin facade over the ``app.services.vault`` domain package: ``VaultService``
owns the vault-creation transaction (``initiate_vault``) and delegates the
seeding/economy/reads seams to the role-named collaborators, keeping the
public singleton surface stable for existing callers.
"""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.core.game_data import get_static_game_data
from app.crud.storage import storage as storage_crud
from app.crud.vault import vault as vault_crud
from app.models.vault import Vault
from app.schemas.vault import MedicalTransferResponse, VaultNumber, VaultReadWithNumbers, VaultUpdate
from app.services.resource_manager import compute_medical_capacity
from app.services.vault import economy, reads, seeding


class VaultService:
    """Service for vault initialization and management."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def initiate_vault(
        self,
        db_session: AsyncSession,
        obj_in: VaultNumber,
        user_id: UUID4,
        is_boosted: bool = False,
        scenario_start: bool = False,
    ) -> Vault:
        """Create a new vault for a user and initialize it with essential rooms and dwellers.

        Standard vault includes:
        - Vault door and elevators (infrastructure)
        - Production rooms (power generator, diner, water treatment) with assigned dwellers
        - Storage room and 1 living room
        - 6 production workers, 2 living-quarter residents and their family child

        Boosted vault additionally includes:
        - Radio Studio, Overseer's Office, Response Station and Arena
        - All 7 training rooms (one for each SPECIAL stat)
        - A merged living room plus the base room (capacity for more than 32 dwellers)
        - Both crafting workshops staffed with two dwellers each
        - Three storage rooms and a stock of steel/leather/circuitry/cloth junk
          so timed crafting is testable, with 36 dwellers seeded (33 non-legendary
          plus a 3-dweller legendary roster; the fused size-6 generator's
          enlarged crew reuses the same slots, so the headcount is unchanged).

        Scenario starts use the boosted room layout and skip starter objectives,
        while keeping the requested normal population and resource start.
        """
        # Create vault and storage
        vault_db_obj = await vault_crud.create_with_user_id(db_session=db_session, obj_in=obj_in, user_id=user_id)
        await vault_crud.create_storage(db_session=db_session, vault_id=vault_db_obj.id)
        await db_session.refresh(vault_db_obj)

        # Prepare room data
        game_data_store = await get_static_game_data()
        rooms = game_data_store.rooms
        prepared = seeding.prepare_initial_rooms(rooms, vault_db_obj.id, is_boosted or scenario_start)

        # Create rooms and get created production/training/misc rooms
        vault_db_obj, created = await seeding.create_initial_rooms(db_session, vault_db_obj, prepared)
        created_production_rooms = created.production
        created_training_rooms = created.training
        created_misc_rooms = created.misc
        created_capacity_rooms = created.capacity

        # Set initial resources to the configured share of max capacity
        vault_start = game_config.vault_start
        initial_power = int(vault_db_obj.power_max * vault_start.initial_resource_pct)
        initial_food = int(vault_db_obj.food_max * vault_start.initial_resource_pct)
        initial_water = int(vault_db_obj.water_max * vault_start.initial_resource_pct)

        vault_db_obj = await vault_crud.update(
            db_session=db_session,
            id=vault_db_obj.id,
            obj_in=VaultUpdate(
                bottle_caps=vault_start.boosted_initial_caps if is_boosted else vault_db_obj.bottle_caps,
                power=initial_power,
                food=initial_food,
                water=initial_water,
            ),
        )

        # Set initial medical supplies on Storage (computed from Medbay/Science Lab rooms)
        all_rooms = created_production_rooms + created_capacity_rooms + created_training_rooms + created_misc_rooms
        medical_capacity = compute_medical_capacity(all_rooms)
        initial_stimpack = min(vault_start.initial_stimpaks, medical_capacity.get("stimpack", 0))
        initial_radaway = min(vault_start.initial_radaways, medical_capacity.get("radaway", 0))
        if initial_stimpack > 0 or initial_radaway > 0:
            await storage_crud.set_medical_supplies(db_session, vault_db_obj.id, initial_stimpack, initial_radaway)

        # Create and assign dwellers
        await seeding.create_initial_dwellers(
            db_session,
            vault_db_obj.id,
            created_production_rooms,
            created_training_rooms,
            created_misc_rooms,
            created_capacity_rooms,
            is_boosted,
            created_crafting_rooms=created.crafting,
        )

        if is_boosted:
            await seeding.create_boosted_legendary_dwellers(db_session, vault_db_obj.id)

        # Commit to ensure all dwellers and rooms are persisted before starting training
        await db_session.commit()

        # Start training sessions for boosted vaults
        await seeding.start_training_sessions(db_session, vault_db_obj.id, created_training_rooms, is_boosted)

        # Assign initial objectives to the vault (boosted vaults get more objectives)
        from app.crud.objective import objective_crud

        assigned = await objective_crud.assign_initial(
            db_session, vault_db_obj.id, is_boosted=is_boosted or scenario_start
        )
        if assigned == 0:
            self.logger.warning("No objectives found for vault %s", vault_db_obj.id)

        from app.services.progression.objectives.refresh_service import ensure_current_objectives

        await ensure_current_objectives(db_session, vault_db_obj.id)

        if is_boosted:
            await seeding.seed_boosted_theme_unlocks(db_session, vault_db_obj.id)

        # Create initial weapons, outfits, and (boosted) crafting materials for testing
        await seeding.create_initial_items(db_session, vault_db_obj.id, is_boosted)

        return vault_db_obj

    async def update_vault_resources(self, db_session: AsyncSession, vault_id: UUID4) -> Vault:
        """Update vault resources based on resource manager processing."""
        return await economy.update_vault_resources(db_session, vault_id)

    async def transfer_medical_supplies(
        self,
        db_session: AsyncSession,
        vault: Vault,
        dweller_id: UUID4,
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
        self, *, db_session: AsyncSession, vault_id: UUID4, population_required: int | None
    ) -> bool:
        """Check if the vault has enough dwellers to perform an operation."""
        return await economy.is_enough_dwellers(
            db_session=db_session, vault_id=vault_id, population_required=population_required
        )

    @staticmethod
    async def is_enough_population_space(*, db_session: AsyncSession, vault_id: UUID4, space_required: int) -> bool:
        """Check if the vault has enough space to perform an operation.

        Only counts dwellers that are assigned to rooms (have room_id).
        Unassigned dwellers don't take up living space.
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
        self, *, db_session: AsyncSession, user_id: UUID4
    ) -> list[VaultReadWithNumbers]:
        """List the user's non-deleted vaults with room/dweller counts and resource warnings."""
        return await reads.get_vaults_with_room_and_dweller_count(db_session=db_session, user_id=user_id)

    async def get_vault_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, vault_id: UUID4
    ) -> VaultReadWithNumbers:
        """Fetch a single vault with room/dweller counts and resource warnings."""
        return await reads.get_vault_with_room_and_dweller_count(db_session=db_session, vault_id=vault_id)


# Singleton instance
vault_service = VaultService()
