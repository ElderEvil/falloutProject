"""Service for room operations: build, destroy, upgrade, and queries."""

import logging
from dataclasses import dataclass
from uuid import uuid4

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RoomActionEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.core.grid_config import GRID_X_MAX, GRID_X_MIN, GRID_Y_MAX, GRID_Y_MIN
from app.crud.training import training as training_crud
from app.models.room import Room
from app.schemas.room import RoomBuild, RoomCreate, RoomUpdate
from app.services.user_service import user_service
from app.services.vault_service import vault_service
from app.utils import room_rules
from app.utils.exceptions import (
    InsufficientResourcesException,
    NoSpaceAvailableException,
    UniqueRoomViolationException,
    VaultOperationException,
)
from app.utils.room_assets import get_room_image_url
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """Result of an attempted adjacent-room merge."""

    room: Room | None
    absorbed_ids: list[UUID4]
    merged: bool
    created: bool = False
    # Capacity the vault already counts for the rooms this merge absorbs, so the
    # survivor's total replaces it instead of being added on top.
    previous_capacity: int = 0


class RoomService:
    """Service for room operations."""

    async def merge_adjacent_rooms(
        self,
        db_session: AsyncSession,
        *,
        candidate: RoomCreate | Room,
        dry_run: bool = False,
    ) -> MergeResult:
        """Merge a candidate footprint with directly adjacent identical rooms.

        The survivor is always the room at the lowest ``coordinate_x``.  When the
        candidate itself is the leftmost entity it is created (new segment) or
        updated (existing room).  Absorbed rooms are deleted and their dwellers
        reassigned to the survivor.

        Returns the surviving room and the IDs of rooms absorbed into it.
        If no merge is possible ``merged`` is ``False``.
        """
        vault_id = candidate.vault_id
        name = candidate.name
        tier = candidate.tier
        coordinate_x = candidate.coordinate_x
        coordinate_y = candidate.coordinate_y
        size = candidate.size if candidate.size is not None else candidate.size_min
        size_max = candidate.size_max
        capacity_formula = getattr(candidate, "capacity_formula", None)
        output_formula = getattr(candidate, "output_formula", None)
        candidate_id = getattr(candidate, "id", None)

        if coordinate_x is None or coordinate_y is None:
            return MergeResult(room=None, absorbed_ids=[], merged=False)

        adjacent = await crud.room.get_adjacent_mergeable_rooms(
            db_session=db_session,
            vault_id=vault_id,
            name=name,
            tier=tier,
            coordinate_x=coordinate_x,
            coordinate_y=coordinate_y,
            size=size,
        )
        adjacent = [room for room in adjacent if room.id != candidate_id]

        same_coordinate_room = await crud.room.get_room_by_coordinates(
            db_session=db_session, vault_id=vault_id, x_coord=coordinate_x, y_coord=coordinate_y
        )
        if (
            same_coordinate_room
            and same_coordinate_room.id != candidate_id
            and same_coordinate_room.name == name
            and same_coordinate_room.tier == tier
        ):
            group = [*adjacent, same_coordinate_room]
        else:
            group = adjacent

        if not group:
            return MergeResult(room=None, absorbed_ids=[], merged=False)

        leftmost_existing_x = min(
            (room.coordinate_x for room in group if room.coordinate_x is not None),
            default=coordinate_x + 1,
        )
        survivor_is_candidate = coordinate_x < leftmost_existing_x

        if survivor_is_candidate:
            survivor_room = None
            absorbed = group
            source_for_preview: RoomCreate | Room = candidate
        else:
            survivor_room = next(room for room in group if room.coordinate_x == leftmost_existing_x)
            absorbed = [room for room in group if room.id != survivor_room.id]
            source_for_preview = survivor_room

        absorbed_ids = [room.id for room in absorbed]
        total_size = size + sum((room.size if room.size is not None else room.size_min) for room in group)
        counted_capacity = sum((room.capacity or 0) for room in group)

        if total_size > size_max:
            return MergeResult(room=None, absorbed_ids=[], merged=False)

        new_capacity = None
        new_output = None
        if capacity_formula:
            new_capacity = crud.room.evaluate_capacity_formula(capacity_formula, tier, total_size)
        if output_formula:
            new_output = crud.room.evaluate_output_formula(output_formula, tier, total_size)
        new_image_url = get_room_image_url(name, tier=tier, size=total_size)

        if dry_run:
            preview_id = candidate_id or uuid4()
            preview = Room.model_construct(
                id=preview_id,
                vault_id=vault_id,
                name=name,
                category=source_for_preview.category,
                ability=source_for_preview.ability,
                population_required=source_for_preview.population_required,
                base_cost=source_for_preview.base_cost,
                incremental_cost=source_for_preview.incremental_cost,
                t2_upgrade_cost=source_for_preview.t2_upgrade_cost,
                t3_upgrade_cost=source_for_preview.t3_upgrade_cost,
                capacity=new_capacity,
                output=new_output,
                size_min=source_for_preview.size_min,
                size_max=size_max,
                size=total_size,
                tier=tier,
                coordinate_x=coordinate_x if survivor_is_candidate else leftmost_existing_x,
                coordinate_y=coordinate_y,
                image_url=new_image_url,
                speedup_multiplier=source_for_preview.speedup_multiplier,
            )
            return MergeResult(
                room=preview,
                absorbed_ids=absorbed_ids,
                merged=True,
                created=survivor_is_candidate and candidate_id is None,
                previous_capacity=counted_capacity,
            )

        created = False
        if survivor_is_candidate:
            if candidate_id is None:
                survivor_room = await crud.room.create(
                    db_session,
                    obj_in=RoomCreate(
                        vault_id=vault_id,
                        name=name,
                        category=candidate.category,
                        ability=candidate.ability,
                        population_required=candidate.population_required,
                        base_cost=candidate.base_cost,
                        incremental_cost=candidate.incremental_cost,
                        t2_upgrade_cost=candidate.t2_upgrade_cost,
                        t3_upgrade_cost=candidate.t3_upgrade_cost,
                        capacity=new_capacity,
                        output=new_output,
                        size_min=candidate.size_min,
                        size_max=size_max,
                        size=total_size,
                        tier=tier,
                        coordinate_x=coordinate_x,
                        coordinate_y=coordinate_y,
                        image_url=new_image_url,
                        speedup_multiplier=candidate.speedup_multiplier,
                        capacity_formula=capacity_formula,
                        output_formula=output_formula,
                    ),
                )
                created = True
            else:
                survivor_room = await crud.room.update(
                    db_session=db_session,
                    id=candidate_id,
                    obj_in=RoomUpdate(
                        size=total_size,
                        capacity=new_capacity,
                        output=new_output,
                        image_url=new_image_url,
                    ),
                )
        elif survivor_room is not None:
            survivor_room = await crud.room.update(
                db_session=db_session,
                id=survivor_room.id,
                obj_in=RoomUpdate(
                    size=total_size,
                    capacity=new_capacity,
                    output=new_output,
                    image_url=new_image_url,
                ),
            )
        else:
            return MergeResult(room=None, absorbed_ids=[], merged=False)

        if absorbed_ids:
            await crud.dweller.reassign_dwellers_between_rooms(
                db_session=db_session,
                vault_id=vault_id,
                from_room_ids=absorbed_ids,
                to_room_id=survivor_room.id,
            )
            await training_crud.reassign_room_training(
                db_session=db_session,
                vault_id=vault_id,
                from_room_ids=absorbed_ids,
                to_room_id=survivor_room.id,
            )
            # Flush the moves before the rooms go away: deleting an absorbed Room
            # makes the ORM detach its children by nulling their room_id, which
            # would otherwise undo the reassignment for dwellers still listed on
            # that Room's collection.
            await db_session.flush()
            for room in absorbed:
                await crud.room.delete(db_session=db_session, id=room.id, soft=False)

        return MergeResult(
            room=survivor_room,
            absorbed_ids=absorbed_ids,
            merged=True,
            created=created,
            previous_capacity=counted_capacity,
        )

    async def backfill_merge_rooms_for_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        *,
        dry_run: bool = True,
    ) -> dict[str, int]:
        """Merge existing adjacent duplicate rooms in one vault.

        Scans left-to-right, top-to-bottom and repeatedly merges each room with
        adjacent identical neighbours until no more merges fit within ``size_max``.
        """
        rooms = await crud.room.get_all_by_vault(db_session, vault_id)
        absorbed_ids: set[UUID4] = set()
        merged_count = 0

        positioned = [room for room in rooms if room.coordinate_x is not None and room.coordinate_y is not None]
        for room in sorted(positioned, key=lambda room: (room.coordinate_y, room.coordinate_x)):
            if room.id in absorbed_ids or room.name.lower() in {"elevator", "vault door"}:
                continue

            current: Room = room
            while True:
                result = await self.merge_adjacent_rooms(
                    db_session,
                    candidate=current,
                    dry_run=dry_run,
                )
                if not result.merged:
                    break
                if result.room is None:
                    break
                current = result.room
                absorbed_ids.update(result.absorbed_ids)
                merged_count += len(result.absorbed_ids)

        return {"merged": merged_count}

    async def build_room(
        self,
        db_session: AsyncSession,
        room_request: RoomBuild,
    ) -> Room:
        """Build a new room in a vault.

        Args:
            db_session: Database session
            room_request: Requested template and placement

        Returns:
            Created room

        Raises:
            InsufficientResourcesException: If vault lacks resources
            NoSpaceAvailableException: If no space for the room
            UniqueRoomViolationException: If unique room already exists
            VaultOperationException: On other build failures
        """
        try:
            room_template = game_data_store.get_room(room_request.room_name)
            if room_template is None or room_template.name.lower() == "vault door":
                raise VaultOperationException(detail=f"Room cannot be built: {room_request.room_name}")
            room_data = RoomCreate(
                vault_id=room_request.vault_id,
                name=room_template.name,
                category=room_template.category,
                ability=room_template.ability,
                population_required=room_template.population_required,
                base_cost=room_template.base_cost,
                incremental_cost=room_template.incremental_cost,
                t2_upgrade_cost=room_template.t2_upgrade_cost,
                t3_upgrade_cost=room_template.t3_upgrade_cost,
                capacity=room_template.capacity,
                output=room_template.output,
                size_min=room_template.size_min,
                size_max=room_template.size_max,
                size=room_template.size_min,
                tier=room_template.tier,
                coordinate_x=room_request.coordinate_x,
                coordinate_y=room_request.coordinate_y,
                image_url=room_template.image_url,
                speedup_multiplier=room_template.speedup_multiplier,
                capacity_formula=room_template.capacity_formula,
                output_formula=room_template.output_formula,
            )
            room, created = await self._build(db_session=db_session, obj_in=room_data)
        except (InsufficientResourcesException, NoSpaceAvailableException, UniqueRoomViolationException):
            raise
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e
        else:
            if created:
                await user_service.record_vault_statistic(db_session, room.vault_id, "total_rooms_built")
            return room

    async def _build(self, *, db_session: AsyncSession, obj_in: RoomCreate) -> tuple[Room, bool]:
        """Build a room from a full create payload, expanding when the same room exists."""
        vault = await crud.vault.get(db_session, id=obj_in.vault_id)

        if obj_in.size_min is None or obj_in.size_min < 1:
            msg = f"Invalid room size: {obj_in.size_min}. Size must be at least 1."
            raise ValueError(msg)

        if obj_in.size_max is None or obj_in.size_min > obj_in.size_max:
            msg = f"Invalid room size: {obj_in.size_min} exceeds maximum size {obj_in.size_max}."
            raise ValueError(msg)

        if obj_in.coordinate_x is None or obj_in.coordinate_y is None:
            msg = "Room coordinates must be specified."
            raise ValueError(msg)

        if obj_in.coordinate_x < GRID_X_MIN or obj_in.coordinate_x > GRID_X_MAX:
            msg = f"Invalid X coordinate: {obj_in.coordinate_x}. Must be between {GRID_X_MIN} and {GRID_X_MAX}."
            raise ValueError(msg)

        max_x = obj_in.coordinate_x + obj_in.size_min - 1
        if max_x > GRID_X_MAX:
            msg = f"Room exceeds grid width: max X {max_x} > {GRID_X_MAX}"
            raise ValueError(msg)

        if obj_in.coordinate_y < GRID_Y_MIN or obj_in.coordinate_y > GRID_Y_MAX:
            msg = f"Invalid Y coordinate: {obj_in.coordinate_y}. Must be between {GRID_Y_MIN} and {GRID_Y_MAX}."
            raise ValueError(msg)

        await room_rules.validate_build_placement(
            db_session,
            vault.id,
            obj_in.name,
            obj_in.coordinate_x,
            obj_in.coordinate_y,
            obj_in.size if obj_in.size is not None else obj_in.size_min,
            tier=obj_in.tier,
        )

        if obj_in.name.lower() == "vault door":
            existing_names = await crud.room.get_existing_room_names(db_session=db_session, vault_id=vault.id)
            if "vault door" in existing_names:
                raise UniqueRoomViolationException(room_name="Vault Door")

        if not await vault_service.is_enough_dwellers(
            db_session=db_session, vault_id=vault.id, population_required=obj_in.population_required
        ):
            raise InsufficientResourcesException(resource_name="dwellers", resource_amount=obj_in.population_required)

        room_template = game_data_store.get_room(obj_in.name)
        if room_template:
            obj_in.capacity_formula = room_template.capacity_formula
            obj_in.output_formula = room_template.output_formula

        await crud.room.check_is_unique_room(db_session=db_session, obj_in=obj_in)

        merge_result = await self.merge_adjacent_rooms(db_session=db_session, candidate=obj_in)
        if merge_result.merged and merge_result.room is not None:
            survivor = merge_result.room
            price = await crud.room.get_room_build_price(db_session=db_session, room_in=obj_in)
            await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price)

            if crud.room.requires_recalculation(survivor):
                await vault_service.recalculate_vault_attributes(
                    db_session=db_session,
                    vault_obj=vault,
                    room_obj=survivor,
                    action=RoomActionEnum.BUILD,
                    previous_capacity=merge_result.previous_capacity,
                )

            await event_bus.emit(
                GameEvent.ROOM_BUILT,
                vault.id,
                {"room_type": survivor.name, "tier": survivor.tier, "room_id": str(survivor.id)},
            )
            return survivor, merge_result.created

        if obj_in.capacity_formula:
            room_size = obj_in.size if obj_in.size is not None else obj_in.size_min
            obj_in.capacity = crud.room.evaluate_capacity_formula(obj_in.capacity_formula, obj_in.tier, room_size)

        if obj_in.output_formula:
            room_size = obj_in.size if obj_in.size is not None else obj_in.size_min
            obj_in.output = crud.room.evaluate_output_formula(obj_in.output_formula, obj_in.tier, room_size)

        price = await crud.room.get_room_build_price(db_session=db_session, room_in=obj_in)
        await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price)

        room_size = obj_in.size if obj_in.size is not None else obj_in.size_min
        obj_in.image_url = get_room_image_url(obj_in.name, tier=obj_in.tier, size=room_size)

        obj_in_db: Room = await crud.room.create(db_session, obj_in=obj_in)
        await db_session.refresh(obj_in_db)

        if crud.room.requires_recalculation(obj_in_db):
            await vault_service.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=obj_in_db, action=RoomActionEnum.BUILD
            )

        await event_bus.emit(
            GameEvent.ROOM_BUILT,
            vault.id,
            {"room_type": obj_in_db.name, "tier": obj_in_db.tier, "room_id": str(obj_in_db.id)},
        )

        return obj_in_db, True

    async def destroy_room(
        self,
        db_session: AsyncSession,
        room_id: UUID4,
    ) -> Room:
        """Destroy a room and refund a portion of its cost.

        Args:
            db_session: Database session
            room_id: Room ID to destroy

        Returns:
            Destroyed room data

        Raises:
            ResourceNotFoundException: If room not found
            VaultOperationException: If room cannot be destroyed (vault door, elevator dependency)
        """
        try:
            return await self._destroy(db_session, room_id)
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e

    async def _destroy(self, db_session: AsyncSession, room_id: UUID4) -> Room:
        room = await crud.room.get(db_session, room_id)
        vault = await crud.vault.get(db_session, id=room.vault_id)

        if room.name.lower() == "vault door":
            msg = "Cannot destroy the vault door. It is a critical structure and must remain in place."
            raise ValueError(msg)

        await room_rules.validate_elevator_destroy(db_session, room)

        db_obj = await crud.room.delete(db_session, id=room_id)

        refundable_total = db_obj.base_cost + (db_obj.incremental_cost or 0)

        if db_obj.tier >= 2 and db_obj.t2_upgrade_cost:
            refundable_total += db_obj.t2_upgrade_cost
        if db_obj.tier >= 3 and db_obj.t3_upgrade_cost:
            refundable_total += db_obj.t3_upgrade_cost

        refund = int(refundable_total * db_obj.segment_count * game_config.resource.destroy_room_refund_rate)

        await vault_service.deposit_caps(db_session=db_session, vault_obj=vault, amount=refund, track_earnings=False)

        if crud.room.requires_recalculation(db_obj):
            await vault_service.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=db_obj, action=RoomActionEnum.DESTROY
            )

        return db_obj

    async def upgrade_room(
        self,
        db_session: AsyncSession,
        room_id: UUID4,
    ) -> Room:
        """Upgrade a room to the next tier.

        Args:
            db_session: Database session
            room_id: Room ID to upgrade

        Returns:
            Upgraded room

        Raises:
            ResourceNotFoundException: If room not found
            InsufficientResourcesException: If vault lacks caps
            VaultOperationException: On other upgrade failures
        """
        try:
            return await self._upgrade(db_session, room_id)
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e

    async def _upgrade(self, db_session: AsyncSession, room_id: UUID4) -> Room:
        room = await crud.room.get(db_session, room_id)
        vault = await crud.vault.get(db_session, id=room.vault_id)

        max_tier = room.max_tier

        if room.tier >= max_tier:
            msg = f"Room {room.name} is already at maximum tier {max_tier}"
            raise ValueError(msg)

        if room.tier == 1 and room.t2_upgrade_cost:
            upgrade_cost = room.t2_upgrade_cost * room.segment_count
        elif room.tier == 2 and room.t3_upgrade_cost:
            upgrade_cost = room.t3_upgrade_cost * room.segment_count
        else:
            msg = f"No upgrade cost defined for room {room.name} at tier {room.tier}"
            raise ValueError(msg)

        await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=upgrade_cost)

        old_tier = room.tier
        old_capacity = room.capacity
        room.tier += 1

        room_size = room.size if room.size is not None else room.size_min
        template = game_data_store.get_room(room.name)

        new_capacity = None
        new_output = None

        # Re-evaluate the template's own formula. The (tier + 4) ratio below only
        # matches rooms whose capacity happens to be proportional to it — storage
        # scales with (tier + 1), so the ratio silently understates it.
        if template and template.capacity_formula:
            new_capacity = crud.room.evaluate_capacity_formula(template.capacity_formula, room.tier, room_size)
        elif room.capacity is not None:
            new_capacity = int(room.capacity * (room.tier + 4) / (old_tier + 4))

        if template and template.output_formula:
            new_output = crud.room.evaluate_output_formula(template.output_formula, room.tier, room_size)
        elif room.output is not None:
            new_output = int(room.output * (room.tier + 4) / (old_tier + 4))

        new_image_url = get_room_image_url(room.name, tier=room.tier, size=room_size)

        await crud.room.update(
            db_session=db_session,
            obj_in=RoomUpdate(tier=room.tier, capacity=new_capacity, output=new_output, image_url=new_image_url),
            id=room.id,
        )

        room.capacity = new_capacity
        room.output = new_output

        if crud.room.requires_recalculation(room):
            await vault_service.recalculate_vault_attributes(
                db_session=db_session,
                vault_obj=vault,
                room_obj=room,
                action=RoomActionEnum.UPGRADE,
                previous_capacity=old_capacity,
            )

        await event_bus.emit(
            GameEvent.ROOM_UPGRADED,
            vault.id,
            {"room_type": room.name, "from_tier": old_tier, "to_tier": room.tier, "room_id": str(room.id)},
        )

        await db_session.refresh(room)
        return room

    async def get_buildable_rooms(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list:
        """Get list of rooms that can be built in a vault.

        Filters out vault doors and unique rooms already built.

        Args:
            db_session: Database session
            vault_id: Vault ID

        Returns:
            List of buildable room specs
        """
        from app.core.game_data import get_static_game_data

        data_store = await get_static_game_data()
        existing_room_names = await crud.room.get_existing_room_names(db_session=db_session, vault_id=vault_id)
        return data_store.get_buildable_rooms(existing_room_names)

    async def get_rooms_by_name_pattern(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        pattern: str,
    ) -> "list[Room]":
        """Rooms of a vault whose name matches a LIKE pattern (e.g. ``%radio%``)."""
        return await crud.room.get_by_name_pattern(db_session, vault_id, pattern)


# Singleton instance
room_service = RoomService()
