"""General dweller business logic service."""

import logging
import random
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    AgeGroupEnum,
    ContentProvenanceEnum,
    DwellerRosterFocus,
    DwellerStatusEnum,
    ExpeditionRunStatus,
    ExplorationStatus,
    FactionEnum,
    GenderEnum,
    RaceEnum,
    RarityEnum,
    RoomTypeEnum,
)
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import training as training_crud
from app.crud.dweller import determine_status_for_room
from app.crud.storage import storage as storage_crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.storage import Storage
from app.options.appearance import (
    background_options,
    body_type_options,
    expression_options,
    eye_color_options,
    hair_color_options,
    haircuts,
    headgear_options,
    height_options,
    pose_options,
    skin_tone_options,
)
from app.options.factions import faction_restrictions
from app.options.races import STATE_OF_BEING_VALUES, RaceOption, is_ageless, race_of
from app.schemas.dweller import (
    DwellerAppearanceOptions,
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerIdentityOptions,
    DwellerReadWithRoomID,
    DwellerUpdate,
    DwellerUpdateRequest,
)
from app.services.leveling_service import leveling_service
from app.services.map_service import map_service
from app.services.room_assignment_policy import (
    calculate_room_capacity,
    get_highest_special,
    validate_automatic_assignment,
    validate_room_assignment,
)
from app.services.training_service import training_service
from app.services.user_service import user_service
from app.services.vault_service import vault_service
from app.utils.appearance_roll import complete_appearance
from app.utils.dwellers import elder_birth_threshold
from app.utils.exceptions import (
    ContentNoChangeException,
    FeatureDisabledException,
    InvalidVaultTransferException,
    ResourceConflictException,
    ResourceNotFoundException,
    VaultOperationException,
)
from app.utils.reward_delivery import persist_reward_change

if TYPE_CHECKING:
    from app.services.map.bio_registration import _MapDwellerLike

logger = logging.getLogger(__name__)


