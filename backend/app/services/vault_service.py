"""Service for vault initialization and resource management."""

import logging
import random
from datetime import datetime, timedelta
from itertools import starmap

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import (
    AgeGroupEnum,
    DwellerStatusEnum,
    GenderEnum,
    RarityEnum,
    RoomActionEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.game_config import game_config
from app.core.game_data import get_static_game_data
from app.core.grid_config import SHAFT_X
from app.crud import dweller as dweller_crud
from app.crud import outfit as outfit_crud
from app.crud import room as room_crud
from app.crud import weapon as weapon_crud
from app.crud.relationship import relationship_crud
from app.crud.storage import storage as storage_crud
from app.crud.vault import vault as vault_crud
from app.models import Dweller, Room, Storage
from app.models.outfit import Outfit
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreateCommonOverride, DwellerUpdate
from app.schemas.room import RoomCreate, RoomCreateWithoutVaultID
from app.schemas.vault import MedicalTransferResponse, VaultNumber, VaultReadWithNumbers, VaultUpdate
from app.services.resource_manager import ResourceManager, compute_medical_capacity
from app.services.training_service import training_service
from app.services.vault_seed import (
    BOOSTED_CRAFTING_ROOM_SPECS,
    BOOSTED_LOADOUTS,
    BOOSTED_MERGED_LIVING_ROOM,
    BOOSTED_SEED_JUNK,
    BOOSTED_SEED_OUTFITS,
    BOOSTED_TRAINING_STATS,
    SEED_OUTFITS,
    SEED_WEAPONS,
    SEEDED_CHILD_AGE_HOURS,
    SEEDED_COUPLE_AFFINITY,
    SEEDED_COUPLE_STAGE,
    SEEDED_FAMILIES_BOOSTED,
    SEEDED_FAMILIES_STANDARD,
    YOUTH_APPRENTICE_BIRTH_AGE_HOURS,
    CreatedRooms,
    PreparedRooms,
)
from app.utils.dwellers import group_dwellers_by_room
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceConflictException,
    ResourceNotFoundException,
)
from app.utils.item_factory import build_outfit, build_weapon
from app.utils.resource_warnings import get_resource_warnings


