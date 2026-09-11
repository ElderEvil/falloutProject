import random
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import UUID4
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum, GenderEnum, RarityEnum, RoomTypeEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud.base import CRUDBase
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerReadFull,
    DwellerUpdate,
)
from app.services.room_assignment_policy import adult_assignment_conditions
from app.utils.dwellers import create_random_common_dweller
from app.utils.exceptions import ContentNoChangeException, ResourceConflictException
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
    async def create(self, db_session: AsyncSession, obj_in: DwellerCreate) -> Dweller:
        """Create a dweller and record the overseer's lifetime total."""
        dweller = await super().create(db_session, obj_in)

        from app.services.user_service import user_service

        await user_service.record_vault_statistic(db_session, dweller.vault_id, "total_dwellers_created")
        return dweller

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

    async def has_other_apprentice(
        self, db_session: AsyncSession, *, room_id: UUID4, exclude_dweller_id: UUID4
    ) -> bool:
        """Whether a room already has an apprentice besides the given dweller."""
        query = select(self.model.id).where(
            self.model.room_id == room_id,
            self.model.id != exclude_dweller_id,
            self.model.apprentice_started_at.is_not(None),
            ~self.model.is_deleted,
        )
        response = await db_session.execute(query)
        return response.scalars().first() is not None

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
    ) -> Sequence[Dweller]:
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

    async def get_by_room(self, db_session: AsyncSession, room_id: UUID4) -> Sequence[Dweller]:
        """Dwellers assigned to one room, excluding soft-deleted."""
        query = select(self.model).where(self.model.room_id == room_id, ~self.model.is_deleted)
        return (await db_session.execute(query)).scalars().all()

    async def get_aging_youth(
        self, db_session: AsyncSession, vault_id: UUID4, age_group: AgeGroupEnum, born_before: datetime
    ) -> Sequence[Dweller]:
        """Dwellers of one young age group born before the threshold (ready to age up)."""
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.age_group == age_group)
            .where(self.model.birth_date.is_not(None))
            .where(self.model.birth_date <= born_before)
        )
        return list((await db_session.execute(query)).scalars().all())

    async def get_children_of(
        self, db_session: AsyncSession, *, vault_id: UUID4, parent_ids: Sequence[UUID4], exclude_id: UUID4 | None = None
    ) -> Sequence[Dweller]:
        """Live dwellers in a vault whose parent_1 or parent_2 is one of the given ids."""
        from sqlalchemy import or_

        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(~self.model.is_deleted)
            .where(~self.model.is_dead)
            .where(or_(self.model.parent_1_id.in_(parent_ids), self.model.parent_2_id.in_(parent_ids)))
        )
        if exclude_id is not None:
            query = query.where(self.model.id != exclude_id)
        return list((await db_session.execute(query)).scalars().all())

    async def get_reciprocal_partners(
        self, db_session: AsyncSession, vault_id: UUID4, dweller_id: UUID4
    ) -> Sequence[Dweller]:
        """Live dwellers in a vault whose partner_id points at this dweller."""
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(~self.model.is_deleted)
            .where(~self.model.is_dead)
            .where(self.model.partner_id == dweller_id)
        )
        return list((await db_session.execute(query)).scalars().all())

    async def count_death_stats(self, db_session: AsyncSession, vault_ids: Sequence[UUID4]) -> tuple[int, int]:
        """(revivable, permanently_dead) dead-dweller counts across the given vaults."""
        revivable_query = (
            select(self.model)
            .where(self.model.vault_id.in_(vault_ids))
            .where(self.model.is_dead)
            .where(~self.model.is_permanently_dead)
        )
        revivable = len((await db_session.execute(revivable_query)).scalars().all())

        permanent_query = (
            select(self.model).where(self.model.vault_id.in_(vault_ids)).where(self.model.is_permanently_dead)
        )
        permanent = len((await db_session.execute(permanent_query)).scalars().all())
        return revivable, permanent

    async def get_permanently_dead_before(self, db_session: AsyncSession, cutoff: datetime) -> Sequence[Dweller]:
        """Dead, not-yet-permanent dwellers whose death predates the cutoff."""
        query = (
            select(self.model)
            .where(self.model.is_dead)
            .where(~self.model.is_permanently_dead)
            .where(self.model.death_timestamp <= cutoff)
        )
        return list((await db_session.execute(query)).scalars().all())

    async def get_by_room_ids(
        self, db_session: AsyncSession, vault_id: UUID4, room_ids: list[UUID4]
    ) -> Sequence[Dweller]:
        """Assigned dwellers of a vault filtered to the given rooms, excluding soft-deleted."""
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.room_id.in_(room_ids))
            .where(~self.model.is_deleted)
        )
        return (await db_session.execute(query)).scalars().all()

    async def count_alive_in_vault(
        self, db_session: AsyncSession, vault_id: UUID4, *, min_level: int | None = None
    ) -> int:
        """Count non-deleted dwellers of a vault, optionally with a level floor."""
        conditions = [self.model.vault_id == vault_id, ~self.model.is_deleted]
        if min_level is not None:
            conditions.append(self.model.level >= min_level)
        result = await db_session.execute(select(func.count(self.model.id)).where(and_(*conditions)))
        return result.scalar_one()

    async def count_room_names_by_type(self, db_session: AsyncSession, vault_id: UUID4) -> list[str]:
        """Room names of a vault (for callers that classify them by normalized type)."""
        from app.models.room import Room

        result = await db_session.execute(select(Room.name).where(Room.vault_id == vault_id))
        return list(result.scalars().all())

    async def count_in_room(self, db_session: AsyncSession, room_id: UUID4) -> int:
        """Count all dwellers currently occupying a room (no status filters)."""
        result = await db_session.execute(select(func.count(self.model.id)).where(self.model.room_id == room_id))
        return int(result.scalar_one())

    async def get_unassigned_adults(
        self, db_session: AsyncSession, vault_id: UUID4, age_group: AgeGroupEnum | None = None
    ) -> Sequence[Dweller]:
        """Idle adults without a room, optionally narrowed to one age group."""
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.status == DwellerStatusEnum.IDLE)
            .where(self.model.room_id.is_(None))
            .where(*adult_assignment_conditions())
            .where(~self.model.is_deleted)
            .where(~self.model.is_dead)
        )
        if age_group:
            query = query.where(self.model.age_group == age_group)
        return list((await db_session.execute(query)).scalars().all())

    async def get_all_in_vault(self, db_session: AsyncSession, vault_id: UUID4) -> Sequence[Dweller]:
        """Every dweller row of a vault, no status/deleted filters (tick processing)."""
        result = await db_session.execute(select(self.model).where(self.model.vault_id == vault_id))
        return result.scalars().all()

    async def count_in_vault(self, db_session: AsyncSession, vault_id: UUID4) -> int:
        """Count every dweller row of a vault (no status/deleted filters)."""
        result = await db_session.execute(select(func.count(self.model.id)).where(self.model.vault_id == vault_id))
        return int(result.scalar_one())

    async def get_active_apprentices(self, db_session: AsyncSession, vault_id: UUID4) -> Sequence[Dweller]:
        """All active apprentices of a vault."""
        query = select(self.model).where(
            self.model.vault_id == vault_id,
            self.model.apprentice_stat.is_not(None),
            self.model.apprentice_started_at.is_not(None),
            ~self.model.is_deleted,
            ~self.model.is_dead,
        )
        return (await db_session.execute(query)).scalars().all()

    async def get_living_quarters_dwellers(self, db_session: AsyncSession, vault_id: UUID4) -> Sequence[Dweller]:
        """Dwellers assigned to living-quarter (capacity) rooms of a vault."""
        from app.models.room import Room

        query = (
            select(self.model)
            .join(Room, self.model.room_id == Room.id)
            .where(
                self.model.vault_id == vault_id,
                self.model.room_id.is_not(None),
                Room.name.ilike("%living%"),
                Room.category == RoomTypeEnum.CAPACITY,
            )
        )
        return (await db_session.execute(query)).scalars().all()

    async def get_healthy_adults_in_room(self, db_session: AsyncSession, room_id: UUID4) -> Sequence[Dweller]:
        """Adult dwellers with positive health in a room, weapon/outfit eager-loaded."""
        query = (
            select(self.model)
            .options(
                selectinload(self.model.weapon),
                selectinload(self.model.outfit),
            )
            .where(
                (self.model.room_id == room_id)
                & (self.model.health > 0)
                & self.model.is_adult
                & (self.model.age_group == AgeGroupEnum.ADULT)
            )
        )
        return list((await db_session.execute(query)).scalars().all())

    async def get_by_ids_in_vault(
        self, db_session: AsyncSession, ids: list[UUID4], vault_id: UUID4
    ) -> Sequence[Dweller]:
        """Dwellers by ids scoped to one vault (no status filters)."""
        query = select(self.model).where(self.model.id.in_(ids), self.model.vault_id == vault_id)
        return (await db_session.execute(query)).scalars().all()

    @staticmethod
    def _arena_fighter_conditions(room_id: UUID4, *, require_alive: bool = True) -> list[Any]:
        conditions = [
            Dweller.room_id == room_id,
            Dweller.is_adult,
            Dweller.age_group == AgeGroupEnum.ADULT,
        ]
        if require_alive:
            conditions.append(Dweller.health > 0)
        return conditions

    async def get_arena_fighters(
        self, db_session: AsyncSession, room_id: UUID4, *, ids: Sequence[UUID4] | None = None
    ) -> Sequence[Dweller]:
        """Adult, alive dwellers assigned to a room (arena fighters), weapon eager-loaded."""
        query = (
            select(self.model).options(selectinload(self.model.weapon)).where(*self._arena_fighter_conditions(room_id))
        )
        if ids is not None:
            query = query.where(self.model.id.in_(ids))
        return (await db_session.execute(query)).scalars().all()

    async def get_arena_roster(self, db_session: AsyncSession, room_id: UUID4) -> Sequence[Dweller]:
        """Adult, alive dwellers assigned to a room, oldest first (arena roster)."""
        query = select(self.model).where(*self._arena_fighter_conditions(room_id)).order_by(self.model.created_at)
        return (await db_session.execute(query)).scalars().all()

    async def get_first_active_apprentice(self, db_session: AsyncSession, vault_id: UUID4) -> Dweller | None:
        """The vault's longest-standing active apprentice, if any."""
        query = (
            select(self.model)
            .where(
                self.model.vault_id == vault_id,
                self.model.apprentice_stat.is_not(None),
                self.model.apprentice_started_at.is_not(None),
                ~self.model.is_deleted,
                ~self.model.is_dead,
            )
            .order_by(self.model.apprentice_started_at)
        )
        return (await db_session.execute(query)).scalars().first()

    async def get_bio_without_locations(
        self, db_session: AsyncSession, vault_id: UUID4, limit: int | None = None
    ) -> Sequence[Dweller]:
        """Dwellers with a bio but no DwellerLocation links, oldest first."""
        from sqlalchemy import exists

        from app.models.wasteland_location import DwellerLocation

        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(~self.model.is_deleted)
            .where(self.model.bio.is_not(None))
            .where(self.model.bio != "")
            .where(~exists().where(DwellerLocation.dweller_id == self.model.id))
            .order_by(self.model.created_at)
        )
        if limit is not None:
            query = query.limit(limit)
        return (await db_session.execute(query)).scalars().all()

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
        from app.services.user_service import user_service

        await user_service.record_vault_statistic(db_session, vault_id, "total_dwellers_created")
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

    async def reanimate(self, db_session: AsyncSession, dweller_obj: Dweller) -> Dweller | None:
        """Revive a dead dweller."""
        if self.is_alive(dweller_obj):
            raise ContentNoChangeException(detail="Dweller is already alive")
        await self.update(
            db_session,
            dweller_obj.id,
            DwellerUpdate(health=dweller_obj.effective_max_health, status=DwellerStatusEnum.IDLE),
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

    async def get_tradable_by_id(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller | None:
        """Soft-deleted, non-dead dweller by id (trading-post candidate)."""
        query = (
            select(self.model)
            .where(self.model.id == dweller_id)
            .where(self.model.is_deleted)
            .where(~self.model.is_dead)
        )
        return (await db_session.execute(query)).scalars().one_or_none()

    async def get_tradable(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4 | None = None,
        exclude_vault_id: UUID4 | None = None,
        limit: int | None = None,
    ) -> Sequence[Dweller]:
        """Soft-deleted, non-dead dwellers, newest deletions first, weapon eager-loaded.

        Optionally scoped to one vault (``vault_id``) or to every other vault
        (``exclude_vault_id``), optionally capped at ``limit``.
        """
        query = (
            select(self.model)
            .where(self.model.is_deleted)
            .where(~self.model.is_dead)
            .order_by(self.model.deleted_at.desc())
            .options(selectinload(Dweller.weapon))
        )
        if vault_id is not None:
            query = query.where(self.model.vault_id == vault_id)
        if exclude_vault_id is not None:
            query = query.where(self.model.vault_id != exclude_vault_id)
        if limit is not None:
            query = query.limit(limit)
        return (await db_session.execute(query)).scalars().all()

    async def get_recyclable(
        self,
        db_session: AsyncSession,
        *,
        gender: GenderEnum | None = None,
        rarity: RarityEnum | None = None,
        deleted_before: datetime | None = None,
        limit: int = 10,
    ) -> Sequence[Dweller]:
        """Soft-deleted dwellers eligible for recycling, newest deletions first."""
        query = select(self.model).where(self.model.is_deleted).order_by(self.model.deleted_at.desc()).limit(limit)
        if deleted_before is not None:
            query = query.where(self.model.deleted_at <= deleted_before)
        if gender is not None:
            query = query.where(self.model.gender == gender)
        if rarity is not None:
            query = query.where(self.model.rarity == rarity)
        return (await db_session.execute(query)).scalars().all()

    async def get_for_update(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller | None:
        """One dweller locked FOR UPDATE (recycling race protection)."""
        result = await db_session.execute(select(self.model).where(self.model.id == dweller_id).with_for_update())
        return result.scalars().one_or_none()

    async def get_soft_deleted_before(
        self, db_session: AsyncSession, cutoff: datetime, limit: int
    ) -> Sequence[Dweller]:
        """Soft-deleted dwellers deleted at or before the cutoff, oldest first."""
        query = (
            select(self.model)
            .where(self.model.is_deleted)
            .where(self.model.deleted_at <= cutoff)
            .order_by(self.model.deleted_at.asc())
            .limit(limit)
        )
        return (await db_session.execute(query)).scalars().all()

    async def count_soft_deleted(self, db_session: AsyncSession, deleted_before: datetime | None = None) -> int:
        """Count soft-deleted dwellers, optionally only those deleted at/before a cutoff."""
        conditions = [self.model.is_deleted]
        if deleted_before is not None:
            conditions.append(self.model.deleted_at <= deleted_before)
        result = await db_session.execute(select(func.count()).where(and_(*conditions)))
        return int(result.scalar_one())

    async def count_soft_deleted_grouped(self, db_session: AsyncSession, column: Any) -> list[tuple[Any, int]]:
        """Soft-deleted dweller counts grouped by a column (e.g. gender, rarity)."""
        query = select(column, func.count()).where(self.model.is_deleted).group_by(column)
        return [(row[0], row[1]) for row in (await db_session.execute(query)).all()]

    async def get_oldest_deleted_at(self, db_session: AsyncSession) -> datetime | None:
        """Earliest deletion timestamp among soft-deleted dwellers, or None."""
        result = await db_session.execute(select(func.min(self.model.deleted_at)).where(self.model.is_deleted))
        return result.scalar_one_or_none()

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


dweller = CRUDDweller(Dweller)
