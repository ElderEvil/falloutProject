"""Service for intelligent dweller assignment to rooms."""

import logging

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.dweller import determine_status_for_room
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerUpdate

logger = logging.getLogger(__name__)

ABILITY_TO_STAT_MAP = {
    SPECIALEnum.STRENGTH: "strength",
    SPECIALEnum.PERCEPTION: "perception",
    SPECIALEnum.ENDURANCE: "endurance",
    SPECIALEnum.CHARISMA: "charisma",
    SPECIALEnum.INTELLIGENCE: "intelligence",
    SPECIALEnum.AGILITY: "agility",
    SPECIALEnum.LUCK: "luck",
}

PRODUCTION_ABILITIES = [
    SPECIALEnum.STRENGTH,
    SPECIALEnum.AGILITY,
    SPECIALEnum.PERCEPTION,
]

MEDSCI_ABILITIES = [SPECIALEnum.INTELLIGENCE]
RADIO_ABILITIES = [SPECIALEnum.CHARISMA]
TRAINING_ABILITIES = list(SPECIALEnum)


class DwellerAssignmentService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _calculate_room_capacity(self, room: Room) -> int:
        """Calculate room capacity (2 dwellers per 3 size units)."""
        room_size = room.size if room.size is not None else room.size_min
        return (room_size // 3) * 2 if room_size else 0

    async def _get_available_slots(self, room: Room, db_session: AsyncSession) -> int:
        """Get available slots in a room."""
        dweller_count_query = select(Dweller).where(Dweller.room_id == room.id)
        dweller_count_result = await db_session.execute(dweller_count_query)
        current_dwellers = len(dweller_count_result.scalars().all())
        max_capacity = self._calculate_room_capacity(room)
        return max(0, max_capacity - current_dwellers)

    async def _assign_dweller_to_room(
        self,
        dweller: Dweller,
        room: Room,
        db_session: AsyncSession,
        assignments: list[dict[str, str]],
        assigned_dweller_ids: set,
    ) -> None:
        """Assign a single dweller to a room and record the assignment."""
        await crud.dweller.update(
            db_session,
            dweller.id,
            DwellerUpdate(room_id=room.id, status=determine_status_for_room(room.category)),
        )
        assignments.append(
            {
                "dweller_id": str(dweller.id),
                "room_id": str(room.id),
                "room_name": room.name,
            }
        )
        assigned_dweller_ids.add(dweller.id)

    def _filter_rooms_by_abilities(self, rooms: list[Room], abilities: list[SPECIALEnum]) -> list[Room]:
        """Filter rooms by a list of abilities."""
        ability_rooms = []
        for ability in abilities:
            ability_rooms.extend([r for r in rooms if r.ability == ability])
        return ability_rooms

    async def _calculate_total_slots(
        self,
        ability_rooms: list[Room],
        db_session: AsyncSession,
    ) -> tuple[list[tuple[Room, int]], int]:
        """Calculate total available slots across rooms. Returns room_slots list and total."""
        room_slots = []
        total_slots = 0
        for room in ability_rooms:
            slots = await self._get_available_slots(room, db_session)
            if slots > 0:
                room_slots.append((room, slots))
                total_slots += slots
        return room_slots, total_slots

    async def _assign_ability_dwellers(
        self,
        ability: SPECIALEnum,
        ability_rooms: list[Room],
        db_session: AsyncSession,
        unassigned_dwellers: list[Dweller],
        assignments: list[dict[str, str]],
        assigned_dweller_ids: set,
        dwellers_for_tier: int,
    ) -> list[Dweller]:
        """Assign dwellers for a specific ability. Returns updated unassigned dwellers list."""
        ability_specific_rooms = [r for r in ability_rooms if r.ability == ability]
        if not ability_specific_rooms:
            return unassigned_dwellers

        ability_slots = []
        ability_total = 0
        for room in ability_specific_rooms:
            slots = await self._get_available_slots(room, db_session)
            if slots > 0:
                ability_slots.append((room, slots))
                ability_total += slots

        if ability_total == 0:
            return unassigned_dwellers

        stat_name = ABILITY_TO_STAT_MAP[ability]
        sorted_dwellers = sorted(
            [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids],
            key=lambda d: getattr(d, stat_name),
            reverse=True,
        )

        for room, slots in ability_slots:
            if not sorted_dwellers:
                break

            proportion = slots / ability_total
            target_for_room = max(1, int(dwellers_for_tier * proportion))
            actual_for_room = min(target_for_room, slots, len(sorted_dwellers))

            for _ in range(actual_for_room):
                if not sorted_dwellers:
                    break
                dweller = sorted_dwellers.pop(0)
                await self._assign_dweller_to_room(dweller, room, db_session, assignments, assigned_dweller_ids)

        return [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids]

    async def _assign_to_rooms_proportional(
        self,
        rooms: list[Room],
        abilities: list[SPECIALEnum],
        db_session: AsyncSession,
        unassigned_dwellers: list[Dweller],
        assignments: list[dict[str, str]],
        assigned_dweller_ids: set,
    ) -> list[Dweller]:
        """Assign dwellers to rooms with proportional fill within the tier."""
        if not unassigned_dwellers or not rooms:
            return unassigned_dwellers

        ability_rooms = self._filter_rooms_by_abilities(rooms, abilities)
        if not ability_rooms:
            return unassigned_dwellers

        _room_slots, total_slots = await self._calculate_total_slots(ability_rooms, db_session)
        if total_slots == 0:
            return unassigned_dwellers

        dwellers_for_tier = min(len(unassigned_dwellers), total_slots)

        for ability in abilities:
            if not unassigned_dwellers:
                break

            unassigned_dwellers = await self._assign_ability_dwellers(
                ability,
                ability_rooms,
                db_session,
                unassigned_dwellers,
                assignments,
                assigned_dweller_ids,
                dwellers_for_tier,
            )

        return unassigned_dwellers

    async def unassign_all_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> dict[str, int]:
        """Unassign all dwellers from their rooms in the specified vault."""
        dwellers = await crud.dweller.get_multi_by_vault(db_session, vault_id=vault_id, limit=10000)
        unassigned_count = 0

        for dweller in dwellers:
            if dweller.room_id is not None:
                await crud.dweller.update(
                    db_session,
                    dweller.id,
                    DwellerUpdate(room_id=None, status=DwellerStatusEnum.IDLE),
                )
                unassigned_count += 1

        return {"unassigned_count": unassigned_count}

    async def auto_assign_production_rooms(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> dict[str, int | list[dict[str, str]]]:
        """
        Intelligently assign unassigned dwellers to production rooms based on SPECIAL stats.
        Priority order: Power Plant (Strength) -> Diner (Agility) -> Water Treatment (Perception)
        """
        rooms_query = (
            select(Room)
            .where(Room.vault_id == vault_id)
            .where(Room.category == RoomTypeEnum.PRODUCTION)
            .where(Room.ability.in_(PRODUCTION_ABILITIES))
        )
        rooms_result = await db_session.execute(rooms_query)
        all_production_rooms = rooms_result.scalars().all()

        unassigned_query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.room_id.is_(None))
            .where(Dweller.is_deleted == False)
            .where(Dweller.is_dead == False)
        )
        unassigned_result = await db_session.execute(unassigned_query)
        unassigned_dwellers = list(unassigned_result.scalars().all())

        assignments: list[dict[str, str]] = []
        assigned_dweller_ids: set = set()

        for ability in PRODUCTION_ABILITIES:
            if not unassigned_dwellers:
                break

            ability_rooms = [r for r in all_production_rooms if r.ability == ability]

            for room in ability_rooms:
                if not unassigned_dwellers:
                    break

                dweller_count_query = select(Dweller).where(Dweller.room_id == room.id)
                dweller_count_result = await db_session.execute(dweller_count_query)
                current_dwellers_in_room = len(dweller_count_result.scalars().all())

                room_size = room.size if room.size is not None else room.size_min
                max_capacity = (room_size // 3) * 2 if room_size else 0

                available_slots = max_capacity - current_dwellers_in_room
                if available_slots <= 0:
                    continue

                stat_name = ABILITY_TO_STAT_MAP[ability]
                sorted_dwellers = sorted(
                    [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids],
                    key=lambda d: getattr(d, stat_name),
                    reverse=True,
                )

                for dweller in sorted_dwellers[:available_slots]:
                    await crud.dweller.update(
                        db_session,
                        dweller.id,
                        DwellerUpdate(room_id=room.id, status=determine_status_for_room(room.category)),
                    )
                    assignments.append(
                        {
                            "dweller_id": str(dweller.id),
                            "room_id": str(room.id),
                            "room_name": room.name,
                        }
                    )
                    assigned_dweller_ids.add(dweller.id)

            unassigned_dwellers = [d for d in unassigned_dwellers if d.id not in assigned_dweller_ids]

        return {"assigned_count": len(assignments), "assignments": assignments}

    async def auto_assign_all_rooms(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> dict[str, int | list[dict[str, str]]]:
        """
        Intelligently assign unassigned dwellers to ALL room types based on SPECIAL stats.
        Priority: Production -> Med/Science -> Radio -> Training
        """
        rooms_query = (
            select(Room)
            .where(Room.vault_id == vault_id)
            .where(Room.category.in_([RoomTypeEnum.PRODUCTION, RoomTypeEnum.MISC, RoomTypeEnum.TRAINING]))
        )
        rooms_result = await db_session.execute(rooms_query)
        all_rooms = rooms_result.scalars().all()

        production_rooms = [r for r in all_rooms if r.category == RoomTypeEnum.PRODUCTION]
        medsci_rooms = [
            r for r in all_rooms if r.category == RoomTypeEnum.MISC and r.ability == SPECIALEnum.INTELLIGENCE
        ]
        radio_rooms = [r for r in all_rooms if r.category == RoomTypeEnum.MISC and r.ability == SPECIALEnum.CHARISMA]
        training_rooms = [r for r in all_rooms if r.category == RoomTypeEnum.TRAINING]

        unassigned_query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.room_id.is_(None))
            .where(Dweller.is_deleted == False)
            .where(Dweller.is_dead == False)
        )
        unassigned_result = await db_session.execute(unassigned_query)
        unassigned_dwellers = list(unassigned_result.scalars().all())

        assignments: list[dict[str, str]] = []
        assigned_dweller_ids: set = set()

        unassigned_dwellers = await self._assign_to_rooms_proportional(
            production_rooms,
            PRODUCTION_ABILITIES,
            db_session,
            unassigned_dwellers,
            assignments,
            assigned_dweller_ids,
        )

        unassigned_dwellers = await self._assign_to_rooms_proportional(
            medsci_rooms,
            MEDSCI_ABILITIES,
            db_session,
            unassigned_dwellers,
            assignments,
            assigned_dweller_ids,
        )

        unassigned_dwellers = await self._assign_to_rooms_proportional(
            radio_rooms,
            RADIO_ABILITIES,
            db_session,
            unassigned_dwellers,
            assignments,
            assigned_dweller_ids,
        )

        unassigned_dwellers = await self._assign_to_rooms_proportional(
            training_rooms,
            TRAINING_ABILITIES,
            db_session,
            unassigned_dwellers,
            assignments,
            assigned_dweller_ids,
        )

        return {"assigned_count": len(assignments), "assignments": assignments}


dweller_assignment_service = DwellerAssignmentService()
