import random
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, RowMapping, func
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.base import CRUDBase
from app.crud.room import room as room_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum, RarityEnum, RoomTypeEnum
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerReadFull,
    DwellerReadWithRoomID,
    DwellerUpdate,
)
from app.services.event_bus import GameEvent, event_bus
from app.services.room_assignment_policy import validate_automatic_assignment, validate_room_assignment
from app.utils.dwellers import create_random_common_dweller
from app.utils.exceptions import (
    ContentNoChangeException,
    InvalidVaultTransferException,
    ResourceConflictException,
)
from app.utils.reward_delivery import persist_reward_change, reward_delivery_is_deferred


def determine_status_for_room(room_category: RoomTypeEnum | None, room_name: str | None = None) -> DwellerStatusEnum:
    """
    Determine the appropriate dweller status based on room category.

    :param room_category: The category of the room, or None if unassigning
    :returns: The appropriate DwellerStatusEnum
    """
    if room_category is None:
        return DwellerStatusEnum.IDLE
    if room_category == RoomTypeEnum.TRAINING:
        return DwellerStatusEnum.TRAINING
    if room_category == RoomTypeEnum.ARENA:
        return DwellerStatusEnum.FIGHTING
    if room_category == RoomTypeEnum.CAPACITY and "living" in (room_name or "").lower():
        return DwellerStatusEnum.RESTING
    # Default to WORKING for PRODUCTION, CAPACITY, CRAFTING, MISC, QUESTS, THEME
    return DwellerStatusEnum.WORKING


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    async def get(self, db_session: AsyncSession, id: UUID4, include_deleted: bool = False) -> Dweller:
        """Override to eager load weapon and outfit relationships."""
        from app.utils.exceptions import ResourceNotFoundException

        query = (
            select(self.model)
            .where(self.model.id == id)
            .options(
                selectinload(Dweller.vault),
                selectinload(Dweller.room),
                selectinload(Dweller.weapon),
                selectinload(Dweller.outfit),
            )
        )

        # Filter out soft-deleted dwellers by default
        if not include_deleted:
            query = query.where(~self.model.is_deleted)

        response = await db_session.execute(query)
        db_obj = response.scalar_one_or_none()
        if db_obj is None:
            raise ResourceNotFoundException(self.model, identifier=id)
        return db_obj

    async def get_multi(
        self, db_session: AsyncSession, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> Sequence[Dweller]:
        """Override to eager load weapon (needed for weapon_type on DwellerReadLess)."""
        query = (
            select(self.model).offset(skip).limit(limit).order_by(self.model.id).options(selectinload(Dweller.weapon))
        )
        if not include_deleted:
            query = query.where(~self.model.is_deleted)
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_multi_by_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
        status: DwellerStatusEnum | None = None,
        age_group: AgeGroupEnum | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        include_deleted: bool = False,
    ) -> Sequence[Row[Any] | RowMapping | Any]:
        """Get multiple dwellers by vault ID with optional filtering and sorting."""
        query = select(self.model).where(self.model.vault_id == vault_id)

        # Filter out soft-deleted dwellers by default
        if not include_deleted:
            query = query.where(~self.model.is_deleted)

        # Filter by status
        if status:
            query = query.where(self.model.status == status)

        # Filter by age group
        if age_group:
            query = query.where(self.model.age_group == age_group)

        # Search by name
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (self.model.first_name.ilike(search_pattern)) | (self.model.last_name.ilike(search_pattern))
            )

        # Sorting
        if sort_by == "name":
            # Special handling for name sorting - sort by first_name, then last_name
            if order.lower() == "asc":
                query = query.order_by(self.model.first_name.asc(), self.model.last_name.asc())
            else:
                query = query.order_by(self.model.first_name.desc(), self.model.last_name.desc())
        elif hasattr(self.model, sort_by):
            sort_column = getattr(self.model, sort_by)
            if order.lower() == "asc":
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())

        query = query.offset(skip).limit(limit).options(selectinload(Dweller.weapon))
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_by_status(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        status: DwellerStatusEnum,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> Sequence[Dweller]:
        """Get dwellers by status."""
        query = select(self.model).where(self.model.vault_id == vault_id).where(self.model.status == status)

        # Filter out soft-deleted dwellers by default
        if not include_deleted:
            query = query.where(~self.model.is_deleted)

        query = query.offset(skip).limit(limit)
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_adults_with_partners_in_rooms(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        room_ids: list[UUID4],
    ) -> Sequence[Dweller]:
        """Active adults with a partner currently assigned to any of the given rooms."""
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.partner_id.is_not(None))
            .where(self.model.room_id.in_(room_ids))
            .where(self.model.age_group == AgeGroupEnum.ADULT)
            .where(~self.model.is_deleted)
        )
        return list((await db_session.execute(query)).scalars().all())

    async def create_random(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        obj_in: DwellerCreateCommonOverride | None = None,
        seed: int | None = None,
        rarity: RarityEnum = RarityEnum.COMMON,
        register_bio_places: bool = True,
    ) -> Dweller:
        """Create a random dweller.

        Pass ``seed`` through for deterministic output (used by dev/QA seeding).
        ``rarity`` is threaded to the generator — the radio service rolls RARE
        on a rare_chance and passes it here.

        When ``register_bio_places`` is True (default) the procedural bio places
        are registered on the world map. Callers that compose their OWN bio and
        register their own places (e.g. pregen_service) pass False to avoid
        double registration.
        """
        has_custom_name = bool(obj_in and (obj_in.first_name is not None or obj_in.last_name is not None))
        if rarity in (RarityEnum.RARE, RarityEnum.LEGENDARY) and not has_custom_name:
            from app.utils.static_data import game_data_store

            rng = random.Random(seed) if seed is not None else None
            active_names = await self.lock_vault_for_template(db_session, vault_id)
            template = game_data_store.pick_template(
                rarity.value,
                rng=rng,
                exclude_names=active_names or None,
            )
            if template is not None:
                return await self._create_template(
                    db_session, vault_id, template, register_bio_places=register_bio_places, seed=seed
                )
            rarity = RarityEnum.COMMON
        dweller_data = create_random_common_dweller(seed=seed, rarity=rarity)
        if obj_in:
            new_dweller_data = obj_in.model_dump(exclude_unset=True)
            if stat := new_dweller_data.get("special_boost"):
                dweller_data[stat.value.lower()] = game_config.dweller.boosted_stat_value
                new_dweller_data.pop("special_boost")
            dweller_data.update(new_dweller_data)

        return await self._persist_with_bio_places(db_session, vault_id, dweller_data, register_bio_places)

    async def create_from_template(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        template_id: str,
        register_bio_places: bool = True,
        overrides: Mapping[str, Any] | None = None,
    ) -> Dweller:
        """Instantiate a dweller from a named template via the shared flow."""
        from app.utils.exceptions import ResourceNotFoundException
        from app.utils.static_data import game_data_store

        template = game_data_store.get_dweller(template_id)
        if template is None:
            raise ResourceNotFoundException(template_id)
        return await self._create_template(db_session, vault_id, template, register_bio_places, overrides=overrides)

    async def get_active_template_names(self, db_session: AsyncSession, vault_id: UUID4) -> set[str]:
        """Return names that reserve curated templates in a vault."""
        rows = (
            await db_session.execute(
                select(Dweller.first_name, Dweller.last_name)
                .where(Dweller.vault_id == vault_id)
                .where(~Dweller.is_deleted)
            )
        ).all()
        return {f"{first_name} {last_name or ''}".strip().casefold() for first_name, last_name in rows}

    async def lock_vault_for_template(self, db_session: AsyncSession, vault_id: UUID4) -> set[str]:
        """Take a row lock on the vault so template reservation is atomic, then return active names.

        The lock is held until the caller's next commit/rollback — the shared
        persist path commits, which makes the check-then-insert reservation
        atomic under concurrency (a second creator blocks on the lock and then
        sees the committed dweller in its fresh name snapshot). SQLite test
        engines ignore FOR UPDATE; PostgreSQL enforces it in production.
        """
        from app.models.vault import Vault

        await db_session.execute(select(Vault).where(Vault.id == vault_id).with_for_update())
        return await self.get_active_template_names(db_session, vault_id)

    async def _create_template(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        template: Any,
        register_bio_places: bool,
        *,
        seed: int | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> Dweller:
        """Persist a curated template while preserving its identity and SPECIAL.

        Reservation is enforced here: the vault row is locked and the template's
        canonical name is checked against active dwellers before insert, so no
        caller can bypass per-vault uniqueness. Raises ResourceConflictException
        when the template is already active.
        """
        from app.utils.dwellers import create_dweller_from_template

        active_names = await self.lock_vault_for_template(db_session, vault_id)
        canonical = f"{template.first_name} {template.last_name or ''}".strip().casefold()
        if canonical in active_names:
            raise ResourceConflictException(detail=f"Template dweller '{canonical}' is already active in this vault")
        data = create_dweller_from_template(template, seed=seed)
        if overrides:
            for field in ("level", "experience", "happiness", "health", "max_health"):
                if (value := overrides.get(field)) is not None:
                    data[field] = value
        return await self._persist_with_bio_places(db_session, vault_id, data, register_bio_places)

    @staticmethod
    async def _persist_with_bio_places(
        db_session: AsyncSession,
        vault_id: UUID4,
        dweller_data: dict[str, Any],
        register_bio_places: bool,
    ) -> Dweller:
        """Persist a dweller payload and register its explicit bio-place metadata once."""
        bio_places = dweller_data.pop("_bio_places", None)
        db_obj = Dweller(**dweller_data, vault_id=vault_id)
        db_session.add(db_obj)
        await db_session.commit()
        await db_session.refresh(db_obj)
        if bio_places and register_bio_places:
            from app.services.map_service import map_service

            origin, visited = bio_places
            await map_service.register_bio_places(db_session, db_obj, origin_place=origin or "", visited_places=visited)
        return db_obj

    @staticmethod
    def calculate_experience_required(dweller_obj: Dweller) -> int:
        """Calculate the experience required for the next level."""
        return int(100 * 1.5**dweller_obj.level)

    @staticmethod
    def is_alive(dweller_obj: Dweller) -> bool:
        return dweller_obj.health > 0

    async def add_experience(self, db_session: AsyncSession, dweller_obj: Dweller, amount: int):
        """Add experience to dweller and level up if necessary."""
        from app.services.notification_service import notification_service

        old_level = dweller_obj.level
        dweller_obj.experience += amount
        experience_required = self.calculate_experience_required(dweller_obj)
        leveled_up = False

        if dweller_obj.experience >= experience_required:
            dweller_obj.level += 1
            dweller_obj.experience -= experience_required
            leveled_up = True

        if reward_delivery_is_deferred(db_session):
            await persist_reward_change(db_session, dweller_obj)
            updated_dweller = dweller_obj
        else:
            updated_dweller = await self.update(
                db_session,
                dweller_obj.id,
                DwellerUpdate(level=dweller_obj.level, experience=dweller_obj.experience),
            )

        # Emit DWELLER_LEVEL_UP event for objective tracking
        if leveled_up and updated_dweller.vault_id and not reward_delivery_is_deferred(db_session):
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

            # Get vault to find the owner
            vault = await vault_crud.get(db_session, updated_dweller.vault_id)
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

    async def get_dweller_by_name(self, db_session: AsyncSession, name: str) -> Dweller | None:
        """Get dweller by name."""
        query = select(self.model).where(self.model.first_name == name)
        response = await db_session.execute(query)
        return response.scalars().first()

    async def move_to_room(
        self, db_session: AsyncSession, dweller_id: UUID4, room_id: UUID4
    ) -> DwellerReadWithRoomID | None:
        """Move dweller to a different room."""
        dweller_obj = await self.get(db_session, dweller_id)

        if dweller_obj.status == DwellerStatusEnum.EXPLORING:
            raise ResourceConflictException(detail="Dweller is exploring and cannot be assigned to a room")

        # Validate room transfer (can't move to same room)
        if dweller_obj.room_id == room_id:
            raise ResourceConflictException(detail="Dweller is already in the room")

        old_room_id = dweller_obj.room_id
        room_obj = await room_crud.get(db_session, room_id)

        # Validate vault transfer (can't move between vaults)
        if dweller_obj.vault_id != room_obj.vault_id:
            raise InvalidVaultTransferException

        await validate_room_assignment(db_session, dweller_obj, room_obj)

        if not dweller_obj.room_id and not await vault_crud.is_enough_population_space(
            db_session=db_session, vault_id=dweller_obj.vault_id, space_required=1
        ):
            raise ContentNoChangeException(detail="Not enough space in the vault to move dweller")

        new_status = determine_status_for_room(
            room_obj.category if room_id else None, room_obj.name if room_id else None
        )

        apprenticeship_update = (
            {"apprentice_stat": room_obj.ability, "apprentice_started_at": datetime.utcnow()}
            if not dweller_obj.is_mature
            else {"apprentice_stat": None, "apprentice_started_at": None, "apprentice_stat_gains": {}}
        )
        dweller_obj = await self.update(
            db_session,
            dweller_id,
            {"room_id": room_id, "status": new_status, **apprenticeship_update},
            commit=False,
        )

        # Leaving an arena room must clear the stale fighter slot, or later fighter picks get rejected.
        if old_room_id is not None:
            from app.services.arena_service import arena_service

            await arena_service.clear_fighter_slots_for_dweller(db_session, dweller_id, commit=False)
        await db_session.commit()

        # Emit dweller assigned event for objective tracking
        await event_bus.emit(
            GameEvent.DWELLER_ASSIGNED,
            dweller_obj.vault_id,
            {"dweller_id": str(dweller_id), "room_type": room_obj.name},
        )

        # Check if this is a "correct" assignment (dweller's highest SPECIAL matches room's ability)
        if room_obj.ability:
            special_stats = {
                "strength": dweller_obj.strength,
                "perception": dweller_obj.perception,
                "endurance": dweller_obj.endurance,
                "charisma": dweller_obj.charisma,
                "intelligence": dweller_obj.intelligence,
                "agility": dweller_obj.agility,
                "luck": dweller_obj.luck,
            }
            highest_stat = max(special_stats, key=special_stats.get)
            if highest_stat == room_obj.ability.value:
                await event_bus.emit(
                    GameEvent.DWELLER_ASSIGNED_CORRECTLY,
                    dweller_obj.vault_id,
                    {"dweller_id": str(dweller_id), "room_type": room_obj.name, "is_correct": True},
                )

        return DwellerReadWithRoomID.model_validate(dweller_obj)

    async def reanimate(self, db_session: AsyncSession, dweller_obj: Dweller) -> Dweller | None:
        """Revive a dead dweller."""
        if self.is_alive(dweller_obj):
            raise ContentNoChangeException(detail="Dweller is already alive")
        await self.update(
            db_session, dweller_obj.id, DwellerUpdate(health=dweller_obj.max_health, status=DwellerStatusEnum.IDLE)
        )
        return dweller_obj

    async def mark_as_dead(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        """Mark dweller as dead (health=0, status=DEAD)."""
        return await self.update(db_session, dweller_id, DwellerUpdate(health=0, status=DwellerStatusEnum.DEAD))

    async def get_full_info(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        """Get full information about a dweller."""
        query = (
            select(self.model)
            .options(
                selectinload(self.model.vault),
                selectinload(self.model.room),
                selectinload(self.model.weapon),
                selectinload(self.model.outfit),
            )
            .where(self.model.id == dweller_id)
        )
        response = await db_session.execute(query)
        dweller_obj = response.scalar_one_or_none()

        return DwellerReadFull.model_validate(dweller_obj)

    async def use_stimpack(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        """Use a stimpack to heal the dweller."""
        dweller_obj = await self.get(db_session, dweller_id)

        if dweller_obj.stimpack <= 0:
            raise ResourceConflictException(detail="No stimpacks available to use.")

        if dweller_obj.health >= dweller_obj.max_health:
            raise ContentNoChangeException(detail="Dweller is already at full health.")

        # Heal for 40% of max health (rounded)
        heal_amount = int(dweller_obj.max_health * 0.4)
        new_health = min(dweller_obj.health + heal_amount, dweller_obj.max_health)

        return await self.update(
            db_session, dweller_id, DwellerUpdate(health=new_health, stimpack=dweller_obj.stimpack - 1)
        )

    async def use_radaway(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        """Use a radaway to remove radiation from the dweller."""
        dweller_obj = await self.get(db_session, dweller_id)

        if dweller_obj.radaway <= 0:
            raise ResourceConflictException(detail="No radaways available to use.")

        if dweller_obj.radiation <= 0:
            raise ContentNoChangeException(detail="Dweller has no radiation to remove.")

        # Remove 50% of radiation (rounded)
        radiation_removal = int(dweller_obj.radiation * 0.5)
        new_radiation = max(dweller_obj.radiation - radiation_removal, 0)

        return await self.update(
            db_session, dweller_id, DwellerUpdate(radiation=new_radiation, radaway=dweller_obj.radaway - 1)
        )

    async def get_dead_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        include_permanent: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get dead dwellers for a vault.

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param include_permanent: If True, include permanently dead dwellers
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of dead dwellers
        """
        query = select(self.model).where(self.model.vault_id == vault_id).where(self.model.is_dead.is_(True))

        if not include_permanent:
            query = query.where(self.model.is_permanently_dead.is_(False))

        query = query.order_by(self.model.death_timestamp.desc()).offset(skip).limit(limit)
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_deleted_by_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get soft-deleted dwellers for a specific vault.

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of soft-deleted dwellers
        """
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.is_deleted)
            .order_by(self.model.deleted_at.desc())
            .options(selectinload(Dweller.weapon))
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_revivable_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get dwellers that can be revived (dead but not permanently dead).

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of revivable dwellers
        """
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.is_dead.is_(True))
            .where(self.model.is_permanently_dead.is_(False))
            .order_by(self.model.death_timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_graveyard(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get permanently dead dwellers (graveyard).

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of permanently dead dwellers
        """
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.is_permanently_dead.is_(True))
            .order_by(self.model.death_timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()

    async def auto_assign_to_best_room(
        self, db_session: AsyncSession, dweller_id: UUID4
    ) -> DwellerReadWithRoomID | None:
        """Auto-assign dweller to the best matching production room based on their highest SPECIAL stat."""
        from app.models.room import Room
        from app.schemas.common import SPECIALEnum

        dweller_obj = await self.get(db_session, dweller_id)
        validate_automatic_assignment(dweller_obj)

        # Find dweller's highest SPECIAL stat
        special_stats = {
            SPECIALEnum.STRENGTH: dweller_obj.strength,
            SPECIALEnum.PERCEPTION: dweller_obj.perception,
            SPECIALEnum.ENDURANCE: dweller_obj.endurance,
            SPECIALEnum.CHARISMA: dweller_obj.charisma,
            SPECIALEnum.INTELLIGENCE: dweller_obj.intelligence,
            SPECIALEnum.AGILITY: dweller_obj.agility,
            SPECIALEnum.LUCK: dweller_obj.luck,
        }

        best_stat = max(special_stats, key=special_stats.get)

        # Find production rooms in the dweller's vault that match this stat and have space
        query = (
            select(Room)
            .where(Room.vault_id == dweller_obj.vault_id)
            .where(Room.category == RoomTypeEnum.PRODUCTION)
            .where(Room.ability == best_stat)
        )
        response = await db_session.execute(query)
        matching_rooms = response.scalars().all()

        if not matching_rooms:
            raise ResourceConflictException(
                detail=f"No production rooms found matching {best_stat.value} stat in this vault"
            )

        # Check if dweller is already in a matching room
        if dweller_obj.room_id:
            current_room = await room_crud.get(db_session, dweller_obj.room_id)
            if current_room.category == RoomTypeEnum.PRODUCTION and current_room.ability == best_stat:
                raise ContentNoChangeException(
                    detail=f"Dweller is already assigned to the best matching room ({current_room.name})"
                )

        # Find room with available capacity (based on room size)
        room_ids = [r.id for r in matching_rooms]
        count_stmt = (
            select(Dweller.room_id, func.count(Dweller.id).label("count"))
            .where(Dweller.room_id.in_(room_ids))
            .group_by(Dweller.room_id)
        )
        count_result = await db_session.execute(count_stmt)
        counts = {row.room_id: row.count for row in count_result}

        best_room = None
        for room in matching_rooms:
            dweller_count = counts.get(room.id, 0)

            # Room capacity: 2 dwellers per 3 size units (e.g., size 3 = 2 dwellers, size 6 = 4 dwellers)
            max_dwellers = room.size // 3 * 2 if room.size else 0
            if dweller_count < max_dwellers:
                best_room = room
                break

        if not best_room:
            raise ResourceConflictException(detail=f"All {best_stat.value} production rooms are at full capacity")

        # Move dweller to the best room
        return await self.move_to_room(db_session, dweller_id, best_room.id)


dweller = CRUDDweller(Dweller)
