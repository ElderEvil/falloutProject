"""Service for vault initialization and resource management."""

import logging

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.game_data_deps import get_static_game_data
from app.crud import dweller as dweller_crud
from app.crud import room as room_crud
from app.crud.vault import vault as vault_crud
from app.models import Room
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import DwellerStatusEnum, GenderEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreateCommonOverride, DwellerUpdate
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultNumber, VaultUpdate
from app.services.resource_manager import ResourceManager
from app.services.training_service import training_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


class VaultService:
    """Service for vault initialization and management."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.resource_manager = ResourceManager()

    @staticmethod
    def _prepare_room_data(rooms: list[RoomCreate], room_name: str, vault_id: UUID4, x: int, y: int) -> dict:
        room_data = next(room for room in rooms if room.name.lower() == room_name)
        room_data_dict = room_data.model_dump()

        # Evaluate capacity and output formulas if present
        size = room_data.size_min
        tier = 1  # Initial tier

        # Check in the dumped dict for formula fields
        if room_data_dict.get("capacity_formula"):
            room_data_dict["capacity"] = room_crud.evaluate_capacity_formula(
                room_data_dict["capacity_formula"], tier, size
            )
        if room_data_dict.get("output_formula"):
            room_data_dict["output"] = room_crud.evaluate_output_formula(room_data_dict["output_formula"], tier, size)

        room_data_dict.update(
            {
                "vault_id": vault_id,
                "size": size,
                "tier": tier,
                "coordinate_x": x,
                "coordinate_y": y,
            }
        )
        return room_data_dict

    def _prepare_initial_rooms(
        self,
        rooms: list[RoomCreate],
        vault_id: UUID4,
        is_boosted: bool,
    ) -> tuple[list[RoomCreate], list[RoomCreate], list[RoomCreate], list[RoomCreate], list[RoomCreate]]:
        """Prepare all room data for vault initialization."""
        # Infrastructure rooms
        vault_door_data = self._prepare_room_data(rooms, "vault door", vault_id, 0, 0)
        elevators_data = [self._prepare_room_data(rooms, "elevator", vault_id, 0, y) for y in range(1, 4)]
        infrastructure_rooms = [RoomCreate(**vault_door_data)] + [RoomCreate(**data) for data in elevators_data]

        # Capacity rooms (living rooms + storage)
        living_room_data = self._prepare_room_data(rooms, "living room", vault_id, 2, 1)
        storage_room_data = self._prepare_room_data(rooms, "storage room", vault_id, 2, 2)
        capacity_rooms = [RoomCreate(**living_room_data), RoomCreate(**storage_room_data)]

        # Add extra living rooms for boosted
        if is_boosted:
            extra_capacity_rooms_data = [
                self._prepare_room_data(rooms, "living room", vault_id, 4, 3),
                self._prepare_room_data(rooms, "living room", vault_id, 5, 3),
            ]
            capacity_rooms.extend([RoomCreate(**data) for data in extra_capacity_rooms_data])

        # Production rooms
        power_generator_data = self._prepare_room_data(rooms, "power generator", vault_id, 1, 1)
        diner_data = self._prepare_room_data(rooms, "diner", vault_id, 1, 2)
        water_treatment_data = self._prepare_room_data(rooms, "water treatment", vault_id, 1, 3)
        production_rooms = [
            RoomCreate(**power_generator_data),
            RoomCreate(**diner_data),
            RoomCreate(**water_treatment_data),
        ]

        # Add Medbay and Science Lab for boosted (produce stimpaks/radaways)
        if is_boosted:
            medbay_data = self._prepare_room_data(rooms, "medbay", vault_id, 7, 1)
            science_lab_data = self._prepare_room_data(rooms, "science lab", vault_id, 7, 2)
            production_rooms.extend([RoomCreate(**medbay_data), RoomCreate(**science_lab_data)])

        # Miscellaneous rooms
        radio_studio_data = self._prepare_room_data(rooms, "radio studio", vault_id, 2, 3)
        misc_rooms = [RoomCreate(**radio_studio_data)]

        # Add Overseer's Office for boosted
        if is_boosted:
            overseer_office_data = self._prepare_room_data(rooms, "overseer's office", vault_id, 6, 2)
            misc_rooms.append(RoomCreate(**overseer_office_data))

        # Training rooms (boosted only)
        training_rooms = []
        if is_boosted:
            training_room_configs = [
                ("weight room", 3, 1),  # Strength
                ("armory", 3, 2),  # Perception
                ("athletics room", 4, 1),  # Endurance
                ("classroom", 4, 2),  # Charisma
                ("game room", 5, 1),  # Intelligence
                ("fitness room", 5, 2),  # Agility
                ("lounge", 6, 1),  # Luck
            ]
            training_rooms_data = [
                self._prepare_room_data(rooms, room_name, vault_id, x, y) for room_name, x, y in training_room_configs
            ]
            training_rooms = [RoomCreate(**data) for data in training_rooms_data]

        return infrastructure_rooms, capacity_rooms, production_rooms, misc_rooms, training_rooms

    async def _create_initial_rooms(  # noqa: C901, PLR0912
        self,
        db_session: AsyncSession,
        vault: Vault,
        infrastructure_rooms: list[RoomCreate],
        capacity_rooms: list[RoomCreate],
        production_rooms: list[RoomCreate],
        misc_rooms: list[RoomCreate],
        training_rooms: list[RoomCreate],
    ) -> tuple[Vault, list[Room], list[Room], list[Room], list[Room]]:
        """Create all rooms for a new vault and return production/training rooms."""
        # Create infrastructure rooms
        for room_data in infrastructure_rooms:
            await room_crud.create(db_session, room_data)

        # Create capacity rooms and update vault max capacities
        created_capacity_rooms = []
        for room_data in capacity_rooms:
            created_room = await room_crud.create(db_session, room_data)
            created_capacity_rooms.append(created_room)
            # Update vault capacities based on new rooms
            if created_room.category == RoomTypeEnum.CAPACITY:
                # Check room name to determine what capacity to increase
                if "living" in created_room.name.lower():
                    vault.population_max += created_room.capacity or 0
                elif "storage" in created_room.name.lower() and created_room.capacity:
                    # Storage rooms increase Storage.max_space, not individual vault capacities
                    # Query current storage max_space to avoid lazy load issue
                    from sqlmodel import select

                    from app.models.storage import Storage

                    storage_result = await db_session.execute(
                        select(Storage.max_space).where(Storage.vault_id == vault.id)
                    )
                    current_max_space = storage_result.scalar_one_or_none() or 0
                    await vault_crud.update_storage(db_session, vault.id, current_max_space + created_room.capacity)

        await db_session.commit()
        await db_session.refresh(vault)

        # Create production rooms and update vault capacities
        created_production_rooms = []
        for room_data in production_rooms:
            created_room = await room_crud.create(db_session, room_data)
            created_production_rooms.append(created_room)

            # Update vault capacities based on room ability (strength→power, agility→food, perception→water)
            if created_room.ability and created_room.capacity:
                ability_lower = created_room.ability.value.lower()
                if ability_lower == "strength":
                    vault.power_max += created_room.capacity
                elif ability_lower == "agility":
                    vault.food_max += created_room.capacity
                elif ability_lower == "perception":
                    vault.water_max += created_room.capacity

        # Create misc rooms
        created_misc_rooms = []
        for room_data in misc_rooms:
            created_room = await room_crud.create(db_session, room_data)
            created_misc_rooms.append(created_room)

        # Create training rooms
        created_training_rooms = []
        for room_data in training_rooms:
            created_room = await room_crud.create(db_session, room_data)
            created_training_rooms.append(created_room)

        await db_session.commit()

        # Refresh vault and room objects
        await db_session.refresh(vault)
        for room in created_production_rooms + created_training_rooms + created_misc_rooms + created_capacity_rooms:
            await db_session.refresh(room)

        return vault, created_production_rooms, created_training_rooms, created_misc_rooms, created_capacity_rooms

    async def _create_initial_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        created_production_rooms: list[Room],
        created_training_rooms: list[Room],
        created_misc_rooms: list[Room],
        created_capacity_rooms: list[Room],
        is_boosted: bool,
    ) -> None:
        """Create and assign initial dwellers to production and training rooms."""

        try:
            # Production dwellers (always created) - all should be WORKING
            production_assignments = [
                (created_production_rooms[0], SPECIALEnum.STRENGTH),
                (created_production_rooms[0], SPECIALEnum.STRENGTH),
                (created_production_rooms[1], SPECIALEnum.AGILITY),
                (created_production_rooms[1], SPECIALEnum.AGILITY),
                (created_production_rooms[2], SPECIALEnum.PERCEPTION),
                (created_production_rooms[2], SPECIALEnum.PERCEPTION),
            ]

            for room, boosted_stat in production_assignments:
                dweller_data = DwellerCreateCommonOverride(special_boost=boosted_stat)
                dweller_obj = await dweller_crud.create_random(db_session, vault_id, dweller_data)

                # Assign dweller to room with WORKING status
                await dweller_crud.update(
                    db_session=db_session,
                    id=dweller_obj.id,
                    obj_in=DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.WORKING),
                )
                self.logger.info(f"Dweller {dweller_obj.id} assigned to room {room.id}")

            # Medbay and Science Lab dwellers (boosted only, Intelligence-based)
            if is_boosted and len(created_production_rooms) >= 5:
                medbay_room = created_production_rooms[3]  # 4th room is Medbay
                science_lab_room = created_production_rooms[4]  # 5th room is Science Lab

                # Create 2 dwellers for Medbay
                for _ in range(2):
                    dweller_data = DwellerCreateCommonOverride(special_boost=SPECIALEnum.INTELLIGENCE)
                    dweller_obj = await dweller_crud.create_random(db_session, vault_id, dweller_data)
                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller_obj.id,
                        obj_in=DwellerUpdate(room_id=medbay_room.id, status=DwellerStatusEnum.WORKING),
                    )
                    self.logger.info(f"Dweller {dweller_obj.id} assigned to Medbay")

                # Create 2 dwellers for Science Lab
                for _ in range(2):
                    dweller_data = DwellerCreateCommonOverride(special_boost=SPECIALEnum.INTELLIGENCE)
                    dweller_obj = await dweller_crud.create_random(db_session, vault_id, dweller_data)
                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller_obj.id,
                        obj_in=DwellerUpdate(room_id=science_lab_room.id, status=DwellerStatusEnum.WORKING),
                    )
                    self.logger.info(f"Dweller {dweller_obj.id} assigned to Science Lab")

            # Training dwellers (boosted only)
            if is_boosted:
                training_stats = [
                    SPECIALEnum.STRENGTH,
                    SPECIALEnum.PERCEPTION,
                    SPECIALEnum.ENDURANCE,
                    SPECIALEnum.CHARISMA,
                    SPECIALEnum.INTELLIGENCE,
                    SPECIALEnum.AGILITY,
                    SPECIALEnum.LUCK,
                ]

                for i, training_stat in enumerate(training_stats):
                    if i < len(created_training_rooms):
                        room = created_training_rooms[i]
                        dweller_data = DwellerCreateCommonOverride(special_boost=training_stat)
                        dweller_obj = await dweller_crud.create_random(db_session, vault_id, dweller_data)

                        # Assign to training room with IDLE status (training service will update status)

                        await dweller_crud.update(
                            db_session=db_session,
                            id=dweller_obj.id,
                            obj_in=DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.IDLE),
                        )
                        self.logger.info(f"Dweller {dweller_obj.id} assigned to training room {room.id}")

            # Radio studio dweller (Charisma-based, for recruitment)
            if created_misc_rooms:
                radio_room = next((r for r in created_misc_rooms if "radio" in r.name.lower()), None)
                if radio_room:
                    dweller_data = DwellerCreateCommonOverride(special_boost=SPECIALEnum.CHARISMA)
                    dweller_obj = await dweller_crud.create_random(db_session, vault_id, dweller_data)
                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller_obj.id,
                        obj_in=DwellerUpdate(room_id=radio_room.id, status=DwellerStatusEnum.WORKING),
                    )
                    self.logger.info(f"Dweller {dweller_obj.id} assigned to Radio Studio")

            # Living quarters dwellers (opposite genders for birth testing)
            living_rooms = [r for r in created_capacity_rooms if "living" in r.name.lower()]
            if living_rooms:
                # Create one male and one female dweller in the first living room
                living_room = living_rooms[0]

                # Create male dweller
                male_dweller_data = DwellerCreateCommonOverride(gender=GenderEnum.MALE)
                male_dweller = await dweller_crud.create_random(db_session, vault_id, male_dweller_data)
                await dweller_crud.update(
                    db_session=db_session,
                    id=male_dweller.id,
                    obj_in=DwellerUpdate(room_id=living_room.id, status=DwellerStatusEnum.IDLE),
                )
                self.logger.info(f"Male dweller {male_dweller.id} assigned to living quarters for birth testing")

                # Create female dweller
                female_dweller_data = DwellerCreateCommonOverride(gender=GenderEnum.FEMALE)
                female_dweller = await dweller_crud.create_random(db_session, vault_id, female_dweller_data)
                await dweller_crud.update(
                    db_session=db_session,
                    id=female_dweller.id,
                    obj_in=DwellerUpdate(room_id=living_room.id, status=DwellerStatusEnum.IDLE),
                )
                self.logger.info(f"Female dweller {female_dweller.id} assigned to living quarters for birth testing")

        except Exception:
            self.logger.exception("Failed to create dwellers")
            raise

    async def _start_training_sessions(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        created_training_rooms: list[Room],
        is_boosted: bool,
    ) -> None:
        """Start training sessions for dwellers in training rooms (boosted only)."""
        if not is_boosted or not created_training_rooms:
            return

        try:
            # Batch-fetch all dwellers in training rooms via CRUD
            room_ids = [room.id for room in created_training_rooms]
            # Get all dwellers in vault via CRUD
            vault_dwellers = await dweller_crud.get_multi_by_vault(db_session, vault_id)
            # Filter by room_ids (training rooms)
            all_dwellers = [d for d in vault_dwellers if d.room_id in room_ids]

            # Group dwellers by room_id for processing
            dwellers_by_room = {}
            for dweller in all_dwellers:
                if dweller.room_id not in dwellers_by_room:
                    dwellers_by_room[dweller.room_id] = []
                dwellers_by_room[dweller.room_id].append(dweller)

            # Process each training room
            for room in created_training_rooms:
                # Re-fetch room to ensure all fields are loaded
                await db_session.refresh(room)
                self.logger.info(f"Room {room.id} ({room.name}) - tier: {room.tier}, ability: {room.ability}")

                dwellers = dwellers_by_room.get(room.id, [])

                for dweller in dwellers:
                    try:
                        # Refresh dweller to ensure all fields loaded
                        await db_session.refresh(dweller)

                        # Debug: Check dweller stats
                        stat_name = room.ability.value.lower() if room.ability else "unknown"
                        stat_value = getattr(dweller, stat_name, None) if room.ability else None
                        self.logger.info(
                            f"Dweller {dweller.id} {stat_name}={stat_value}, "
                            f"all stats: S={dweller.strength}, P={dweller.perception}, "
                            f"E={dweller.endurance}, status={dweller.status}"
                        )

                        await training_service.start_training(db_session, dweller.id, room.id)
                        self.logger.info(f"Started training for dweller {dweller.id} in room {room.id}")
                    except (ResourceNotFoundException, ResourceConflictException, ValueError) as e:
                        # Log error but continue with other dwellers
                        self.logger.warning(f"Failed to start training for dweller {dweller.id} in room {room.id}: {e}")
        except Exception as e:
            self.logger.error(f"Failed to start training sessions: {e}", exc_info=True)  # noqa: G201
            raise

    async def _assign_initial_objectives(
        self, db_session: AsyncSession, vault_id: UUID4, is_boosted: bool = False
    ) -> None:
        """Assign initial objectives to a new vault.

        Standard vaults get 1 daily and 1 weekly objective.
        Boosted vaults get additional achievement objectives (weapons, outfits, stimpaks, etc.)
        """
        try:
            from sqlmodel import select

            from app.models.objective import Objective

            assigned_count = 0
            assigned_types = []
            objectives_to_assign = []

            # Get 1 daily objective
            daily_result = await db_session.execute(
                select(Objective)
                .where(Objective.challenge.ilike("%daily%"))
                .where(Objective.objective_type.isnot(None))
                .order_by(Objective.id)
                .limit(1)
            )
            daily_objective = daily_result.scalar_one_or_none()
            if daily_objective:
                objectives_to_assign.append(daily_objective)
                assigned_types.append("daily")

            # Get 1 weekly objective
            weekly_result = await db_session.execute(
                select(Objective)
                .where(Objective.challenge.ilike("%weekly%"))
                .where(Objective.objective_type.isnot(None))
                .order_by(Objective.id)
                .limit(1)
            )
            weekly_objective = weekly_result.scalar_one_or_none()
            if weekly_objective:
                objectives_to_assign.append(weekly_objective)
                assigned_types.append("weekly")

            # For boosted vaults, add achievement objectives (collection, build, etc.)
            if is_boosted:
                # Get basic objectives (non-daily, non-weekly) with different types
                basic_result = await db_session.execute(
                    select(Objective)
                    .where(Objective.challenge.not_ilike("%daily%"))
                    .where(Objective.challenge.not_ilike("%weekly%"))
                    .where(Objective.objective_type.isnot(None))
                    .order_by(Objective.id)
                    .limit(8)
                )
                basic_objectives = basic_result.scalars().all()
                objectives_to_assign.extend(basic_objectives)
                if basic_objectives:
                    assigned_types.append(f"{len(basic_objectives)} achievement")

            # Assign all objectives
            for objective in objectives_to_assign:
                link = VaultObjectiveProgressLink(
                    vault_id=vault_id,
                    objective_id=objective.id,
                    progress=0,
                    total=objective.target_amount or 1,
                    is_completed=False,
                )
                db_session.add(link)
                assigned_count += 1

            if assigned_count > 0:
                await db_session.commit()
                types_str = ", ".join(assigned_types) if assigned_types else "objectives"
                self.logger.info(
                    "Assigned %d initial objective(s) (%s) to vault %s", assigned_count, types_str, vault_id
                )
            else:
                self.logger.warning("No objectives found for vault %s", vault_id)
        except SQLAlchemyError as e:
            self.logger.warning("Failed to assign initial objectives to vault %s: %s", vault_id, e)

    async def initiate_vault(
        self,
        db_session: AsyncSession,
        obj_in: VaultNumber,
        user_id: UUID4,
        is_boosted: bool = False,
    ) -> Vault:
        """
        Create a new vault for a user and initialize it with essential rooms and dwellers.

        Standard vault includes:
        - Vault door and elevators (infrastructure)
        - Production rooms (power generator, diner, water treatment) with assigned dwellers
        - Storage room and 1 living room
        - Radio studio (for recruitment)
        - Weight room (training room for testing leveling system)
        - 6 dwellers with boosted SPECIAL stats assigned to production rooms

        Boosted vault additionally includes:
        - All 7 training rooms (one for each SPECIAL stat)
        - 2 additional living rooms (3 total for 13+ dwellers)
        - 7 additional dwellers assigned to training rooms (13 total)
        """
        # Create vault and storage
        vault_db_obj = await vault_crud.create_with_user_id(db_session=db_session, obj_in=obj_in, user_id=user_id)
        await vault_crud.create_storage(db_session=db_session, vault_id=vault_db_obj.id)
        await db_session.refresh(vault_db_obj)

        # Prepare room data
        game_data_store = get_static_game_data()
        rooms = game_data_store.rooms
        infrastructure_rooms, capacity_rooms, production_rooms, misc_rooms, training_rooms = (
            self._prepare_initial_rooms(rooms, vault_db_obj.id, is_boosted)
        )

        # Create rooms and get created production/training/misc rooms
        (
            vault_db_obj,
            created_production_rooms,
            created_training_rooms,
            created_misc_rooms,
            created_capacity_rooms,
        ) = await self._create_initial_rooms(
            db_session, vault_db_obj, infrastructure_rooms, capacity_rooms, production_rooms, misc_rooms, training_rooms
        )

        # Set initial resources to 50% of max capacity
        initial_power = vault_db_obj.power_max // 2
        initial_food = vault_db_obj.food_max // 2
        initial_water = vault_db_obj.water_max // 2
        vault_db_obj = await vault_crud.update(
            db_session=db_session,
            id=vault_db_obj.id,
            obj_in=VaultUpdate(power=initial_power, food=initial_food, water=initial_water),
        )

        # Create and assign dwellers
        await self._create_initial_dwellers(
            db_session,
            vault_db_obj.id,
            created_production_rooms,
            created_training_rooms,
            created_misc_rooms,
            created_capacity_rooms,
            is_boosted,
        )

        # Commit to ensure all dwellers and rooms are persisted before starting training
        await db_session.commit()

        # Start training sessions for boosted vaults
        await self._start_training_sessions(db_session, vault_db_obj.id, created_training_rooms, is_boosted)

        # Assign initial objectives to the vault (boosted vaults get more objectives)
        await self._assign_initial_objectives(db_session, vault_db_obj.id, is_boosted)

        return vault_db_obj

    async def update_vault_resources(self, db_session: AsyncSession, vault_id: UUID4) -> Vault:
        """Update vault resources based on resource manager processing."""
        updated_resources, _events = await self.resource_manager.process_vault_resources(
            db_session=db_session, vault_id=vault_id, seconds_passed=60
        )

        return await vault_crud.update(db_session=db_session, id=vault_id, obj_in=updated_resources)


# Singleton instance
vault_service = VaultService()