class DwellerService:
    """Service for general dweller operations that span multiple CRUD modules."""

    @staticmethod
    def _require_vault_id(dweller: Dweller) -> UUID4:
        if dweller.vault_id is None:
            raise VaultOperationException(detail="Dweller is no longer in this vault")
        return dweller.vault_id

    async def delete_dweller(self, db_session: AsyncSession, dweller_id: UUID4, *, soft: bool = True) -> None:
        """Delete a dweller and close any in-progress journey in one transaction.

        A deleted dweller cannot keep exploring; leaving the journey active would
        orphan it (the detail endpoint could no longer resolve the dweller).
        """
        dweller = await crud.dweller.get_for_update(db_session, dweller_id, include_deleted=True)
        if dweller is None:
            raise ResourceNotFoundException(Dweller, dweller_id)
        now = datetime.now(UTC).replace(tzinfo=None)
        explorations = await crud.exploration.get_in_progress_for_dwellers(db_session, [dweller_id])
        for exploration in explorations:
            exploration.status = ExplorationStatus.RECALLED
            exploration.end_time = now
            exploration.return_started_at = None
            exploration.return_completes_at = None
            exploration.paused_at = None
            exploration.unclaimed_loot = []
            db_session.add(exploration)
            run = await crud.expedition_run.get_open_for_exploration_for_update(db_session, exploration.id)
            if run is not None:
                run.status = ExpeditionRunStatus.RETREATED
                run.finished_at = now
                db_session.add(run)
        await crud.dweller.delete(db_session, dweller_id, soft=soft, commit=False)
        await db_session.commit()

    def get_identity_options(self) -> DwellerIdentityOptions:
        """Return identity choices derived directly from the canonical options modules."""
        factions_by_race = (
            {}
            if not game_config.features.faction_mechanics
            else {
                race.value: [faction.value for faction in factions] for race, factions in faction_restrictions.items()
            }
        )
        return DwellerIdentityOptions(
            races=[race.value for race in RaceOption],
            factions_by_race=factions_by_race,
            states_by_race={race.value: states for race, states in STATE_OF_BEING_VALUES.items()},
        )

    def get_appearance_options(self) -> DwellerAppearanceOptions:
        """Return the canonical appearance choices derived from the options module."""
        return DwellerAppearanceOptions(
            skin_tones_by_race={race.value: tones for race, tones in skin_tone_options.items()},
            builds_by_race={race.value: builds for race, builds in body_type_options.items()},
            haircuts_by_race={race.value: cuts for race, cuts in haircuts.items()},
            headgear_by_race={race.value: gear for race, gear in headgear_options.items()},
            expressions=list(expression_options),
            poses=pose_options,
            backgrounds=background_options,
            heights=height_options,
            eye_colors=eye_color_options,
            hair_colors=hair_color_options,
        )

    async def create_dweller(
        self,
        db_session: AsyncSession,
        obj_in: DwellerCreate,
        *,
        commit: bool = True,
        content_provenance: ContentProvenanceEnum = ContentProvenanceEnum.PLAYER_EDITED,
    ) -> Dweller:
        """Create a dweller and record the overseer's lifetime total.

        ``content_provenance`` defaults to the private/player-authored value; system
        generators pass ``GENERATED`` and curated templates pass ``CURATED`` so future
        backfills can exclude content they must not rewrite.

        A ``commit=False`` caller owns the commit and must emit the DWELLER_ADDED event itself after committing.
        """
        obj_in = obj_in.model_copy(update={"visual_attributes": complete_appearance(obj_in.model_dump())})
        dweller = await crud.dweller.create(db_session, obj_in, commit=False)
        dweller.content_provenance = content_provenance
        if commit:
            await db_session.commit()
            await db_session.refresh(dweller)
        vault_id = self._require_vault_id(dweller)
        await user_service.record_vault_statistic(db_session, vault_id, "total_dwellers_created", commit=commit)
        if commit:
            await event_bus.emit(GameEvent.DWELLER_ADDED, vault_id, {"dweller_id": str(dweller.id)})
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
        payload["visual_attributes"] = complete_appearance(payload, random.Random(seed))
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
        dweller = await self._persist_registered_dweller(db_session, vault_id, payload, register_bio_places=True)
        from app.services.family.known_relations import reconcile_known_parent_links

        await reconcile_known_parent_links(db_session, vault_id, template_id)
        return dweller

    async def _persist_registered_dweller(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        payload: dict[str, Any],
        register_bio_places: bool,
    ) -> Dweller:
        """Persist a prepared payload, record the lifetime total and register explicit bio places."""
        from app.services.bio_service import make_entry

        payload["visual_attributes"] = complete_appearance(payload)
        bio_places = payload.pop("_bio_places", None)
        if payload.get("bio") and not payload.get("bio_entries"):
            payload["bio_entries"] = [make_entry("template", payload["bio"])]
        dweller = await crud.dweller.persist_new_dweller(db_session, vault_id, payload)
        await user_service.record_vault_statistic(db_session, vault_id, "total_dwellers_created")
        await event_bus.emit(GameEvent.DWELLER_ADDED, vault_id, {"dweller_id": str(dweller.id)})
        if bio_places and register_bio_places:
            origin, visited = bio_places
            await map_service.register_bio_places(
                db_session, cast("_MapDwellerLike", dweller), origin_place=origin or "", visited_places=visited
            )
        return dweller

    async def add_experience(self, db_session: AsyncSession, dweller_obj: Dweller, amount: int) -> Dweller:
        """Add cumulative XP and settle levels/health in the reward transaction."""
        old_level = dweller_obj.level
        dweller_obj.experience += amount
        await leveling_service.check_level_up(db_session, dweller_obj, commit=False)
        await persist_reward_change(db_session, dweller_obj, refresh=True)

        if dweller_obj.level > old_level:
            await leveling_service.settle_level_up(
                db_session,
                dweller_obj,
                old_level=old_level,
                levels_gained=dweller_obj.level - old_level,
            )

        return dweller_obj

    async def list_vault_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        *,
        skip: int = 0,
        limit: int = 100,
        status: DwellerStatusEnum | None = None,
        focus: DwellerRosterFocus | None = None,
        age_group: AgeGroupEnum | None = None,
        gender: GenderEnum | None = None,
        rarity: RarityEnum | None = None,
        search: str | None = None,
        race: RaceEnum | None = None,
        faction: FactionEnum | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> Sequence[Dweller]:
        """The vault roster query.

        Identity filters are enum-typed at the boundary and translated to the stored
        ``visual_attributes`` values here, so the endpoint stays transport-only.
        """
        if faction is not None and not game_config.features.faction_mechanics:
            raise FeatureDisabledException("Faction filtering is disabled while the faction switch is off.")
        return await crud.dweller.get_multi_by_vault(
            db_session=db_session,
            vault_id=vault_id,
            skip=skip,
            limit=limit,
            status=status,
            focus=focus,
            age_group=age_group,
            gender=gender,
            rarity=rarity,
            search=search,
            race=race.value if race else None,
            faction=faction.value if faction else None,
            sort_by=sort_by,
            order=order,
        )

    async def update_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        dweller_data: DwellerUpdate | DwellerUpdateRequest | dict[str, Any],
    ) -> Any:
        """Update a dweller, computing room-based status automatically.

        When room_id is being changed, determines the correct dweller status
        (idle/working/training) based on the target room's category.
        """
        # Ensure we work with a dict for mutation
        data = dweller_data if isinstance(dweller_data, dict) else dweller_data.model_dump(exclude_unset=True)
        room_id = data.get("room_id")
        name_fields = ("first_name", "last_name")
        existing: Dweller | None = None
        if "room_id" in data or any(field in data for field in name_fields):
            existing = await crud.dweller.get(db_session, dweller_id)
        name_changed = existing is not None and any(
            field in data and data[field] != getattr(existing, field) for field in name_fields
        )
        room_changed = "room_id" in data and existing is not None and room_id != existing.room_id

        if room_changed:
            active_training = await training_crud.training.get_active_by_dweller(db_session, dweller_id)
            if active_training:
                await training_service.cancel_training(db_session, active_training.id, dweller=existing)

        # An unchanged posting must preserve the active match's busy status.
        if room_changed:
            if room_id is None:
                data["status"] = determine_status_for_room(None)
            else:
                room_obj = await crud.room.get(db_session, room_id)
                if not room_obj:
                    raise ResourceNotFoundException(model=Room, identifier=room_id)
                data["status"] = determine_status_for_room(room_obj.category, room_obj.name)

        if room_changed:
            from app.services.combat.arena_service import arena_service

            await arena_service.clear_fighter_slots_for_dweller(db_session, dweller_id, commit=False)

        updated = await crud.dweller.update(db_session, dweller_id, DwellerUpdate(**data), commit=False)
        if name_changed:
            updated.content_provenance = ContentProvenanceEnum.PLAYER_EDITED

        if "visual_attributes" in data:
            if is_ageless(race_of(updated)):
                if updated.age_group == AgeGroupEnum.ELDER:
                    updated.age_group = AgeGroupEnum.ADULT
                updated.radiation = 0
                if updated.radaway > 0:
                    storage = await storage_crud.get_by_vault_for_update(db_session, self._require_vault_id(updated))
                    if storage is None:
                        storage = Storage(vault_id=self._require_vault_id(updated))
                    storage.radaway += updated.radaway
                    updated.radaway = 0
                    db_session.add(storage)
            elif updated.age_group in (AgeGroupEnum.ADULT, AgeGroupEnum.ELDER):
                updated.age_group = (
                    AgeGroupEnum.ELDER
                    if updated.birth_date is not None
                    and updated.birth_date <= elder_birth_threshold(datetime.now(UTC).replace(tzinfo=None))
                    else AgeGroupEnum.ADULT
                )
            db_session.add(updated)

        await db_session.commit()
        return updated

    async def move_to_room(
        self, db_session: AsyncSession, dweller_id: UUID4, room_id: UUID4, *, commit: bool = True
    ) -> DwellerReadWithRoomID:
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
            db_session=db_session, vault_id=self._require_vault_id(dweller_obj), space_required=1
        ):
            raise ContentNoChangeException(detail="Not enough space in the vault to move dweller")

        new_status = determine_status_for_room(room_obj.category, room_obj.name)

        apprenticeship_update = (
            {"apprentice_stat": room_obj.ability, "apprentice_started_at": datetime.utcnow()}
            if not dweller_obj.is_mature
            else {"apprentice_stat": None, "apprentice_started_at": None, "apprentice_stat_gains": {}}
        )
        # Leaving an arena room must clear the stale fighter slot, or later fighter picks get rejected.
        if old_room_id is not None:
            from app.services.combat.arena_service import arena_service

            await arena_service.clear_fighter_slots_for_dweller(db_session, dweller_id, commit=False)

        dweller_obj = await crud.dweller.update(
            db_session, dweller_id, {"room_id": room_id, "status": new_status, **apprenticeship_update}, commit=False
        )

        if commit:
            await db_session.commit()
            await self.publish_room_assignment(dweller_obj, room_obj)
        else:
            await db_session.flush()
        return DwellerReadWithRoomID.model_validate(dweller_obj)

    async def publish_room_assignment(self, dweller_obj: Dweller, room_obj: Room) -> None:
        """Deliver progression only after the transaction owning the move commits."""
        # Emit dweller assigned event for objective tracking
        await event_bus.emit(
            GameEvent.DWELLER_ASSIGNED,
            self._require_vault_id(dweller_obj),
            {"dweller_id": str(dweller_obj.id), "room_type": room_obj.name},
        )

        # Check if this is a "correct" assignment (dweller's highest SPECIAL matches room's ability)
        if room_obj.ability and get_highest_special(dweller_obj) == room_obj.ability:
            await event_bus.emit(
                GameEvent.DWELLER_ASSIGNED_CORRECTLY,
                self._require_vault_id(dweller_obj),
                {"dweller_id": str(dweller_obj.id), "room_type": room_obj.name, "is_correct": True},
            )

    async def auto_assign_to_best_room(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadWithRoomID:
        """Auto-assign dweller to the best matching production room based on their highest SPECIAL stat."""
        dweller_obj = await crud.dweller.get(db_session, dweller_id)
        validate_automatic_assignment(dweller_obj)

        # Find dweller's highest SPECIAL stat
        best_stat = get_highest_special(dweller_obj)

        # Find production rooms in the dweller's vault that match this stat
        production_rooms = await crud.room.get_by_category(
            db_session, self._require_vault_id(dweller_obj), RoomTypeEnum.PRODUCTION
        )
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
            dweller_count = await crud.dweller.count_in_room(db_session, room.id, include_apprentices=False)
            if dweller_count < calculate_room_capacity(room.size):
                best_room = room
                break

        if not best_room:
            raise ResourceConflictException(detail=f"All {best_stat.value} production rooms are at full capacity")

        # Move dweller to the best room
        return await self.move_to_room(db_session, dweller_id, best_room.id)


dweller_service = DwellerService()
