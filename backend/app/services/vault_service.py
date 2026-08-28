"""Service for vault initialization and resource management."""

import logging

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.game_data_deps import get_static_game_data
from app.core.game_config import compute_medical_capacity
from app.crud import dweller as dweller_crud
from app.crud import room as room_crud
from app.crud.storage import storage as storage_crud
from app.crud.vault import vault as vault_crud
from app.models import Room, Storage
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import DwellerStatusEnum, GenderEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreateCommonOverride, DwellerUpdate
from app.schemas.room import RoomCreate
from app.schemas.vault import MedicalTransferResponse, VaultNumber, VaultUpdate
from app.services.resource_manager import ResourceManager
from app.services.training_service import training_service
from app.utils.dwellers import group_dwellers_by_room
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

    async def _create_initial_rooms(
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
                # Living rooms: ability=Charisma
                if created_room.ability == SPECIALEnum.CHARISMA:
                    vault.population_max += created_room.capacity or 0
                # Storage rooms: ability=Endurance
                elif created_room.ability == SPECIALEnum.ENDURANCE and created_room.capacity:
                    # Storage rooms increase Storage.max_space, not individual vault capacities
                    # Query current storage max_space to avoid lazy load issue
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
            assignments = [
                (room, stat, 2)
                for room, stat in zip(
                    created_production_rooms[:3],
                    (SPECIALEnum.STRENGTH, SPECIALEnum.AGILITY, SPECIALEnum.PERCEPTION),
                    strict=True,
                )
            ]
            if is_boosted and len(created_production_rooms) >= 5:
                assignments.extend((room, SPECIALEnum.INTELLIGENCE, 2) for room in created_production_rooms[3:5])
            for room, boosted_stat, count in assignments:
                for _ in range(count):
                    dweller_obj = await dweller_crud.create_random(
                        db_session, vault_id, DwellerCreateCommonOverride(special_boost=boosted_stat)
                    )
                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller_obj.id,
                        obj_in=DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.WORKING),
                    )
                    self.logger.info("Dweller %s assigned to %s", dweller_obj.id, room.name)

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

            living_rooms = [r for r in created_capacity_rooms if "living" in r.name.lower()]
            if living_rooms:
                living_room = living_rooms[0]
                for gender in (GenderEnum.MALE, GenderEnum.FEMALE):
                    dweller_data = DwellerCreateCommonOverride(
                        gender=gender,
                        special_boost=SPECIALEnum.CHARISMA if is_boosted else None,
                    )
                    dweller = await dweller_crud.create_random(db_session, vault_id, dweller_data)
                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller.id,
                        obj_in=DwellerUpdate(room_id=living_room.id, status=DwellerStatusEnum.RESTING),
                    )
                    self.logger.info("Dweller %s assigned to living quarters for socializing", dweller.id)

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
            dwellers_by_room = group_dwellers_by_room(all_dwellers)

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
        except Exception:
            self.logger.exception("Failed to start training sessions")
            raise

    async def _create_initial_items(self, db_session: AsyncSession, vault_id: UUID4) -> None:
        """Create initial weapons and outfits for testing."""

        from app.models.outfit import Outfit
        from app.models.weapon import Weapon
        from app.schemas.common import (
            OutfitTypeEnum,
            RarityEnum,
            WeaponSubtypeEnum,
            WeaponTypeEnum,
        )
        from app.utils.outfit_assets import get_outfit_image_url
        from app.utils.weapon_assets import get_weapon_image_url

        storage = await storage_crud.get_by_vault(db_session, vault_id)
        if not storage:
            return

        weapons_data = [
            {
                "name": "Rusty Pistol",
                "rarity": RarityEnum.COMMON,
                "value": 50,
                "weapon_type": WeaponTypeEnum.GUN,
                "weapon_subtype": WeaponSubtypeEnum.PISTOL,
                "stat": "agility",
                "damage_min": 2,
                "damage_max": 5,
            },
            {
                "name": "Hunting Rifle",
                "rarity": RarityEnum.RARE,
                "value": 150,
                "weapon_type": WeaponTypeEnum.GUN,
                "weapon_subtype": WeaponSubtypeEnum.RIFLE,
                "stat": "perception",
                "damage_min": 5,
                "damage_max": 12,
            },
            {
                "name": "Sledgehammer",
                "rarity": RarityEnum.RARE,
                "value": 300,
                "weapon_type": WeaponTypeEnum.MELEE,
                "weapon_subtype": WeaponSubtypeEnum.BLUNT,
                "stat": "strength",
                "damage_min": 8,
                "damage_max": 15,
            },
            {
                "name": "Laser Pistol",
                "rarity": RarityEnum.LEGENDARY,
                "value": 500,
                "weapon_type": WeaponTypeEnum.ENERGY,
                "weapon_subtype": WeaponSubtypeEnum.PISTOL,
                "stat": "intelligence",
                "damage_min": 10,
                "damage_max": 20,
            },
        ]

        outfits_data = [
            {
                "name": "Vault Jumpsuit",
                "rarity": RarityEnum.COMMON,
                "value": 20,
                "outfit_type": OutfitTypeEnum.COMMON,
                "gender": None,
            },
            {
                "name": "Leather Armor",
                "rarity": RarityEnum.RARE,
                "value": 100,
                "outfit_type": OutfitTypeEnum.RARE,
                "gender": None,
            },
            {
                "name": "Metal Armor",
                "rarity": RarityEnum.RARE,
                "value": 250,
                "outfit_type": OutfitTypeEnum.RARE,
                "gender": None,
            },
            {
                "name": "T-51b Power Armor",
                "rarity": RarityEnum.LEGENDARY,
                "value": 1000,
                "outfit_type": OutfitTypeEnum.POWER_ARMOR,
                "gender": None,
            },
        ]

        for weapon_data in weapons_data:
            weapon_data["image_url"] = get_weapon_image_url(weapon_data["name"])
            weapon = Weapon(**weapon_data, storage_id=storage.id)
            db_session.add(weapon)

        for outfit_data in outfits_data:
            outfit_data["image_url"] = get_outfit_image_url(outfit_data["name"])
            outfit = Outfit(**outfit_data, storage_id=storage.id)
            db_session.add(outfit)

        await db_session.commit()
        self.logger.info(f"Created initial items for vault {vault_id}")

    async def _create_boosted_legendary_dwellers(self, db_session: AsyncSession, vault_id: UUID4) -> None:
        """Add a small, equipped legendary roster for boosted-vault testing."""
        from app.models.dweller import Dweller
        from app.models.outfit import Outfit
        from app.models.weapon import Weapon
        from app.schemas.common import OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
        from app.utils.outfit_assets import get_outfit_image_url
        from app.utils.static_data import game_data_store
        from app.utils.weapon_assets import get_weapon_image_url

        loadouts = {
            "Abraham Washington": ("Lever-action rifle", "Abraham's relaxedwear"),
            "Allistair Tenpenny": ("Hunting rifle", "Eulogy Jones' suit"),
            "Bittercup": ("10mm pistol", "Bittercup's outfit"),
        }
        templates = {
            f"{dweller.first_name} {dweller.last_name or ''}".strip(): dweller
            for dweller in game_data_store.dwellers
            if dweller.rarity.lower() == RarityEnum.LEGENDARY.value
        }

        for name, (weapon_name, outfit_name) in loadouts.items():
            template = templates[name]
            dweller = Dweller(**template.model_dump(exclude={"weapon", "outfit"}), vault_id=vault_id)
            db_session.add(dweller)
            await db_session.flush()
            db_session.add(
                Weapon(
                    name=weapon_name,
                    rarity=RarityEnum.LEGENDARY,
                    weapon_type=WeaponTypeEnum.GUN,
                    weapon_subtype=WeaponSubtypeEnum.RIFLE if "rifle" in weapon_name else WeaponSubtypeEnum.PISTOL,
                    stat="perception",
                    damage_min=12,
                    damage_max=20,
                    image_url=get_weapon_image_url(weapon_name),
                    dweller_id=dweller.id,
                )
            )
            db_session.add(
                Outfit(
                    name=outfit_name,
                    rarity=RarityEnum.LEGENDARY,
                    outfit_type=OutfitTypeEnum.LEGENDARY,
                    image_url=get_outfit_image_url(outfit_name),
                    dweller_id=dweller.id,
                )
            )

        await db_session.commit()

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
                .where(Objective.category == "daily")
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
                .where(Objective.category == "weekly")
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
                    .where(Objective.category != "daily")
                    .where(Objective.category != "weekly")
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
        """Create a new vault for a user and initialize it with essential rooms and dwellers.

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
        game_data_store = await get_static_game_data()
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
            obj_in=VaultUpdate(
                power=initial_power,
                food=initial_food,
                water=initial_water,
            ),
        )

        # Set initial medical supplies on Storage (computed from Medbay/Science Lab rooms)
        all_rooms = created_production_rooms + created_capacity_rooms + created_training_rooms + created_misc_rooms
        medical_capacity = compute_medical_capacity(all_rooms)
        initial_stimpack = min(5, medical_capacity.get("stimpack", 0))
        initial_radaway = min(5, medical_capacity.get("radaway", 0))
        if initial_stimpack > 0 or initial_radaway > 0:
            storage_obj = await storage_crud.get_by_vault(db_session, vault_db_obj.id)
            if storage_obj:
                storage_obj.stimpack = initial_stimpack
                storage_obj.radaway = initial_radaway
                db_session.add(storage_obj)
                await db_session.commit()

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

        if is_boosted:
            await self._create_boosted_legendary_dwellers(db_session, vault_db_obj.id)

        # Commit to ensure all dwellers and rooms are persisted before starting training
        await db_session.commit()

        # Start training sessions for boosted vaults
        await self._start_training_sessions(db_session, vault_db_obj.id, created_training_rooms, is_boosted)

        # Assign initial objectives to the vault (boosted vaults get more objectives)
        await self._assign_initial_objectives(db_session, vault_db_obj.id, is_boosted)

        # Create initial weapons and outfits for testing
        await self._create_initial_items(db_session, vault_db_obj.id)

        return vault_db_obj

    async def update_vault_resources(self, db_session: AsyncSession, vault_id: UUID4) -> Vault:
        """Update vault resources based on resource manager processing."""
        updated_resources, events = await self.resource_manager.process_vault_resources(
            db_session=db_session, vault_id=vault_id, seconds_passed=60
        )
        vault_obj = await vault_crud.update(db_session=db_session, id=vault_id, obj_in=updated_resources)
        await self.resource_manager.emit_production_events(vault_id, events)
        return vault_obj

    async def transfer_medical_supplies(
        self,
        db_session: AsyncSession,
        vault: Vault,
        dweller_id: UUID4,
        stimpaks: int,
        radaways: int,
    ) -> dict:
        """Transfer medical supplies from vault storage to a dweller's inventory.

        Dwellers can carry max 15 stimpaks and 15 radaways each.
        """
        storage = await storage_crud.get_by_vault(db_session, vault.id)
        if not storage:
            raise ResourceNotFoundException(model=Storage, identifier=vault.id)

        vault_stimpaks = storage.stimpack or 0
        vault_radaways = storage.radaway or 0

        if stimpaks > vault_stimpaks:
            raise ResourceConflictException(detail=f"Vault only has {vault_stimpaks} stimpaks")
        if radaways > vault_radaways:
            raise ResourceConflictException(detail=f"Vault only has {vault_radaways} radaways")

        dweller = await dweller_crud.get(db_session, dweller_id)

        if dweller.vault_id != vault.id:
            from app.utils.exceptions import AccessDeniedException

            raise AccessDeniedException(detail="Dweller does not belong to this vault")

        dweller_stimpaks = dweller.stimpack or 0
        dweller_radaways = dweller.radaway or 0

        max_per_dweller = 15
        if stimpaks + dweller_stimpaks > max_per_dweller:
            raise ResourceConflictException(detail=f"Dweller can only carry {max_per_dweller} stimpaks")
        if radaways + dweller_radaways > max_per_dweller:
            raise ResourceConflictException(detail=f"Dweller can only carry {max_per_dweller} radaways")

        new_storage_stimpaks = vault_stimpaks - stimpaks
        new_storage_radaways = vault_radaways - radaways
        new_dweller_stimpaks = dweller_stimpaks + stimpaks
        new_dweller_radaways = dweller_radaways + radaways

        try:
            storage.stimpack = new_storage_stimpaks
            storage.radaway = new_storage_radaways
            db_session.add(storage)

            await dweller_crud.update(
                db_session,
                dweller_id,
                obj_in={"stimpack": new_dweller_stimpaks, "radaway": new_dweller_radaways},
                commit=False,
            )

            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

        self.logger.info(
            "Medical supplies transferred",
            extra={
                "vault_id": str(vault.id),
                "dweller_id": str(dweller_id),
                "stimpaks_transferred": stimpaks,
                "radaways_transferred": radaways,
            },
        )

        return MedicalTransferResponse(
            vault_stimpaks=new_storage_stimpaks,
            vault_radaways=new_storage_radaways,
            dweller_stimpaks=new_dweller_stimpaks,
            dweller_radaways=new_dweller_radaways,
        )


# Singleton instance
vault_service = VaultService()