class VaultService:
    """Service for vault initialization and management."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.resource_manager = ResourceManager()

    @staticmethod
    def _build_room(
        rooms_by_name: dict[str, RoomCreateWithoutVaultID],
        name: str,
        vault_id: UUID4,
        x: int,
        y: int,
        size: int | None = None,
    ) -> RoomCreate:
        template = rooms_by_name.get(name.lower())
        if template is None:
            raise ValueError(f"Room template '{name}' not found")
        data = template.model_dump()
        size = size if size is not None else data["size_min"]
        if size > data["size_max"]:
            raise ValueError(f"Room '{name}' cannot span {size} units (max {data['size_max']})")
        tier = 1
        if data.get("capacity_formula"):
            data["capacity"] = room_crud.evaluate_capacity_formula(data["capacity_formula"], tier, size)
        if data.get("output_formula"):
            data["output"] = room_crud.evaluate_output_formula(data["output_formula"], tier, size)
        data.update(vault_id=vault_id, size=size, tier=tier, coordinate_x=x, coordinate_y=y)
        return RoomCreate(**data)

    @staticmethod
    def _prepare_room_data(
        rooms: list[RoomCreateWithoutVaultID], room_name: str, vault_id: UUID4, x: int, y: int
    ) -> dict:
        rooms_by_name = {r.name.lower(): r for r in rooms}
        return VaultService._build_room(rooms_by_name, room_name, vault_id, x, y).model_dump()

    def _prepare_initial_rooms(
        self,
        rooms: list[RoomCreateWithoutVaultID],
        vault_id: UUID4,
        is_boosted: bool,
    ) -> PreparedRooms:
        rooms_by_name = {r.name.lower(): r for r in rooms}

        def mk(specs: list[tuple[str, int, int]]) -> list[RoomCreate]:
            return [self._build_room(rooms_by_name, n, vault_id, x, y) for n, x, y in specs]

        def mk_sized(specs: list[tuple[str, int, int, int]]) -> list[RoomCreate]:
            return [self._build_room(rooms_by_name, n, vault_id, x, y, size=s) for n, x, y, s in specs]

        infrastructure = mk([("vault door", 0, 0), *[("elevator", SHAFT_X, level) for level in range(4)]])
        if is_boosted:
            # Boosted blocks read top to bottom: level 1 is the training block,
            # level 2 holds the storage row with medbay and science lab side by
            # side, level 3 the living block; the storage row fuses at seed time.
            capacity_specs = [
                ("living room", 25, 3, 3),
                ("storage room", 7, 2, 3),
                ("storage room", 10, 2, 3),
                ("storage room", 13, 2, 3),
                BOOSTED_MERGED_LIVING_ROOM,
            ]
        else:
            capacity_specs = [("living room", 7, 1, 3), ("storage room", 7, 2, 3)]
        capacity = mk_sized(capacity_specs)
        production = mk(
            [("power generator", 3, 1), ("diner", 3, 2), ("water treatment", 3, 3)]
            + ([("science lab", 19, 2), ("medbay", 16, 2)] if is_boosted else [])
        )
        misc = mk([("radio studio", 7, 3)] + ([("overseer's office", 22, 2)] if is_boosted else []))
        arena = mk([("arena", 10, 3)] if is_boosted else [])
        crafting = mk(list(BOOSTED_CRAFTING_ROOM_SPECS)) if is_boosted else []
        training = mk(
            [
                ("weight room", 7, 1),
                ("athletics room", 10, 1),
                ("game room", 13, 1),
                ("lounge", 16, 1),
                ("armory", 19, 1),
                ("classroom", 22, 1),
                ("fitness room", 25, 1),
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
            crafting=crafting,
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
                    vault.population_max = (vault.population_max or 0) + (room.capacity or 0)
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
        created_crafting = await create_batch(prepared.crafting)

        await db_session.commit()
        await db_session.refresh(vault)
        for room in (
            created_production + created_training + created_misc + created_capacity + created_arena + created_crafting
        ):
            await db_session.refresh(room)

        await self._merge_adjacent_seed_rooms(db_session, vault.id)

        return vault, CreatedRooms(
            production=created_production,
            training=created_training,
            misc=created_misc,
            capacity=created_capacity,
            arena=created_arena,
            crafting=created_crafting,
        )

    async def _merge_adjacent_seed_rooms(self, db_session: AsyncSession, vault_id: UUID4) -> None:
        """Fuse adjacent same-name seed rooms (the boosted storage row) through the standard merge flow."""
        from app.services.room_service import room_service

        await room_service.backfill_merge_rooms_for_vault(db_session, vault_id, dry_run=False)

    def _roll_initial_rarity(self, is_boosted: bool) -> RarityEnum:
        """Roll RARE for initial seeded dwellers; boosted vaults use the higher chance."""
        vault_start = game_config.vault_start
        chance = vault_start.boosted_rare_chance if is_boosted else vault_start.standard_rare_chance
        return RarityEnum.RARE if random.random() < chance else RarityEnum.COMMON

    async def _seed_working_dweller(
        self, db_session: AsyncSession, vault_id: UUID4, room: Room, boosted_stat: SPECIALEnum, is_boosted: bool
    ) -> Dweller:
        """Create a dweller and assign it to a room as a worker."""
        from app.services.dweller_service import dweller_service

        dweller_obj = await dweller_service.create_random_dweller(
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
        dweller_obj.room_id = room.id
        self.logger.info("Dweller %s assigned to %s", dweller_obj.id, room.name)
        return dweller_obj

    async def _create_initial_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        created_production_rooms: list[Room],
        created_training_rooms: list[Room],
        created_misc_rooms: list[Room],
        created_capacity_rooms: list[Room],
        is_boosted: bool,
        created_crafting_rooms: list[Room] | None = None,
    ) -> None:
        """Create and assign initial dwellers to production, training, and crafting rooms."""
        from app.services.dweller_service import dweller_service

        try:
            # Boosted vaults staff production heavier so the population clears 32.
            production_crew = 3 if is_boosted else 2
            assignments = [
                (room, stat, production_crew)
                for room, stat in zip(
                    created_production_rooms[:3],
                    (SPECIALEnum.STRENGTH, SPECIALEnum.AGILITY, SPECIALEnum.PERCEPTION),
                    strict=True,
                )
            ]
            if is_boosted and len(created_production_rooms) >= 5:
                assignments.extend(
                    (room, SPECIALEnum.INTELLIGENCE, production_crew) for room in created_production_rooms[3:5]
                )
            apprentice_rooms = [r for r in created_production_rooms[:2] if r.ability is not None]
            apprentice_ids = {r.id for r in apprentice_rooms}
            if is_boosted:
                # Rooms hosting a family teen keep one slot free, so production
                # rooms never hold more than three dwellers.
                assignments = [
                    (room, stat, count - (1 if room.id in apprentice_ids else 0)) for room, stat, count in assignments
                ]
            workers = [
                await self._seed_working_dweller(db_session, vault_id, room, boosted_stat, is_boosted)
                for room, boosted_stat, count in assignments
                for _ in range(count)
            ]

            # Crafting crew (boosted only): two dwellers per workshop, keyed to the
            # stats most craftable weapons and outfits use so orders finish faster.
            crafting_rooms = created_crafting_rooms or []
            if is_boosted and len(crafting_rooms) >= 2:
                weapon_room, outfit_room = crafting_rooms[0], crafting_rooms[1]
                for room, boosted_stat in (
                    (weapon_room, SPECIALEnum.STRENGTH),
                    (weapon_room, SPECIALEnum.AGILITY),
                    (outfit_room, SPECIALEnum.STRENGTH),
                    (outfit_room, SPECIALEnum.PERCEPTION),
                ):
                    workers.append(
                        await self._seed_working_dweller(db_session, vault_id, room, boosted_stat, is_boosted)
                    )

            # Training dwellers (boosted only)
            if is_boosted:
                for i, training_stat in enumerate(BOOSTED_TRAINING_STATS):
                    if i < len(created_training_rooms):
                        room = created_training_rooms[i]
                        dweller_data = DwellerCreateCommonOverride(special_boost=training_stat)
                        dweller_obj = await dweller_service.create_random_dweller(
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
                    workers.append(
                        await self._seed_working_dweller(
                            db_session, vault_id, radio_room, SPECIALEnum.CHARISMA, is_boosted
                        )
                    )

            living: list[Dweller] = []
            living_rooms = [r for r in created_capacity_rooms if "living" in r.name.lower()]
            if living_rooms:
                living_room = living_rooms[0]
                for gender in (GenderEnum.MALE, GenderEnum.FEMALE):
                    dweller_data = DwellerCreateCommonOverride(
                        gender=gender,
                        special_boost=SPECIALEnum.CHARISMA if is_boosted else None,
                    )
                    dweller = await dweller_service.create_random_dweller(
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
                    dweller.room_id = living_room.id
                    living.append(dweller)
                    self.logger.info("Dweller %s assigned to living quarters for socializing", dweller.id)

            await self._seed_seeded_families(db_session, vault_id, apprentice_rooms, workers, living, is_boosted)

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

    async def _pair_seeded_couple(self, db_session: AsyncSession, first: Dweller, second: Dweller) -> None:
        """Link a seeded couple both ways with a committed relationship row and spouse lore."""
        from app.services.bio_service import bio_service

        first.partner_id, second.partner_id = second.id, first.id
        db_session.add_all([first, second])
        await relationship_crud.create_with_defaults(
            db_session, first.id, second.id, relationship_type=SEEDED_COUPLE_STAGE, affinity=SEEDED_COUPLE_AFFINITY
        )
        bonus = game_config.relationship.partner_happiness_bonus + game_config.relationship.married_happiness_bonus
        for dweller in (first, second):
            await dweller_crud.update(
                db_session, dweller.id, {"happiness": max(0, min(100, dweller.happiness + bonus))}
            )
        first_name = f"{first.first_name} {first.last_name or ''}".strip()
        second_name = f"{second.first_name} {second.last_name or ''}".strip()
        await bio_service.append_entry(
            db_session, first.id, "family", f"Married {second_name}.", ref={"partner_id": str(second.id)}
        )
        await bio_service.append_entry(
            db_session, second.id, "family", f"Married {first_name}.", ref={"partner_id": str(first.id)}
        )

    async def _seed_family_child(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        mother: Dweller,
        father: Dweller,
        room: Room | None,
        is_boosted: bool,
    ) -> Dweller:
        """Create a child linked to both parents; teens apprentice at the working parent's production room."""
        from app.options.bios import render_newborn_bio
        from app.services.bio_service import bio_service, make_entry
        from app.services.dweller_service import dweller_service

        child = await dweller_service.create_random_dweller(
            db_session,
            vault_id,
            DwellerCreateCommonOverride(special_boost=room.ability if room else None),
            rarity=self._roll_initial_rarity(is_boosted),
        )
        surname = father.last_name or child.last_name
        child_name = f"{child.first_name} {surname or ''}".strip()
        mother_name = f"{mother.first_name} {mother.last_name or ''}".strip()
        father_name = f"{father.first_name} {father.last_name or ''}".strip()
        newborn = render_newborn_bio(mother_name, father_name, str(mother.id), str(father.id), str(vault_id))
        await dweller_crud.update(
            db_session,
            child.id,
            {
                "parent_1_id": mother.id,
                "parent_2_id": father.id,
                "last_name": surname,
                "is_adult": False,
                "age_group": AgeGroupEnum.TEEN if room else AgeGroupEnum.CHILD,
                "birth_date": datetime.utcnow()
                - timedelta(hours=YOUTH_APPRENTICE_BIRTH_AGE_HOURS if room else SEEDED_CHILD_AGE_HOURS),
                "bio": newborn,
                "bio_entries": [
                    make_entry(
                        "template",
                        newborn,
                        {"mother_id": str(mother.id), "father_id": str(father.id)},
                    )
                ],
            },
        )
        if room:
            await self._seed_youth_apprentice(db_session, child.id, room)
        for parent, partner, partner_name in (
            (mother, father, father_name),
            (father, mother, mother_name),
        ):
            await bio_service.append_entry(
                db_session,
                parent.id,
                "family",
                f"Became a parent: {child_name} was born.",
                ref={"child_id": str(child.id), "partner_id": str(partner.id), "partner_name": partner_name},
            )
        return child

    async def _seed_seeded_families(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        apprentice_rooms: list[Room],
        workers: list[Dweller],
        living: list[Dweller],
        is_boosted: bool,
    ) -> None:
        """Pair seeded adults into households; teens apprentice only in rooms with a reserved slot."""
        pool = [d for d in (*workers, *living) if d is not None]
        if len(pool) < 2:
            return
        rooms = [r for r in apprentice_rooms if r.ability is not None]
        rooms_by_id = {r.id: r for r in rooms}
        used_rooms: set[UUID4] = set()
        families = SEEDED_FAMILIES_BOOSTED if is_boosted else SEEDED_FAMILIES_STANDARD
        for _ in range(min(families, len(pool) // 2)):
            first = pool.pop(0)
            second = pool.pop(next((j for j, d in enumerate(pool) if d.gender != first.gender), 0))
            await self._pair_seeded_couple(db_session, first, second)
            mother = first if first.gender == GenderEnum.FEMALE else second
            father = second if mother is first else first
            room = rooms_by_id.get(first.room_id) or rooms_by_id.get(second.room_id)
            if room is not None and room.id in used_rooms:
                room = next((r for r in rooms if r.id not in used_rooms), None)
            if room is not None:
                used_rooms.add(room.id)
            await self._seed_family_child(db_session, vault_id, mother, father, room, is_boosted)

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

    async def _seed_boosted_junk(self, db_session: AsyncSession, storage_id: UUID4) -> None:
        """Drop craftable materials into a vault so item creation is testable."""
        from app.models.junk import Junk
        from app.services.exploration.data_loader import load_junk_items

        catalog = {
            (str(entry["junk_type"]).lower(), str(entry["rarity"]).lower()): entry for entry in load_junk_items()
        }
        seeded = 0
        for junk_type, rarity, count in BOOSTED_SEED_JUNK:
            entry = catalog.get((junk_type.value, rarity.value))
            if entry is None:
                continue
            for _ in range(count):
                db_session.add(
                    Junk(
                        name=str(entry["name"]),
                        junk_type=junk_type,
                        rarity=rarity,
                        value=entry.get("value"),
                        description=str(entry.get("description") or entry["name"]),
                        storage_id=storage_id,
                    )
                )
                seeded += 1
        if seeded:
            await db_session.commit()
            self.logger.info(f"Seeded {seeded} crafting materials into storage {storage_id}")

    def _build_boosted_outfits(self, storage_id: UUID4) -> list[Outfit]:
        """Spare hazard-team suits from the outfit catalog, so resists stay correct."""
        from app.services.exploration.data_loader import load_outfits

        catalog = {str(entry["name"]).strip().lower(): entry for entry in load_outfits()}
        outfits: list[Outfit] = []
        for name, count in BOOSTED_SEED_OUTFITS:
            entry = catalog.get(name.strip().lower())
            if entry is None:
                self.logger.warning("Boosted outfit %r missing from catalog, skipping", name)
                continue
            outfits.extend(build_outfit(entry, entry["rarity"], storage_id) for _ in range(count))
        return outfits

    async def _create_initial_items(self, db_session: AsyncSession, vault_id: UUID4, is_boosted: bool = False) -> None:
        """Create initial weapons and outfits for testing, plus crafting junk when boosted."""
        storage = await storage_crud.get_by_vault(db_session, vault_id)
        if not storage:
            return

        weapons = [build_weapon(data, data["rarity"], storage.id) for data in SEED_WEAPONS]
        outfits = [build_outfit(data, data["rarity"], storage.id) for data in SEED_OUTFITS]
        if is_boosted:
            outfits.extend(self._build_boosted_outfits(storage.id))
        await weapon_crud.create_many(db_session, weapons)
        await outfit_crud.create_many(db_session, outfits)
        if is_boosted:
            await self._seed_boosted_junk(db_session, storage.id)
        self.logger.info(f"Created initial items for vault {vault_id}")

    async def _create_boosted_legendary_dwellers(self, db_session: AsyncSession, vault_id: UUID4) -> None:
        """Add a small, equipped legendary roster for boosted-vault testing via shared flow."""
        from app.core.enums import RarityEnum, WeaponTypeEnum
        from app.models.weapon import Weapon
        from app.services.dweller_service import dweller_service
        from app.services.exploration.data_loader import load_outfits
        from app.utils.weapon_assets import get_weapon_image_url

        catalog = {str(entry["name"]).strip().lower(): entry for entry in load_outfits()}
        legendary_weapons = []
        legendary_outfits = []
        for template_id, weapon_name, outfit_name, weapon_subtype in BOOSTED_LOADOUTS:
            try:
                dweller = await dweller_service.create_dweller_from_template(db_session, vault_id, template_id)
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
            entry = catalog.get(outfit_name.strip().lower())
            if entry is None:
                self.logger.warning("Boosted outfit %r missing from catalog, skipping", outfit_name)
                continue
            outfit = build_outfit(entry, entry["rarity"], storage_id=None)
            outfit.dweller_id = dweller.id
            legendary_outfits.append(outfit)

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
        - A merged living room plus the base room (capacity for more than 32 dwellers)
        - Both crafting workshops staffed with two dwellers each
        - Three storage rooms and a stock of steel/leather/circuitry/cloth junk
          so timed crafting is testable, with 34 dwellers seeded.
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
            created_crafting_rooms=created.crafting,
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

        # Create initial weapons, outfits, and (boosted) crafting materials for testing
        await self._create_initial_items(db_session, vault_db_obj.id, is_boosted)

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
    ) -> MedicalTransferResponse:
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

    @staticmethod
    def _calculate_new_capacity(
        action: RoomActionEnum,
        current_capacity: int | None,
        room_capacity: int | None,
        previous_capacity: int | None = None,
    ) -> int:
        base = current_capacity or 0
        if room_capacity is None:
            return base

        # A replacement (upgrade, or a merge absorbing an already-counted room)
        # swaps the room's own contribution, so only the change counts.
        if previous_capacity is not None:
            return base - previous_capacity + room_capacity
        if action in {RoomActionEnum.BUILD, RoomActionEnum.UPGRADE}:
            return base + room_capacity
        if action == RoomActionEnum.DESTROY:
            return base - room_capacity
        msg = f"Invalid room action: {action}"
        raise ValueError(msg)

    async def recalculate_vault_attributes(
        self,
        *,
        db_session: AsyncSession,
        vault_obj: Vault,
        room_obj: Room,
        action: RoomActionEnum,
        previous_capacity: int | None = None,
    ) -> Vault:
        """Recalculate the vault attributes based on the newly added or removed room."""
        if room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.capacity is not None:
            await self._handle_production_room(db_session, vault_obj, room_obj, action, previous_capacity)
        elif room_obj.category == RoomTypeEnum.CAPACITY:
            await self._handle_capacity_room(db_session, vault_obj, room_obj, action, previous_capacity)

        return vault_obj

    async def _handle_production_room(
        self,
        db_session: AsyncSession,
        vault_obj: Vault,
        room_obj: Room,
        action: RoomActionEnum,
        previous_capacity: int | None = None,
    ) -> None:
        """Handle production room capacity updates."""
        if room_obj.ability not in (
            SPECIALEnum.STRENGTH,
            SPECIALEnum.AGILITY,
            SPECIALEnum.PERCEPTION,
            SPECIALEnum.INTELLIGENCE,
        ):
            msg = f"Invalid room ability: {room_obj.ability}"
            raise ValueError(msg)

        resource_map = {
            SPECIALEnum.STRENGTH: ("power_max", vault_obj.power_max),
            SPECIALEnum.AGILITY: ("food_max", vault_obj.food_max),
            SPECIALEnum.PERCEPTION: ("water_max", vault_obj.water_max),
            SPECIALEnum.INTELLIGENCE: (None, None),
        }

        field, current = resource_map[room_obj.ability]

        if field:
            new_capacity = self._calculate_new_capacity(action, current, room_obj.capacity, previous_capacity)
            await vault_crud.update(db_session=db_session, id=vault_obj.id, obj_in={field: new_capacity}, commit=False)
            await db_session.commit()

    async def _handle_capacity_room(
        self,
        db_session: AsyncSession,
        vault_obj: Vault,
        room_obj: Room,
        action: RoomActionEnum,
        previous_capacity: int | None = None,
    ) -> None:
        """Handle capacity room updates."""
        if room_obj.ability == SPECIALEnum.CHARISMA:
            new_population_max = self._calculate_new_capacity(
                action, vault_obj.population_max or 0, room_obj.capacity, previous_capacity
            )
            await vault_crud.update(db_session, vault_obj.id, VaultUpdate(population_max=new_population_max))
        elif room_obj.ability == SPECIALEnum.ENDURANCE and room_obj.capacity is not None:
            storage_obj = await storage_crud.get_by_vault(db_session, vault_obj.id)

            if storage_obj is None:
                storage_obj = await storage_crud.create_for_vault(db_session=db_session, vault_id=vault_obj.id)

            current_max_space = storage_obj.max_space
            new_storage_space_max = self._calculate_new_capacity(
                action, current_max_space, room_obj.capacity, previous_capacity
            )
            await storage_crud.set_max_space(db_session, vault_obj.id, new_storage_space_max)

    async def is_enough_dwellers(
        self, *, db_session: AsyncSession, vault_id: UUID4, population_required: int | None
    ) -> bool:
        """Check if the vault has enough dwellers to perform an operation."""
        if population_required is None:
            return True
        dwellers_count = await vault_crud.get_population(db_session=db_session, vault_id=vault_id)
        return dwellers_count >= population_required

    @staticmethod
    async def is_enough_population_space(*, db_session: AsyncSession, vault_id: UUID4, space_required: int) -> bool:
        """Check if the vault has enough space to perform an operation.

        Only counts dwellers that are assigned to rooms (have room_id).
        Unassigned dwellers don't take up living space.
        """
        population_max, current_assigned_population = await vault_crud.get_population_space(
            db_session=db_session, vault_id=vault_id
        )
        if population_max is None:
            if current_assigned_population == 0:
                raise ResourceNotFoundException(Vault, identifier=vault_id)
            return False
        return current_assigned_population + space_required <= population_max

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
        capped = min(vault_obj.bottle_caps + amount, 999_999)
        credited = capped - vault_obj.bottle_caps
        await vault_crud.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=capped), commit=commit)

        if track_earnings:
            from app.services.user_service import user_service

            await user_service.record_vault_statistic(
                db_session,
                vault_obj.id,
                "total_caps_earned",
                credited,
                commit=commit,
            )

        if emit_event:
            from app.core.event_bus import GameEvent, event_bus

            await event_bus.emit(
                GameEvent.RESOURCE_COLLECTED, vault_obj.id, {"resource_type": "caps", "amount": credited}
            )

        return credited

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int, commit: bool = True):
        """Withdraw the specified amount from the vault's bottle caps as part of a spending operation.

        Pass ``commit=False`` to compose the deduction with other writes into one transaction.
        """
        if vault_obj.bottle_caps < amount:
            amount_needed = amount - vault_obj.bottle_caps
            raise InsufficientResourcesException(resource_name="bottle caps", resource_amount=amount_needed)
        await vault_crud.update(
            db_session,
            id=vault_obj.id,
            obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps - amount),
            commit=commit,
        )

    @staticmethod
    def _vault_with_numbers(
        vault_obj: Vault, room_count: int, dweller_count: int, stimpack: int, radaway: int
    ) -> VaultReadWithNumbers:
        return VaultReadWithNumbers(
            **vault_obj.model_dump(),
            room_count=room_count,
            dweller_count=dweller_count,
            stimpack=stimpack,
            radaway=radaway,
            resource_warnings=get_resource_warnings(
                vault_obj,
                {
                    "power": float(vault_obj.power),
                    "food": float(vault_obj.food),
                    "water": float(vault_obj.water),
                },
            ),
        )

    async def get_vaults_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, user_id: UUID4
    ) -> list[VaultReadWithNumbers]:
        """List the user's non-deleted vaults with room/dweller counts and resource warnings."""
        return list(
            starmap(
                self._vault_with_numbers, await vault_crud.get_vault_count_rows(db_session=db_session, user_id=user_id)
            )
        )

    async def get_vault_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, vault_id: UUID4
    ) -> VaultReadWithNumbers:
        """Fetch a single vault with room/dweller counts and resource warnings."""
        vault_obj, room_count, dweller_count, stimpack, radaway = await vault_crud.get_vault_count_row(
            db_session=db_session, vault_id=vault_id
        )
        return self._vault_with_numbers(vault_obj, room_count, dweller_count, stimpack, radaway)


# Singleton instance
vault_service = VaultService()
