"""Service for vault initialization and resource management."""

import logging
import random
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.game_data_deps import get_static_game_data
from app.core.enums import (
    AgeGroupEnum,
    DwellerStatusEnum,
    GenderEnum,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud import outfit as outfit_crud
from app.crud import room as room_crud
from app.crud import weapon as weapon_crud
from app.crud.storage import storage as storage_crud
from app.crud.vault import vault as vault_crud
from app.models import Dweller, Room, Storage
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreateCommonOverride, DwellerUpdate
from app.schemas.room import RoomCreate
from app.schemas.vault import MedicalTransferResponse, VaultNumber, VaultUpdate
from app.services.resource_manager import ResourceManager, compute_medical_capacity
from app.services.training_service import training_service
from app.services.vault_seed import (
    BOOSTED_LIVING_ROOM_COORDINATES,
    BOOSTED_LOADOUTS,
    BOOSTED_TRAINING_STATS,
    SEED_OUTFITS,
    SEED_WEAPONS,
    YOUTH_APPRENTICE_BIRTH_AGE_HOURS,
    CreatedRooms,
    PreparedRooms,
)
from app.utils.dwellers import group_dwellers_by_room
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


class VaultService:
    """Service for vault initialization and management."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.resource_manager = ResourceManager()

    @staticmethod
    def _build_room(rooms_by_name: dict[str, RoomCreate], name: str, vault_id: UUID4, x: int, y: int) -> RoomCreate:
        template = rooms_by_name.get(name.lower())
        if template is None:
            raise ValueError(f"Room template '{name}' not found")
        data = template.model_dump()
        size = data["size_min"]
        tier = 1
        if data.get("capacity_formula"):
            data["capacity"] = room_crud.evaluate_capacity_formula(data["capacity_formula"], tier, size)
        if data.get("output_formula"):
            data["output"] = room_crud.evaluate_output_formula(data["output_formula"], tier, size)
        data.update(vault_id=vault_id, size=size, tier=tier, coordinate_x=x, coordinate_y=y)
        return RoomCreate(**data)

    @staticmethod
    def _prepare_room_data(rooms: list[RoomCreate], room_name: str, vault_id: UUID4, x: int, y: int) -> dict:
        rooms_by_name = {r.name.lower(): r for r in rooms}
        return VaultService._build_room(rooms_by_name, room_name, vault_id, x, y).model_dump()

    def _prepare_initial_rooms(
        self,
        rooms: list[RoomCreate],
        vault_id: UUID4,
        is_boosted: bool,
    ) -> PreparedRooms:
        rooms_by_name = {r.name.lower(): r for r in rooms}

        def mk(specs: list[tuple[str, int, int]]) -> list[RoomCreate]:
            return [self._build_room(rooms_by_name, n, vault_id, x, y) for n, x, y in specs]

        infrastructure = mk([("vault door", 0, 0), ("elevator", 0, 1), ("elevator", 0, 2), ("elevator", 0, 3)])
        if is_boosted:
            living_template = rooms_by_name.get("living room")
            cap_per = (
                room_crud.evaluate_capacity_formula(living_template.capacity_formula, 1, living_template.size_min)
                if living_template and living_template.capacity_formula
                else 8
            )
            expected_dwellers = 25
            needed_living = (expected_dwellers + cap_per - 1) // cap_per
            extra_living = BOOSTED_LIVING_ROOM_COORDINATES[: max(0, needed_living - 1)]
            capacity_specs = [("living room", 2, 1), ("storage room", 2, 2)] + [
                ("living room", x, y) for x, y in extra_living
            ]
        else:
            capacity_specs = [("living room", 2, 1), ("storage room", 2, 2)]
        capacity = mk(capacity_specs)
        production = mk(
            [("power generator", 1, 1), ("diner", 1, 2), ("water treatment", 1, 3)]
            + ([("medbay", 7, 1), ("science lab", 7, 2)] if is_boosted else [])
        )
        misc = mk([("radio studio", 2, 3)] + ([("overseer's office", 6, 2)] if is_boosted else []))
        arena = mk([("arena", 6, 3)] if is_boosted else [])
        training = mk(
            [
                ("weight room", 3, 1),
                ("armory", 3, 2),
                ("athletics room", 4, 1),
                ("classroom", 4, 2),
                ("game room", 5, 1),
                ("fitness room", 5, 2),
                ("lounge", 6, 1),
            ]
            if is_boosted
            else []
        )
        return PreparedRooms(
            infrastructure=infrastructure,
            capacity=capacity,
            production=production,
            misc=misc,
            training=training,
            arena=arena,
        )

    async def _create_initial_rooms(
        self,
        db_session: AsyncSession,
        vault: Vault,
        prepared: PreparedRooms,
    ) -> tuple[Vault, CreatedRooms]:
        async def create_batch(rooms: list[RoomCreate]) -> list[Room]:
            return [await room_crud.create(db_session, r) for r in rooms]

        for r in prepared.infrastructure:
            await room_crud.create(db_session, r)

        created_capacity = await create_batch(prepared.capacity)
        for room in created_capacity:
            if room.category == RoomTypeEnum.CAPACITY:
                if room.ability == SPECIALEnum.CHARISMA:
                    vault.population_max += room.capacity or 0
                elif room.ability == SPECIALEnum.ENDURANCE and room.capacity:
                    await storage_crud.adjust_max_space(db_session, vault.id, room.capacity)

        await db_session.commit()
        await db_session.refresh(vault)

        created_production = await create_batch(prepared.production)
        for room in created_production:
            if room.ability and room.capacity:
                match room.ability.value.lower():
                    case "strength":
                        vault.power_max += room.capacity
                    case "agility":
                        vault.food_max += room.capacity
                    case "perception":
                        vault.water_max += room.capacity

        created_misc = await create_batch(prepared.misc)
        created_training = await create_batch(prepared.training)
        created_arena = await create_batch(prepared.arena)

        await db_session.commit()
        await db_session.refresh(vault)
        for room in created_production + created_training + created_misc + created_capacity + created_arena:
            await db_session.refresh(room)

        return vault, CreatedRooms(
            production=created_production,
            training=created_training,
            misc=created_misc,
            capacity=created_capacity,
            arena=created_arena,
        )

    def _roll_initial_rarity(self, is_boosted: bool) -> RarityEnum:
        """Roll RARE for initial seeded dwellers; boosted vaults use the higher chance."""
        vault_start = game_config.vault_start
        chance = vault_start.boosted_rare_chance if is_boosted else vault_start.standard_rare_chance
        return RarityEnum.RARE if random.random() < chance else RarityEnum.COMMON

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
                        db_session,
                        vault_id,
                        DwellerCreateCommonOverride(special_boost=boosted_stat),
                        rarity=self._roll_initial_rarity(is_boosted),
                    )
                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller_obj.id,
                        obj_in=DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.WORKING),
                    )
                    self.logger.info("Dweller %s assigned to %s", dweller_obj.id, room.name)

            # Training dwellers (boosted only)
            if is_boosted:
                for i, training_stat in enumerate(BOOSTED_TRAINING_STATS):
                    if i < len(created_training_rooms):
                        room = created_training_rooms[i]
                        dweller_data = DwellerCreateCommonOverride(special_boost=training_stat)
                        dweller_obj = await dweller_crud.create_random(
                            db_session, vault_id, dweller_data, rarity=self._roll_initial_rarity(is_boosted)
                        )

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
                    dweller_obj = await dweller_crud.create_random(
                        db_session, vault_id, dweller_data, rarity=self._roll_initial_rarity(is_boosted)
                    )
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
                    dweller = await dweller_crud.create_random(
                        db_session, vault_id, dweller_data, rarity=self._roll_initial_rarity(is_boosted)
                    )
                    if is_boosted and dweller.charisma != game_config.dweller.boosted_stat_value:
                        await dweller_crud.update(
                            db_session, dweller.id, {"charisma": game_config.dweller.boosted_stat_value}
                        )
                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller.id,
                        obj_in=DwellerUpdate(room_id=living_room.id, status=DwellerStatusEnum.RESTING),
                    )
                    self.logger.info("Dweller %s assigned to living quarters for socializing", dweller.id)

            # Youth apprentices (boosted only) — one per production room, so the
            # apprentice lifecycle is testable end-to-end. Seeded as teens via
            # _seed_youth_apprentice; the seeded vault intentionally skips the
            # population gate.
            if is_boosted:
                for room in created_production_rooms[:2]:
                    if room.ability is None:
                        continue
                    youth_data = DwellerCreateCommonOverride(special_boost=room.ability)
                    youth = await dweller_crud.create_random(
                        db_session, vault_id, youth_data, rarity=self._roll_initial_rarity(is_boosted)
                    )
                    await self._seed_youth_apprentice(db_session, youth.id, room)
                    self.logger.info("Youth %s apprenticed in %s", youth.id, room.name)

        except Exception:
            self.logger.exception("Failed to create dwellers")
            raise

    async def _seed_youth_apprentice(self, db_session: AsyncSession, youth_id: UUID4, room: Room) -> None:
        """Mark a seeded teen as an apprentice of a production room."""
        await dweller_crud.update(
            db_session,
            youth_id,
            {
                "is_adult": False,
                "age_group": AgeGroupEnum.TEEN,
                "birth_date": datetime.utcnow() - timedelta(hours=YOUTH_APPRENTICE_BIRTH_AGE_HOURS),
                "room_id": room.id,
                "status": DwellerStatusEnum.WORKING,
                "apprentice_stat": room.ability,
                "apprentice_started_at": datetime.utcnow(),
            },
        )

    async def _start_dweller_training(self, db_session: AsyncSession, dweller: Dweller, room: Room) -> None:
        """Start one training session; domain failures are logged, not raised."""
        try:
            await db_session.refresh(dweller)
            await training_service.start_training(db_session, dweller.id, room.id)
            self.logger.info(f"Started training for dweller {dweller.id} in room {room.id}")
        except (ResourceNotFoundException, ResourceConflictException, ValueError) as e:
            self.logger.warning(f"Failed to start training for dweller {dweller.id} in room {room.id}: {e}")

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
                    await self._start_dweller_training(db_session, dweller, room)
        except Exception:
            self.logger.exception("Failed to start training sessions")
            raise

    async def _create_initial_items(self, db_session: AsyncSession, vault_id: UUID4) -> None:
        """Create initial weapons and outfits for testing."""

        from app.models.outfit import Outfit
        from app.models.weapon import Weapon
        from app.utils.outfit_assets import get_outfit_image_url
        from app.utils.weapon_assets import get_weapon_image_url

        storage = await storage_crud.get_by_vault(db_session, vault_id)
        if not storage:
            return

        weapons = [
            Weapon(
                **{**weapon_data, "image_url": get_weapon_image_url(weapon_data["name"])},
                storage_id=storage.id,
            )
            for weapon_data in SEED_WEAPONS
        ]
        outfits = [
            Outfit(
                **{**outfit_data, "image_url": get_outfit_image_url(outfit_data["name"])},
                storage_id=storage.id,
            )
            for outfit_data in SEED_OUTFITS
        ]
        await weapon_crud.create_many(db_session, weapons)
        await outfit_crud.create_many(db_session, outfits)
        self.logger.info(f"Created initial items for vault {vault_id}")

    async def _create_boosted_legendary_dwellers(self, db_session: AsyncSession, vault_id: UUID4) -> None:
        """Add a small, equipped legendary roster for boosted-vault testing via shared flow."""
        from app.core.enums import OutfitTypeEnum, RarityEnum, WeaponTypeEnum
        from app.crud.dweller import dweller as dweller_crud
        from app.models.outfit import Outfit
        from app.models.weapon import Weapon
        from app.utils.outfit_assets import get_outfit_image_url
        from app.utils.weapon_assets import get_weapon_image_url

        legendary_weapons = []
        legendary_outfits = []
        for template_id, weapon_name, outfit_name, weapon_subtype in BOOSTED_LOADOUTS:
            try:
                dweller = await dweller_crud.create_from_template(db_session, vault_id, template_id)
            except ResourceConflictException:
                self.logger.info("Boosted template %s already active in vault %s, skipping", template_id, vault_id)
                continue
            legendary_weapons.append(
                Weapon(
                    name=weapon_name,
                    rarity=RarityEnum.LEGENDARY,
                    weapon_type=WeaponTypeEnum.GUN,
                    weapon_subtype=weapon_subtype,
                    stat="perception",
                    damage_min=12,
                    damage_max=20,
                    image_url=get_weapon_image_url(weapon_name),
                    dweller_id=dweller.id,
                )
            )
            legendary_outfits.append(
                Outfit(
                    name=outfit_name,
                    rarity=RarityEnum.LEGENDARY,
                    outfit_type=OutfitTypeEnum.LEGENDARY,
                    image_url=get_outfit_image_url(outfit_name),
                    dweller_id=dweller.id,
                )
            )

        if legendary_weapons:
            await weapon_crud.create_many(db_session, legendary_weapons)
        if legendary_outfits:
            await outfit_crud.create_many(db_session, legendary_outfits)

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
        prepared = self._prepare_initial_rooms(rooms, vault_db_obj.id, is_boosted)

        # Create rooms and get created production/training/misc rooms
        vault_db_obj, created = await self._create_initial_rooms(db_session, vault_db_obj, prepared)
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
        from app.crud.objective import objective_crud

        assigned = await objective_crud.assign_initial(db_session, vault_db_obj.id, is_boosted=is_boosted)
        if assigned == 0:
            self.logger.warning("No objectives found for vault %s", vault_db_obj.id)

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
