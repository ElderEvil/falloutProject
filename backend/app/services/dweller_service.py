"""General dweller business logic service."""

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, RarityEnum, RoomTypeEnum
from app.core.event_bus import GameEvent, event_bus
from app.crud import training as training_crud
from app.crud.dweller import determine_status_for_room
from app.models.dweller import Dweller
from app.models.room import Room
from app.options.factions import faction_restrictions
from app.options.races import STATE_OF_BEING_VALUES, RaceOption
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerIdentityOptions,
    DwellerReadWithRoomID,
    DwellerUpdate,
)
from app.services.map_service import map_service
from app.services.notification_service import notification_service
from app.services.room_assignment_policy import (
    calculate_room_capacity,
    get_highest_special,
    validate_automatic_assignment,
    validate_room_assignment,
)
from app.services.training_service import training_service
from app.services.user_service import user_service
from app.services.vault_service import vault_service
from app.utils.exceptions import (
    ContentNoChangeException,
    InvalidVaultTransferException,
    ResourceConflictException,
    ResourceNotFoundException,
)
from app.utils.reward_delivery import reward_delivery_is_deferred

logger = logging.getLogger(__name__)


class DwellerService:
    """Service for general dweller operations that span multiple CRUD modules."""

    def get_identity_options(self) -> DwellerIdentityOptions:
        """Return identity choices derived directly from the canonical options modules."""
        return DwellerIdentityOptions(
            races=[race.value for race in RaceOption],
            factions_by_race={
                race.value: [faction.value for faction in factions] for race, factions in faction_restrictions.items()
            },
            states_by_race={race.value: states for race, states in STATE_OF_BEING_VALUES.items()},
        )

    async def create_dweller(self, db_session: AsyncSession, obj_in: DwellerCreate) -> Dweller:
        """Create a dweller and record the overseer's lifetime total."""
        dweller = await crud.dweller.create(db_session, obj_in)
        await user_service.record_vault_statistic(db_session, dweller.vault_id, "total_dwellers_created")
        return dweller

    async def create_random_dweller(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        obj_in: DwellerCreateCommonOverride | None = None,
        seed: int | None = None,
        rarity: RarityEnum = RarityEnum.COMMON,
        register_bio_places: bool = True,
    ) -> Dweller:
        """Create a random dweller, recording the overseer's total and registering bio places.

        Callers composing their OWN bio (e.g. pregen_service) pass ``register_bio_places=False``.
        """
        payload = await crud.dweller.prepare_random_dweller(db_session, vault_id, obj_in, seed=seed, rarity=rarity)
        return await self._persist_registered_dweller(db_session, vault_id, payload, register_bio_places)

    async def create_dweller_from_template(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        template_id: str,
        overrides: Mapping[str, Any] | None = None,
    ) -> Dweller:
        """Instantiate a dweller from a named template, recording the overseer's total and bio places."""
        payload = await crud.dweller.prepare_template_dweller(db_session, vault_id, template_id, overrides=overrides)
        return await self._persist_registered_dweller(db_session, vault_id, payload, register_bio_places=True)

    async def _persist_registered_dweller(
        self, db_session: AsyncSession, vault_id: UUID4, payload: dict[str, Any], register_bio_places: bool
    ) -> Dweller:
        """Persist a prepared payload, record the lifetime total and register explicit bio places."""
        bio_places = payload.pop("_bio_places", None)
        dweller = await crud.dweller.persist_new_dweller(db_session, vault_id, payload)
        await user_service.record_vault_statistic(db_session, vault_id, "total_dwellers_created")
        if bio_places and register_bio_places:
            origin, visited = bio_places
            await map_service.register_bio_places(
                db_session, dweller, origin_place=origin or "", visited_places=visited
            )
        return dweller

    async def add_experience(self, db_session: AsyncSession, dweller_obj: Dweller, amount: int) -> Dweller:
        """Add experience via CRUD, then emit the level-up event and notify the vault owner."""
        old_level = dweller_obj.level
        updated_dweller = await crud.dweller.add_experience(db_session, dweller_obj, amount)
        leveled_up = updated_dweller.level > old_level and not reward_delivery_is_deferred(db_session)

        if leveled_up and updated_dweller.vault_id:
            await event_bus.emit(
                GameEvent.DWELLER_LEVEL_UP,
                updated_dweller.vault_id,
                {
                    "dweller_id": str(updated_dweller.id),
                    "level": updated_dweller.level,
                    "old_level": old_level,
                    "amount": 1,
                },
            )

            vault = await crud.vault.get(db_session, updated_dweller.vault_id)
            if vault and vault.user_id:
                await notification_service.notify_level_up(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=updated_dweller.vault_id,
                    dweller_id=updated_dweller.id,
                    dweller_name=f"{updated_dweller.first_name} {updated_dweller.last_name or ''}".strip(),
                    new_level=updated_dweller.level,
                    meta_data={"old_level": old_level, "new_level": updated_dweller.level},
                )

        return updated_dweller

    async def update_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        dweller_data: DwellerUpdate | dict[str, Any],
    ) -> Any:
        """Update a dweller, computing room-based status automatically.

        When room_id is being changed, determines the correct dweller status
        (idle/working/training) based on the target room's category.
        """
        # Ensure we work with a dict for mutation
        data = dweller_data if isinstance(dweller_data, dict) else dweller_data.model_dump(exclude_unset=True)
        room_id = data.get("room_id")

        if "room_id" in data:
            dweller = await crud.dweller.get(db_session, dweller_id)
            if room_id != dweller.room_id:
                active_training = await training_crud.training.get_active_by_dweller(db_session, dweller_id)
                if active_training:
                    await training_service.cancel_training(db_session, active_training.id, dweller=dweller)

        # Compute status if room_id is being set or cleared
        if room_id is not None or "room_id" in data:
            if room_id is None:
                data["status"] = determine_status_for_room(None)
            else:
                room_obj = await crud.room.get(db_session, room_id)
                if not room_obj:
                    raise ResourceNotFoundException(model=Room, identifier=room_id)
                data["status"] = determine_status_for_room(room_obj.category, room_obj.name)

        updated = await crud.dweller.update(db_session, dweller_id, DwellerUpdate(**data), commit=False)

        if "room_id" in data and room_id != dweller.room_id:
            from app.services.combat.arena_service import arena_service

            await arena_service.clear_fighter_slots_for_dweller(db_session, dweller_id, commit=False)
        await db_session.commit()
        return updated

    async def move_to_room(self, db_session: AsyncSession, dweller_id: UUID4, room_id: UUID4) -> DwellerReadWithRoomID:
        """Move dweller to a different room."""
        dweller_obj = await crud.dweller.get(db_session, dweller_id)

        if dweller_obj.status == DwellerStatusEnum.EXPLORING:
            raise ResourceConflictException(detail="Dweller is exploring and cannot be assigned to a room")

        # Validate room transfer (can't move to same room)
        if dweller_obj.room_id == room_id:
            raise ResourceConflictException(detail="Dweller is already in the room")

        old_room_id = dweller_obj.room_id
        room_obj = await crud.room.get(db_session, room_id)

        # Validate vault transfer (can't move between vaults)
        if dweller_obj.vault_id != room_obj.vault_id:
            raise InvalidVaultTransferException

        await validate_room_assignment(db_session, dweller_obj, room_obj)

        if not dweller_obj.room_id and not await vault_service.is_enough_population_space(
            db_session=db_session, vault_id=dweller_obj.vault_id, space_required=1
        ):
            raise ContentNoChangeException(detail="Not enough space in the vault to move dweller")

        new_status = determine_status_for_room(room_obj.category, room_obj.name)

        apprenticeship_update = (
            {"apprentice_stat": room_obj.ability, "apprentice_started_at": datetime.utcnow()}
            if not dweller_obj.is_mature
            else {"apprentice_stat": None, "apprentice_started_at": None, "apprentice_stat_gains": {}}
        )
        dweller_obj = await crud.dweller.update(
            db_session, dweller_id, {"room_id": room_id, "status": new_status, **apprenticeship_update}, commit=False
        )

        # Leaving an arena room must clear the stale fighter slot, or later fighter picks get rejected.
        if old_room_id is not None:
            from app.services.combat.arena_service import arena_service

            await arena_service.clear_fighter_slots_for_dweller(db_session, dweller_id, commit=False)
        await db_session.commit()

        # Emit dweller assigned event for objective tracking
        await event_bus.emit(
            GameEvent.DWELLER_ASSIGNED,
            dweller_obj.vault_id,
            {"dweller_id": str(dweller_id), "room_type": room_obj.name},
        )

        # Check if this is a "correct" assignment (dweller's highest SPECIAL matches room's ability)
        if room_obj.ability and get_highest_special(dweller_obj) == room_obj.ability:
            await event_bus.emit(
                GameEvent.DWELLER_ASSIGNED_CORRECTLY,
                dweller_obj.vault_id,
                {"dweller_id": str(dweller_id), "room_type": room_obj.name, "is_correct": True},
            )

        return DwellerReadWithRoomID.model_validate(dweller_obj)

    async def auto_assign_to_best_room(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadWithRoomID:
        """Auto-assign dweller to the best matching production room based on their highest SPECIAL stat."""
        dweller_obj = await crud.dweller.get(db_session, dweller_id)
        validate_automatic_assignment(dweller_obj)

        # Find dweller's highest SPECIAL stat
        best_stat = get_highest_special(dweller_obj)

        # Find production rooms in the dweller's vault that match this stat
        production_rooms = await crud.room.get_by_category(db_session, dweller_obj.vault_id, RoomTypeEnum.PRODUCTION)
        matching_rooms = [room for room in production_rooms if room.ability == best_stat]

        if not matching_rooms:
            raise ResourceConflictException(
                detail=f"No production rooms found matching {best_stat.value} stat in this vault"
            )

        # Check if dweller is already in a matching room
        if dweller_obj.room_id:
            current_room = await crud.room.get(db_session, dweller_obj.room_id)
            if current_room.category == RoomTypeEnum.PRODUCTION and current_room.ability == best_stat:
                raise ContentNoChangeException(
                    detail=f"Dweller is already assigned to the best matching room ({current_room.name})"
                )

        # Find room with available capacity (based on room size): 2 dwellers per 3 size units
        best_room = None
        for room in matching_rooms:
            dweller_count = await crud.dweller.count_in_room(db_session, room.id)
            if dweller_count < calculate_room_capacity(room.size):
                best_room = room
                break

        if not best_room:
            raise ResourceConflictException(detail=f"All {best_stat.value} production rooms are at full capacity")

        # Move dweller to the best room
        return await self.move_to_room(db_session, dweller_id, best_room.id)


dweller_service = DwellerService()
