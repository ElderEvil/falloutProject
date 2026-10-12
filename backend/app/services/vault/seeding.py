"""Vault seeding: initialize a fresh vault with rooms, dwellers, items, and families.

Orchestrated by ``VaultService.initiate_vault`` (the sole transaction owner for
vault creation) in ``app.services.vault_service``; no function here commits on
its own except the multi-stage create initial rooms/junk boundaries that are
part of that operation.
"""

import logging
import random
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import (
    AgeGroupEnum,
    DwellerStatusEnum,
    GenderEnum,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.game_config import game_config
from app.core.game_data import get_static_game_data
from app.core.grid_config import SHAFT_X
from app.crud import dweller as dweller_crud
from app.crud import outfit as outfit_crud
from app.crud import pet as pet_crud
from app.crud import room as room_crud
from app.crud import weapon as weapon_crud
from app.crud.relationship import relationship_crud
from app.crud.storage import storage as storage_crud
from app.models import Dweller, Room
from app.models.outfit import Outfit
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.dweller import DwellerCreateCommonOverride, DwellerUpdate
from app.schemas.room import RoomCreate, RoomCreateWithoutVaultID
from app.services.family.breeding_service import conception_potential
from app.services.training_service import training_service
from app.services.vault_seed import (
    BOOSTED_CRAFTING_ROOM_SPECS,
    BOOSTED_LEGENDARY_DWELLER_COUNT,
    BOOSTED_MERGED_LIVING_ROOM,
    BOOSTED_SEED_JUNK,
    BOOSTED_SEED_OUTFITS,
    BOOSTED_SEED_PETS,
    BOOSTED_TRAINING_STATS,
    BOOSTED_WORKER_OUTFITS,
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
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException
from app.utils.item_factory import build_catalog_item, build_junk, build_outfit, build_pet, build_weapon
from app.utils.junk_assets import get_junk_image_url
from app.utils.room_assets import get_room_image_url

logger = logging.getLogger(__name__)


def build_room(
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


def prepare_initial_rooms(
    rooms: list[RoomCreateWithoutVaultID],
    vault_id: UUID4,
    is_boosted: bool,
) -> PreparedRooms:
    rooms_by_name = {r.name.lower(): r for r in rooms}

    def mk(specs: list[tuple[str, int, int]]) -> list[RoomCreate]:
        return [build_room(rooms_by_name, n, vault_id, x, y) for n, x, y in specs]

    def mk_sized(specs: list[tuple[str, int, int, int]]) -> list[RoomCreate]:
        return [build_room(rooms_by_name, n, vault_id, x, y, size=s) for n, x, y, s in specs]

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
    if is_boosted:
        # The boosted room set draws ~51.5 power/min, so boosted seeds the
        # generator at its final size-6 footprint at (0, 1) — same footprint,
        # capacity (300), output (58) and art as a fused pair, without the
        # seed-time merge round-trip.
        production = mk_sized([("power generator", 0, 1, 6), ("diner", 3, 2, 3), ("water treatment", 3, 3, 3)])
        production += mk([("science lab", 19, 2), ("medbay", 16, 2)])
    else:
        production = mk([("power generator", 3, 1), ("diner", 3, 2), ("water treatment", 3, 3)])
    for room in production:
        if room.name.lower().startswith("power") and (room.size or 0) > 3:
            room.image_url = get_room_image_url(room.name, tier=room.tier or 1, size=room.size or 3)
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


async def create_initial_rooms(
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

    await merge_adjacent_seed_rooms(db_session, vault.id)

    return vault, CreatedRooms(
        production=created_production,
        training=created_training,
        misc=created_misc,
        capacity=created_capacity,
        arena=created_arena,
        crafting=created_crafting,
    )


async def merge_adjacent_seed_rooms(db_session: AsyncSession, vault_id: UUID4) -> None:
    """Fuse adjacent same-name seed rooms (the boosted storage row and generator pair) via the merge flow."""
    from app.services.room_service import room_service

    await room_service.backfill_merge_rooms_for_vault(db_session, vault_id, dry_run=False)


def roll_initial_rarity(is_boosted: bool) -> RarityEnum:
    """Roll RARE for initial seeded dwellers; boosted vaults use the higher chance."""
    vault_start = game_config.vault_start
    chance = vault_start.boosted_rare_chance if is_boosted else vault_start.standard_rare_chance
    return RarityEnum.RARE if random.random() < chance else RarityEnum.COMMON


async def seed_working_dweller(
    db_session: AsyncSession, vault_id: UUID4, room: Room, boosted_stat: SPECIALEnum, is_boosted: bool
) -> Dweller:
    """Create a dweller and assign it to a room as a worker."""
    from app.services.dweller_service import dweller_service

    dweller_obj = await dweller_service.create_random_dweller(
        db_session,
        vault_id,
        DwellerCreateCommonOverride(special_boost=boosted_stat),
        rarity=roll_initial_rarity(is_boosted),
    )
    await dweller_crud.update(
        db_session=db_session,
        id=dweller_obj.id,
        obj_in=DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.WORKING),
    )
    dweller_obj.room_id = room.id
    logger.info("Dweller %s assigned to %s", dweller_obj.id, room.name)
    return dweller_obj


async def equip_boosted_worker_outfit(db_session: AsyncSession, worker: Dweller, stat: SPECIALEnum) -> None:
    """Craft and equip the Common +3 outfit matching a boosted production worker's room stat."""
    from app.services.exploration.data_loader import load_outfits

    name = BOOSTED_WORKER_OUTFITS.get(stat)
    if name is None:
        return
    entry = next((e for e in load_outfits() if str(e["name"]).strip().lower() == name.lower()), None)
    if entry is None:
        logger.warning("Boosted worker outfit %r missing from catalog, skipping", name)
        return
    item = await outfit_crud.create(db_session, build_outfit(entry, entry["rarity"]))
    await outfit_crud.equip(db_session=db_session, item_id=item.id, dweller_id=worker.id, commit=False)


async def create_initial_dwellers(
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
        # Crew is ``production_crew`` per base segment, keyed to each room's own
        # SPECIAL. The size-6 generator holds a double crew; the first two
        # production rooms keep one adult slot free for their family teen.
        production_crew = 3 if is_boosted else 2
        apprentice_rooms = [r for r in created_production_rooms[:2] if r.ability is not None]
        apprentice_ids = {r.id for r in apprentice_rooms} if is_boosted else frozenset()
        workers: list[Dweller] = []
        for room in created_production_rooms:
            if room.ability is None:
                continue
            count = production_crew * room.segment_count - (1 if room.id in apprentice_ids else 0)
            for _ in range(count):
                worker = await seed_working_dweller(db_session, vault_id, room, room.ability, is_boosted)
                if is_boosted:
                    await equip_boosted_worker_outfit(db_session, worker, room.ability)
                workers.append(worker)

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
                workers.append(await seed_working_dweller(db_session, vault_id, room, boosted_stat, is_boosted))

        # Training dwellers (boosted only)
        if is_boosted:
            for i, training_stat in enumerate(BOOSTED_TRAINING_STATS):
                if i < len(created_training_rooms):
                    room = created_training_rooms[i]
                    dweller_data = DwellerCreateCommonOverride(special_boost=training_stat)
                    dweller_obj = await dweller_service.create_random_dweller(
                        db_session, vault_id, dweller_data, rarity=roll_initial_rarity(is_boosted)
                    )

                    # Assign to training room with IDLE status (training service will update status)

                    await dweller_crud.update(
                        db_session=db_session,
                        id=dweller_obj.id,
                        obj_in=DwellerUpdate(room_id=room.id, status=DwellerStatusEnum.IDLE),
                    )
                    logger.info(f"Dweller {dweller_obj.id} assigned to training room {room.id}")

        # Radio studio dweller (Charisma-based, for recruitment)
        if created_misc_rooms:
            radio_room = next((r for r in created_misc_rooms if "radio" in r.name.lower()), None)
            if radio_room:
                workers.append(
                    await seed_working_dweller(db_session, vault_id, radio_room, SPECIALEnum.CHARISMA, is_boosted)
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
                    db_session, vault_id, dweller_data, rarity=roll_initial_rarity(is_boosted)
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
                logger.info("Dweller %s assigned to living quarters for socializing", dweller.id)

        await seed_seeded_families(db_session, vault_id, apprentice_rooms, workers, living, is_boosted)

    except Exception:
        logger.exception("Failed to create dwellers")
        raise


async def seed_youth_apprentice(db_session: AsyncSession, youth_id: UUID4, room: Room) -> None:
    """Mark a seeded teen as an apprentice of a production room."""
    await dweller_crud.update(
        db_session,
        youth_id,
        {
            "age_group": AgeGroupEnum.TEEN,
            "birth_date": datetime.utcnow() - timedelta(hours=YOUTH_APPRENTICE_BIRTH_AGE_HOURS),
            "room_id": room.id,
            "status": DwellerStatusEnum.WORKING,
            "apprentice_stat": room.ability,
            "apprentice_started_at": datetime.utcnow(),
        },
    )


async def pair_seeded_couple(db_session: AsyncSession, first: Dweller, second: Dweller) -> None:
    """Link a seeded couple both ways with a committed relationship row and spouse lore."""
    from app.services.bio_service import bio_service

    first.partner_id, second.partner_id = second.id, first.id
    db_session.add_all([first, second])
    await relationship_crud.create_with_defaults(
        db_session, first.id, second.id, relationship_type=SEEDED_COUPLE_STAGE, affinity=SEEDED_COUPLE_AFFINITY
    )
    bonus = game_config.relationship.partner_happiness_bonus + game_config.relationship.married_happiness_bonus
    for dweller in (first, second):
        await dweller_crud.update(db_session, dweller.id, {"happiness": max(0, min(100, dweller.happiness + bonus))})
    first_name = f"{first.first_name} {first.last_name or ''}".strip()
    second_name = f"{second.first_name} {second.last_name or ''}".strip()
    await bio_service.append_entry(
        db_session, first.id, "family", f"Married {second_name}.", ref={"partner_id": str(second.id)}
    )
    await bio_service.append_entry(
        db_session, second.id, "family", f"Married {first_name}.", ref={"partner_id": str(first.id)}
    )


async def seed_family_child(
    db_session: AsyncSession,
    vault_id: UUID4,
    mother: Dweller,
    father: Dweller,
    room: Room | None,
    is_boosted: bool,
) -> Dweller:
    """Create a child linked to both parents; teens apprentice at the working parent's production room."""
    from app.options.bios import render_adopted_child_bio, render_newborn_bio
    from app.services.bio_service import bio_service, make_entry
    from app.services.dweller_service import dweller_service

    child = await dweller_service.create_random_dweller(
        db_session,
        vault_id,
        DwellerCreateCommonOverride(special_boost=room.ability if room else None),
        rarity=roll_initial_rarity(is_boosted),
    )
    surname = father.last_name or child.last_name
    child_name = f"{child.first_name} {surname or ''}".strip()
    mother_name = f"{mother.first_name} {mother.last_name or ''}".strip()
    father_name = f"{father.first_name} {father.last_name or ''}".strip()
    biological = conception_potential(mother, father) == "possible"
    origin = (
        render_newborn_bio(mother_name, father_name, str(mother.id), str(father.id), str(vault_id))
        if biological
        else render_adopted_child_bio(mother_name, father_name, str(mother.id), str(father.id), str(vault_id))
    )
    origin_ref = (
        {"mother_id": str(mother.id), "father_id": str(father.id)}
        if biological
        else {"parent_1_id": str(mother.id), "parent_2_id": str(father.id), "adopted": True}
    )
    await dweller_crud.update(
        db_session,
        child.id,
        {
            "parent_1_id": mother.id,
            "parent_2_id": father.id,
            "last_name": surname,
            "age_group": AgeGroupEnum.TEEN if room else AgeGroupEnum.CHILD,
            "birth_date": datetime.utcnow()
            - timedelta(hours=YOUTH_APPRENTICE_BIRTH_AGE_HOURS if room else SEEDED_CHILD_AGE_HOURS),
            "bio": origin,
            "bio_entries": [
                make_entry(
                    "template",
                    origin,
                    origin_ref,
                )
            ],
        },
    )
    if room:
        await seed_youth_apprentice(db_session, child.id, room)
    for parent, partner, partner_name in (
        (mother, father, father_name),
        (father, mother, mother_name),
    ):
        await bio_service.append_entry(
            db_session,
            parent.id,
            "family",
            f"Became a parent: {child_name} was born." if biological else f"Adopted {child_name}.",
            ref={
                "child_id": str(child.id),
                "partner_id": str(partner.id),
                "partner_name": partner_name,
                **({"adopted": True} if not biological else {}),
            },
        )
    return child


async def seed_seeded_families(
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
        await pair_seeded_couple(db_session, first, second)
        mother = first if first.gender == GenderEnum.FEMALE else second
        father = second if mother is first else first
        room = rooms_by_id.get(first.room_id) or rooms_by_id.get(second.room_id)
        if room is not None and room.id in used_rooms:
            room = next((r for r in rooms if r.id not in used_rooms), None)
        if room is not None:
            used_rooms.add(room.id)
        await seed_family_child(db_session, vault_id, mother, father, room, is_boosted)


async def start_dweller_training(db_session: AsyncSession, dweller: Dweller, room: Room) -> None:
    """Start one training session; domain failures are logged, not raised."""
    try:
        await db_session.refresh(dweller)
        await training_service.start_training(db_session, dweller.id, room.id)
        logger.info(f"Started training for dweller {dweller.id} in room {room.id}")
    except (ResourceNotFoundException, ResourceConflictException, ValueError) as e:
        logger.warning(f"Failed to start training for dweller {dweller.id} in room {room.id}: {e}")


async def start_training_sessions(
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
            logger.info(f"Room {room.id} ({room.name}) - tier: {room.tier}, ability: {room.ability}")

            dwellers = dwellers_by_room.get(room.id, [])

            for dweller in dwellers:
                await start_dweller_training(db_session, dweller, room)
    except Exception:
        logger.exception("Failed to start training sessions")
        raise


async def seed_boosted_junk(db_session: AsyncSession, storage_id: UUID4) -> None:
    """Drop craftable materials into a vault so item creation is testable."""
    from app.services.exploration.data_loader import load_junk_items

    catalog = {(str(entry["junk_type"]).lower(), str(entry["rarity"]).lower()): entry for entry in load_junk_items()}
    seeded = 0
    for junk_type, rarity, count in BOOSTED_SEED_JUNK:
        entry = catalog.get((junk_type.value, rarity.value))
        if entry is None:
            continue
        for _ in range(count):
            db_session.add(
                build_junk(
                    str(entry["name"]),
                    rarity,
                    storage_id,
                    value=entry.get("value"),
                    description=str(entry.get("description") or entry["name"]),
                    junk_type=junk_type,
                    image_url=entry.get("image_url") or get_junk_image_url(str(entry["name"])),
                )
            )
            seeded += 1
    if seeded:
        await db_session.commit()
        logger.info(f"Seeded {seeded} crafting materials into storage {storage_id}")


async def seed_boosted_pets(db_session: AsyncSession, storage_id: UUID4) -> None:
    """Seed unassigned pets into a boosted vault's storage so equip and bonuses are testable immediately."""
    pets = [build_pet({"name": name}, rarity, storage_id) for name, rarity in BOOSTED_SEED_PETS]
    await pet_crud.create_many(db_session, pets)
    logger.info(f"Seeded {len(pets)} pets into storage {storage_id}")


def build_boosted_outfits(storage_id: UUID4) -> list[Outfit]:
    """Spare hazard-team suits from the outfit catalog, so resists stay correct."""
    from app.services.exploration.data_loader import load_outfits

    catalog = {str(entry["name"]).strip().lower(): entry for entry in load_outfits()}
    outfits: list[Outfit] = []
    for name, count in BOOSTED_SEED_OUTFITS:
        entry = catalog.get(name.strip().lower())
        if entry is None:
            logger.warning("Boosted outfit %r missing from catalog, skipping", name)
            continue
        outfits.extend(build_outfit(entry, entry["rarity"], storage_id) for _ in range(count))
    return outfits


async def create_initial_items(db_session: AsyncSession, vault_id: UUID4, is_boosted: bool = False) -> None:
    """Create initial weapons and outfits for testing, plus crafting junk when boosted."""
    storage = await storage_crud.get_by_vault(db_session, vault_id)
    if not storage:
        return

    weapons = [build_weapon(data, data["rarity"], storage.id) for data in SEED_WEAPONS]
    outfits = [build_outfit(data, data["rarity"], storage.id) for data in SEED_OUTFITS]
    if is_boosted:
        outfits.extend(build_boosted_outfits(storage.id))
    await weapon_crud.create_many(db_session, weapons)
    await outfit_crud.create_many(db_session, outfits)
    if is_boosted:
        await seed_boosted_junk(db_session, storage.id)
        await seed_boosted_pets(db_session, storage.id)
    logger.info(f"Created initial items for vault {vault_id}")


async def create_boosted_legendary_dwellers(db_session: AsyncSession, vault_id: UUID4) -> None:
    """Add a random, equipped legendary roster to boosted vaults."""
    from app.services.dweller_service import dweller_service
    from app.services.exploration.data_loader import load_outfits, load_weapons

    game_data = await get_static_game_data()
    weapons_data = load_weapons()
    outfits_data = load_outfits()
    weapon_names = {str(entry["name"]) for entry in weapons_data}
    outfit_names = {str(entry["name"]) for entry in outfits_data}
    candidates = [
        template
        for template in game_data.get_dwellers_by_rarity(RarityEnum.LEGENDARY.value)
        if template.weapon and template.outfit and template.weapon in weapon_names and template.outfit in outfit_names
    ]
    selected = random.sample(candidates, k=min(BOOSTED_LEGENDARY_DWELLER_COUNT, len(candidates)))
    legendary_weapons: list[Weapon] = []
    legendary_outfits: list[Outfit] = []
    for template in selected:
        if not template.weapon or not template.outfit:
            continue
        try:
            dweller = await dweller_service.create_dweller_from_template(db_session, vault_id, template.template_id)
        except ResourceConflictException:
            logger.info("Boosted template %s already active in vault %s, skipping", template.template_id, vault_id)
            continue

        for item_type, name in (("weapon", template.weapon), ("outfit", template.outfit)):
            item = build_catalog_item(
                item_type,
                name,
                RarityEnum.LEGENDARY,
                weapons_data=weapons_data,
                outfits_data=outfits_data,
            )
            if item is None:
                logger.warning("Boosted %s %r missing from catalog, skipping", item_type, name)
                continue
            item.dweller_id = dweller.id
            if isinstance(item, Weapon):
                legendary_weapons.append(item)
            else:
                legendary_outfits.append(item)

    if legendary_weapons:
        await weapon_crud.create_many(db_session, legendary_weapons)
    if legendary_outfits:
        await outfit_crud.create_many(db_session, legendary_outfits)
