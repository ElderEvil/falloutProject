from contextlib import contextmanager
from itertools import pairwise
from operator import itemgetter
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlmodel import select

from app import crud
from app.core.enums import (
    AgeGroupEnum,
    DwellerStatusEnum,
    GenderEnum,
    HazardTeam,
    RarityEnum,
    RelationshipTypeEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.game_config import VaultStartConfig, game_config
from app.core.game_data import get_static_game_data
from app.core.grid_config import FLOOR_UNITS, SHAFT_X
from app.crud.broadcast import create_broadcast
from app.crud.item_base import get_items_by_vault
from app.crud.objective import objective_crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.pet import Pet
from app.models.room import Room
from app.models.storage import Storage
from app.models.team import ACTIVE_STATUS
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride, DwellerVisualAttributes
from app.schemas.room import RoomCreate
from app.schemas.vault import (
    MedicalTransferResponse,
    PrimaryResourceAmounts,
    ResourceProduction,
    ResourceTickEvents,
    VaultNumber,
    VaultUpdate,
)
from app.services import broadcast_service
from app.services.catalog_service import load_outfits, load_weapons
from app.services.dweller_service import dweller_service
from app.services.family.lineage_service import lineage_service
from app.services.vault import economy, seeding
from app.services.vault.seed_types import BOOSTED_EQUIPPED_PETS, BOOSTED_SEED_JUNK, BOOSTED_SEED_PETS
from app.services.vault_service import VaultService, vault_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import (
    AccessDeniedException,
    ResourceConflictException,
    ResourceNotFoundException,
    VaultOperationException,
)
from app.utils.room_assets import get_room_image_url
from app.utils.seed_objectives import seed_objectives_from_json
from app.utils.static_data import game_data_store

# Valid UUIDv4 constants for use in mocked objects
VAULT_ID = UUID("12345678-1234-4abc-9def-1234567890ab")
VAULT_ID_B = UUID("87654321-4321-4def-9abc-2109876543ba")
DWELLER_ID = UUID("32345678-1234-4abc-9def-3234567890ab")
STORAGE_ID = UUID("72345678-1234-4abc-9def-7234567890ab")


def _layout_issues(rooms: list[RoomCreate]) -> tuple[int, int, bool]:
    """Count overlaps and floating rooms, and check the floor width, on the unit grid."""
    spans = [(room.coordinate_y, room.coordinate_x, room.coordinate_x + room.size - 1) for room in rooms]
    overlaps = 0
    floating = 0
    for level_y in {span[0] for span in spans}:
        level = sorted((span for span in spans if span[0] == level_y), key=itemgetter(1))
        for index, (_, start, end) in enumerate(level):
            overlaps += int(index + 1 < len(level) and level[index + 1][1] <= end)
            touches = (index > 0 and level[index - 1][2] + 1 == start) or (
                index + 1 < len(level) and level[index + 1][1] == end + 1
            )
            floating += int(not touches)
    return overlaps, floating, all(end < FLOOR_UNITS for _, _, end in spans)


def _room_id(idx: int) -> str:
    return f"{idx:08x}-1234-4abc-9def-{idx:012x}"


def _dweller_id(idx: int) -> str:
    return f"{idx:08x}-5678-4abc-9def-{idx:012x}"


def _make_room(
    name: str = "Test Room",
    category: RoomTypeEnum = RoomTypeEnum.PRODUCTION,
    ability: SPECIALEnum | None = None,
    capacity: int | None = None,
    output: int | None = None,
    tier: int = 1,
    size: int | None = None,
    room_id: str | None = None,
) -> Room:
    return Room(
        id=room_id or _room_id(abs(hash(name)) % 1000000),
        name=name,
        category=category,
        ability=ability,
        capacity=capacity,
        output=output,
        tier=tier,
        size=size or 1,
        size_min=1,
        size_max=3,
        base_cost=100,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
    )


def _make_storage(vault_id: str | None = None, stimpack: int = 10, radaway: int = 5, max_space: int = 100) -> Storage:
    return Storage(
        id=STORAGE_ID,
        vault_id=vault_id or str(VAULT_ID),
        stimpack=stimpack,
        radaway=radaway,
        max_space=max_space,
    )


def _vault(vault_id: UUID = VAULT_ID) -> Vault:
    return Vault(id=vault_id, number=1)


def _dweller(
    dweller_id: UUID = DWELLER_ID, *, vault_id: UUID = VAULT_ID, first_name: str = "Test", **overrides
) -> Dweller:
    return Dweller(
        id=dweller_id,
        first_name=first_name,
        last_name="Dweller",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        vault_id=vault_id,
        level=1,
        **overrides,
    )


def _transfer_db(storage: Storage | None, *, commit: AsyncMock | None = None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = storage
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = commit if commit is not None else AsyncMock()
    db.rollback = AsyncMock()
    return db


@contextmanager
def _transfer_patches(dweller: Dweller | None, *, update_error: Exception | None = None):
    with (
        patch("app.services.vault.economy.dweller_crud.get", new_callable=AsyncMock, return_value=dweller),
        _ap("app.services.vault.economy.dweller_crud.update", side_effect=update_error),
    ):
        yield


def _ap(target: str, **kwargs):
    return patch(target, new_callable=AsyncMock, **kwargs)


def _training_room() -> Room:
    return _make_room(name="Weight Room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH, tier=1)


def _legendary_dwellers(count: int = 4) -> list[Dweller]:
    return [
        Dweller(
            id=_dweller_id(i),
            first_name=f"Legend{i}",
            last_name="Test",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.LEGENDARY,
            level=1,
        )
        for i in range(1, count + 1)
    ]


def _boosted_legendary_templates() -> list:
    ids = ("old-longfellow", "preston-garvey", "betty", "cooper-howard")
    return [game_data_store.get_dweller(template_id) for template_id in ids]


def _seeded_room(vault_id, name: str, category: RoomTypeEnum, ability, x: int, y: int) -> RoomCreate:
    return RoomCreate(
        vault_id=vault_id,
        name=name,
        category=category,
        ability=ability,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        capacity=8 if category == RoomTypeEnum.CAPACITY else None,
        size_min=3,
        size_max=3,
        size=3,
        coordinate_x=x,
        coordinate_y=y,
    )


async def _rooms(db_session, vault_id, *specs) -> list[Room]:
    return [await crud.room.create(db_session, _seeded_room(vault_id, *spec)) for spec in specs]


def _family_texts(dweller: Dweller) -> list[str]:
    return [entry.get("text", "") for entry in dweller.bio_entries or [] if entry.get("source") == "family"]


class TestCreateInitialDwellers:
    async def test_boosted_dwellers_assigned(self) -> None:
        prod_rooms = [
            _make_room(name=name, ability=ability)
            for name, ability in (
                ("Power Gen", SPECIALEnum.STRENGTH),
                ("Diner", SPECIALEnum.AGILITY),
                ("Water Treatment", SPECIALEnum.PERCEPTION),
                ("Medbay", SPECIALEnum.INTELLIGENCE),
                ("Science Lab", SPECIALEnum.INTELLIGENCE),
                ("Power Gen 2", SPECIALEnum.STRENGTH),
            )
        ]
        cap_rooms = [_make_room(name="Living Room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA)]
        misc_rooms = [_make_room(name="Radio Studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA)]
        training_rooms = [
            _make_room(name=name, category=RoomTypeEnum.TRAINING, ability=ability)
            for name, ability in (
                ("Weight Room", SPECIALEnum.STRENGTH),
                ("Armory", SPECIALEnum.PERCEPTION),
                ("Athletics Room", SPECIALEnum.ENDURANCE),
                ("Classroom", SPECIALEnum.CHARISMA),
                ("Game Room", SPECIALEnum.INTELLIGENCE),
                ("Fitness Room", SPECIALEnum.AGILITY),
                ("Lounge", SPECIALEnum.LUCK),
            )
        ]
        call_count = 0

        async def fake_create_random(db_session, vault_id, dweller_data, **kwargs):
            nonlocal call_count
            call_count += 1
            return Dweller(
                id=_dweller_id(call_count),
                first_name=f"Boosted{call_count}",
                last_name="Test",
                gender=GenderEnum.MALE,
                rarity=RarityEnum.COMMON,
                level=1,
            )

        with (
            _ap("app.services.dweller_service.dweller_service.create_random_dweller", side_effect=fake_create_random),
            _ap("app.services.vault.seeding.dweller_crud.update"),
            _ap("app.services.vault.seeding.equip_boosted_worker_outfit"),
            _ap("app.services.vault.seeding.relationship_crud.create_with_defaults"),
            _ap("app.services.bio_service.bio_service.append_entry"),
        ):
            db_session = AsyncMock()
            db_session.add_all = MagicMock()
            await seeding.create_initial_dwellers(
                db_session, VAULT_ID, prod_rooms, training_rooms, misc_rooms, cap_rooms, is_boosted=True
            )
        # 16 production (2 in each apprentice room, 3 elsewhere incl. the second
        # generator) + 7 training + 1 radio + 2 living + 3 family children = 29
        assert call_count == 29

    async def test_boosted_vault_stations_a_fire_and_a_radiation_responder(self, async_session, vault) -> None:
        station = await crud.room.create(
            async_session,
            RoomCreate(
                vault_id=vault.id,
                name="Response Station",
                category=RoomTypeEnum.RESPONSE,
                ability=SPECIALEnum.ENDURANCE,
                population_required=15,
                base_cost=600,
                t2_upgrade_cost=None,
                t3_upgrade_cost=None,
                size_min=3,
                size_max=9,
                size=3,
                coordinate_x=13,
                coordinate_y=3,
            ),
        )
        await seeding.seed_boosted_response_team(async_session, vault.id, station)
        fire = await crud.team_crud.get_hazard_team(async_session, vault.id, HazardTeam.FIRE)
        radiation = await crud.team_crud.get_hazard_team(async_session, vault.id, HazardTeam.RADIATION)
        assert [member.status for member in fire] == [ACTIVE_STATUS]
        assert [member.status for member in radiation] == [ACTIVE_STATUS]
        assert fire[0].dweller_id != radiation[0].dweller_id
        assert {fire[0].dweller.room_id, radiation[0].dweller.room_id} == {station.id}

    async def test_dweller_creation_failure_logs_and_raises(self) -> None:
        prod_rooms = [
            _make_room(name=name, ability=ability)
            for name, ability in (
                ("Power Gen", SPECIALEnum.STRENGTH),
                ("Diner", SPECIALEnum.AGILITY),
                ("Water Treatment", SPECIALEnum.PERCEPTION),
            )
        ]
        with (
            _ap(
                "app.services.dweller_service.dweller_service.create_random_dweller",
                side_effect=RuntimeError("DB error"),
            ),
            pytest.raises(RuntimeError, match="DB error"),
        ):
            await seeding.create_initial_dwellers(AsyncMock(), VAULT_ID, prod_rooms, [], [], [], is_boosted=False)


class TestStartTrainingSessions:
    @pytest.mark.parametrize(
        "error",
        [
            None,
            ResourceNotFoundException(Dweller, "test-id"),
            VaultOperationException(detail="This dweller's state prevents purposeful training."),
        ],
        ids=["ok", "not-found", "state-rejected"],
    )
    async def test_domain_failures_are_logged_not_raised(self, error: Exception | None) -> None:
        room = _training_room()
        dweller = _dweller(
            first_name="Train",
            room_id=room.id,
            strength=5,
            perception=3,
            endurance=4,
            charisma=3,
            intelligence=3,
            agility=3,
            luck=3,
        )
        db_session = AsyncMock()
        db_session.refresh = AsyncMock()
        with (
            patch(
                "app.services.vault.seeding.dweller_crud.get_multi_by_vault",
                new_callable=AsyncMock,
                return_value=[dweller],
            ),
            _ap("app.services.vault.seeding.training_service.start_training", side_effect=error),
        ):
            await seeding.start_training_sessions(db_session, VAULT_ID, [room], is_boosted=True)

    async def test_training_sessions_outer_exception_raises(self) -> None:
        room = _training_room()
        db_session = AsyncMock()
        db_session.refresh = AsyncMock()
        with (
            _ap("app.services.vault.seeding.dweller_crud.get_multi_by_vault", side_effect=RuntimeError("DB down")),
            pytest.raises(RuntimeError, match="DB down"),
        ):
            await seeding.start_training_sessions(db_session, VAULT_ID, [room], is_boosted=True)


class TestCreateInitialItems:
    async def test_noop_when_no_storage(self) -> None:
        db_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=result)
        await seeding.create_initial_items(db_session, VAULT_ID)
        db_session.add.assert_not_called()

    async def test_boosted_vault_seeds_hazard_outfits_pets_and_junk(self, async_session, vault) -> None:
        storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
        first = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(
                **(create_fake_adult_dweller() | {"rarity": RarityEnum.LEGENDARY, "first_name": "Alpha"}),
                vault_id=vault.id,
            ),
        )
        second = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(
                **(create_fake_adult_dweller() | {"rarity": RarityEnum.LEGENDARY, "first_name": "Beta"}),
                vault_id=vault.id,
            ),
        )
        await seeding.create_initial_items(async_session, vault.id, is_boosted=True)
        outfits = await get_items_by_vault(async_session, Outfit, vault.id)
        firefighter = [o for o in outfits if o.name == "Firefighter suit"]
        hazmat = [o for o in outfits if o.name == "Hazmat suit"]
        assert len(firefighter) == 3
        assert len(hazmat) == 3
        assert all(o.fire_resist == 0.5 and o.radiation_resist == 0.0 and o.endurance == 4 for o in firefighter)
        assert all(o.radiation_resist == 1.0 and o.endurance == 2 and o.intelligence == 2 for o in hazmat)
        assert all(o.storage_id == storage.id for o in firefighter + hazmat)
        pets = {pet.name: pet for pet in await get_items_by_vault(async_session, Pet, vault.id)}
        assert set(pets) == {name for name, _ in BOOSTED_SEED_PETS}
        assert all(pet.image_url for pet in pets.values())
        assert all(
            pet.storage_id == storage.id and pet.dweller_id is None
            for name, pet in pets.items()
            if name not in BOOSTED_EQUIPPED_PETS
        )
        assert pets[BOOSTED_EQUIPPED_PETS[0]].dweller_id == first.id
        assert pets[BOOSTED_EQUIPPED_PETS[1]].dweller_id == second.id
        junk = list((await async_session.execute(select(Junk).where(Junk.storage_id == storage.id))).scalars().all())
        assert len(junk) == sum(count for _, _, count in BOOSTED_SEED_JUNK)
        assert {j.junk_type for j in junk} == {junk_type for junk_type, _, _ in BOOSTED_SEED_JUNK}
        assert all(j.storage_id == storage.id for j in junk)
        assert all(j.description and j.value for j in junk)

    async def test_standard_vault_seeds_only_standard_outfits(self, async_session, vault) -> None:
        await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
        await seeding.create_initial_items(async_session, vault.id, is_boosted=False)
        outfits = await get_items_by_vault(async_session, Outfit, vault.id)
        assert not any(o.name in {"Firefighter suit", "Hazmat suit"} for o in outfits)
        assert await get_items_by_vault(async_session, Pet, vault.id) == []
        by_name = {o.name: o for o in outfits}
        t51b = by_name["T-51b Power Armor"]
        assert (t51b.strength, t51b.perception, t51b.endurance) == (3, 1, 2)
        jumpsuit = by_name["Vault Jumpsuit"]
        assert (jumpsuit.charisma, jumpsuit.luck) == (1, 1)


class TestCreateBoostedLegendaryDwellers:
    async def test_random_legendary_roster_uses_catalog_equipment(self) -> None:
        templates = _boosted_legendary_templates()
        dwellers = _legendary_dwellers()
        weapon_names = {entry["name"] for entry in load_weapons()}
        outfit_names = {entry["name"] for entry in load_outfits()}
        with (
            patch("app.services.vault.seeding.random.sample", return_value=templates) as mock_sample,
            _ap("app.services.dweller_service.dweller_service.create_dweller_from_template", side_effect=dwellers),
            _ap("app.services.vault.seeding.weapon_crud.create_many") as mock_weapons,
            _ap("app.services.vault.seeding.outfit_crud.create_many") as mock_outfits,
        ):
            await seeding.create_boosted_legendary_dwellers(AsyncMock(), VAULT_ID)
        mock_sample.assert_called_once()
        assert mock_sample.call_args.kwargs["k"] == 3
        candidates = mock_sample.call_args.args[0]
        assert len(candidates) >= 3
        # Every candidate's equipment must resolve through the case-sensitive item factory.
        assert all(template.weapon in weapon_names and template.outfit in outfit_names for template in candidates)
        expected_outfits = {template.outfit: dwellers[i].id for i, template in enumerate(templates)}
        expected_weapons = {template.weapon: dwellers[i].id for i, template in enumerate(templates)}
        outfits = {item.name: item for item in mock_outfits.call_args.args[1]}
        weapons = {item.name: item for item in mock_weapons.call_args.args[1]}
        assert {name: item.dweller_id for name, item in outfits.items()} == expected_outfits
        assert {name: item.dweller_id for name, item in weapons.items()} == expected_weapons
        assert all(item.rarity == RarityEnum.LEGENDARY for item in (*outfits.values(), *weapons.values()))
        assert all(item.image_url for item in (*outfits.values(), *weapons.values()))

    async def test_legendary_roster_persists_with_catalog_special(self, async_session, vault, dweller_data) -> None:
        templates = _boosted_legendary_templates()
        dwellers = [
            await crud.dweller.create(
                db_session=async_session,
                obj_in=DwellerCreate(**(dict(dweller_data, first_name=f"Legend{i}")), vault_id=vault.id),
            )
            for i in range(1, 5)
        ]
        with (
            patch("app.services.vault.seeding.random.sample", return_value=templates),
            _ap("app.services.dweller_service.dweller_service.create_dweller_from_template", side_effect=dwellers),
        ):
            await seeding.create_boosted_legendary_dwellers(async_session, vault.id)
        outfits = await get_items_by_vault(async_session, Outfit, vault.id)
        weapons = await get_items_by_vault(async_session, Weapon, vault.id)
        assert {item.name for item in outfits} == {template.outfit for template in templates}
        assert {item.name for item in weapons} == {template.weapon for template in templates}
        assert all(item.rarity == RarityEnum.LEGENDARY and item.dweller_id is not None for item in outfits + weapons)

    async def test_roster_excludes_templates_with_missing_catalog_equipment(self) -> None:
        templates = _boosted_legendary_templates()
        catalog = [entry for entry in load_outfits() if entry["name"] != "Vault 33 suit"]
        dwellers = _legendary_dwellers()
        with (
            patch("app.services.catalog_service.load_outfits", return_value=catalog),
            patch(
                "app.services.vault.seeding.random.sample", side_effect=lambda population, k: population[:k]
            ) as sample,
            _ap("app.services.dweller_service.dweller_service.create_dweller_from_template", side_effect=dwellers),
            _ap("app.services.vault.seeding.weapon_crud.create_many"),
            _ap("app.services.vault.seeding.outfit_crud.create_many") as mock_outfits,
        ):
            await seeding.create_boosted_legendary_dwellers(AsyncMock(), VAULT_ID)
        assert all(template.template_id != "betty" for template in sample.call_args.args[0])
        assert len(mock_outfits.call_args.args[1]) == 3
        assert all(item.name != "Vault 33 suit" for item in mock_outfits.call_args.args[1])


# Objective assignment is delegated to objective_crud.assign_initial (CRUD layer).
# Behavior is covered by test_crud/test_objective.py::test_assign_initial_objectives
# and the delegation assertion in TestInitiateVault below.


@pytest.mark.parametrize(
    ("state_of_being", "rejected"), [("gen_3", False), ("gen_1", True)], ids=["gen-3-synth", "visible-synth"]
)
async def test_radaway_transfer_depends_on_synth_visibility(
    async_session, vault: Vault, dweller: Dweller, state_of_being: str, rejected: bool
) -> None:
    dweller.visual_attributes = {"race": "synth", "state_of_being": state_of_being}
    # dweller_data randomizes radaway up to the 15 cap; start below it so the transfer is deterministic.
    dweller.radaway = 0
    before = dweller.radaway
    async_session.add_all([dweller, Storage(vault_id=vault.id, stimpack=5, radaway=5)])
    await async_session.commit()

    if rejected:
        with pytest.raises(ResourceConflictException, match="cannot carry RadAway"):
            await VaultService().transfer_medical_supplies(async_session, vault, dweller.id, stimpaks=0, radaways=1)
    else:
        response = await VaultService().transfer_medical_supplies(
            async_session, vault, dweller.id, stimpaks=0, radaways=1
        )
        assert response.dweller_radaways == before + 1


_TRANSFER_REJECTIONS = (
    (None, {}, {"stimpaks": 1, "radaways": 0}, ResourceNotFoundException, None),
    ((10, 2), {}, {"stimpaks": 0, "radaways": 5}, ResourceConflictException, "only has 2 radaways"),
    ((10, 10), {"vault_id": VAULT_ID_B}, {"stimpaks": 1, "radaways": 0}, AccessDeniedException, None),
    (
        (20, 20),
        {"stimpack": 14},
        {"stimpaks": 2, "radaways": 0},
        ResourceConflictException,
        "can only carry 15 stimpaks",
    ),
    (
        (20, 20),
        {"radaway": 13},
        {"stimpaks": 0, "radaways": 3},
        ResourceConflictException,
        "can only carry 15 radaways",
    ),
)


class TestTransferMedicalSupplies:
    @pytest.mark.parametrize(
        ("storage_counts", "dweller_fields", "payload", "error", "match"),
        _TRANSFER_REJECTIONS,
        ids=["no-storage", "insufficient-radaways", "vault-mismatch", "stimpack-cap", "radaway-cap"],
    )
    async def test_transfer_rejections(
        self, storage_counts: tuple[int, int] | None, dweller_fields: dict, payload: dict, error, match
    ) -> None:
        storage = _make_storage(stimpack=storage_counts[0], radaway=storage_counts[1]) if storage_counts else None
        dweller = _dweller(**dweller_fields) if dweller_fields else None
        with _transfer_patches(dweller), pytest.raises(error, match=match):
            await VaultService().transfer_medical_supplies(_transfer_db(storage), _vault(), DWELLER_ID, **payload)

    @pytest.mark.parametrize(
        ("commit_error", "update_error", "expected"),
        [
            (None, None, (17, 18, 8, 5)),
            (RuntimeError("Commit failed"), None, "Commit failed"),
            (None, RuntimeError("Dweller update failed"), "Dweller update failed"),
        ],
        ids=["success", "commit-failure", "staging-failure"],
    )
    async def test_transfer_outcomes(self, commit_error, update_error, expected) -> None:
        dweller = _dweller(stimpack=5, radaway=3)
        db_session = _transfer_db(_make_storage(stimpack=20, radaway=20), commit=AsyncMock(side_effect=commit_error))
        if isinstance(expected, tuple):
            with _transfer_patches(dweller):
                result = await VaultService().transfer_medical_supplies(
                    db_session, _vault(), DWELLER_ID, stimpaks=3, radaways=2
                )
            assert isinstance(result, MedicalTransferResponse)
            transfers = (result.vault_stimpaks, result.vault_radaways, result.dweller_stimpaks, result.dweller_radaways)
            assert transfers == expected
        else:
            with (
                _transfer_patches(dweller, update_error=update_error),
                pytest.raises(RuntimeError, match=expected),
            ):
                await VaultService().transfer_medical_supplies(db_session, _vault(), DWELLER_ID, stimpaks=1, radaways=0)
            db_session.rollback.assert_awaited_once()

    async def test_transfer_success_with_nulls(self) -> None:
        storage = Storage(
            id="s",
            vault_id=str(VAULT_ID),
            stimpack=None,  # type: ignore[arg-type]
            radaway=None,  # type: ignore[arg-type]
            max_space=100,
        )
        dweller = _dweller(first_name="Null", stimpack=0, radaway=0)
        db_session = _transfer_db(storage)
        with _transfer_patches(dweller), pytest.raises(ResourceConflictException):
            # With 0 in vault, any positive request raises
            await VaultService().transfer_medical_supplies(db_session, _vault(), DWELLER_ID, stimpaks=1, radaways=0)


class TestUpdateVaultResources:
    async def test_updates_resources_and_emits_events(self) -> None:
        new_resources = VaultUpdate(power=80, food=60, water=50)
        events = ResourceTickEvents(
            production=ResourceProduction(power=10, food=5), consumption=PrimaryResourceAmounts(food=1, water=1)
        )
        manager = MagicMock()
        manager.process_vault_resources = AsyncMock(return_value=(new_resources, events))
        manager.emit_production_events = AsyncMock()
        db_session = AsyncMock()
        with (
            patch("app.services.vault.economy.resource_manager", manager),
            _ap("app.services.vault.economy.vault_crud.update") as mock_vault_update,
        ):
            returned_vault = Vault(id=VAULT_ID, number=1, power=80, food=60, water=50)
            mock_vault_update.return_value = returned_vault
            result = await economy.update_vault_resources(db_session, VAULT_ID)
        manager.process_vault_resources.assert_awaited_once_with(
            db_session=db_session, vault_id=VAULT_ID, seconds_passed=60
        )
        manager.emit_production_events.assert_awaited_once_with(VAULT_ID, events)
        mock_vault_update.assert_awaited_once()
        assert result == returned_vault


class TestInitiateVault:
    @pytest.fixture
    async def boosted_seed(self, async_session, vault) -> SimpleNamespace:
        game_data = await get_static_game_data()
        prepared = seeding.prepare_initial_rooms(game_data.rooms, vault.id, is_boosted=True)
        await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
        base_power_max = vault.power_max
        vault_obj, created = await seeding.create_initial_rooms(async_session, vault, prepared)
        await seeding.create_initial_dwellers(
            async_session,
            vault.id,
            created.production,
            created.training,
            created.misc,
            created.capacity,
            is_boosted=True,
            created_crafting_rooms=created.crafting,
        )
        await async_session.commit()
        dwellers = await crud.dweller.get_multi_by_vault(async_session, vault.id)
        return SimpleNamespace(
            vault=vault,
            vault_obj=vault_obj,
            created=created,
            dwellers=dwellers,
            base_power_max=base_power_max,
            session=async_session,
        )

    async def test_prepared_initial_rooms_fit_the_unit_grid(self) -> None:
        game_data = await get_static_game_data()
        vault_id = uuid4()
        for is_boosted in (False, True):
            prepared = seeding.prepare_initial_rooms(game_data.rooms, vault_id, is_boosted)
            rooms = [
                *prepared.infrastructure,
                *prepared.capacity,
                *prepared.production,
                *prepared.misc,
                *prepared.training,
                *prepared.arena,
                *prepared.crafting,
            ]
            assert _layout_issues(rooms) == (0, 0, True)
            for level in {room.coordinate_y for room in rooms}:
                occupied = {
                    x
                    for room in rooms
                    if room.coordinate_y == level
                    for x in range(room.coordinate_x, room.coordinate_x + room.size)
                }
                assert occupied == set(range(min(occupied), max(occupied) + 1)), (is_boosted, level)
            assert len(prepared.crafting) == (2 if is_boosted else 0)
            if is_boosted:
                assert {room.name for room in prepared.crafting} == {"Weapon workshop", "Outfit workshop"}
            merged_living = [room for room in prepared.capacity if room.name == "Living room" and room.size == 9]
            assert len(merged_living) == (1 if is_boosted else 0)
            generators = [room for room in rooms if room.name.lower().startswith("power")]
            assert len(generators) == 1
            if is_boosted:
                assert (generators[0].coordinate_x, generators[0].coordinate_y) == (0, 1)
                assert generators[0].size == 6
            elevators = sorted(
                (room.coordinate_x, room.coordinate_y) for room in rooms if room.name.lower() == "elevator"
            )
            assert elevators == [(SHAFT_X, level) for level in range(5 if is_boosted else 4)]

    async def test_standard_seed_shape_and_living_row_layouts(self) -> None:
        game_data = await get_static_game_data()
        standard = seeding.prepare_initial_rooms(game_data.rooms, uuid4(), is_boosted=False)
        boosted = seeding.prepare_initial_rooms(game_data.rooms, uuid4(), is_boosted=True)
        scenario = seeding.prepare_initial_rooms(game_data.rooms, uuid4(), is_boosted=False, scenario_start=True)
        assert [room.name for room in standard.misc if "radio" in room.name.lower()] == []
        assert [room.name for room in boosted.misc if "radio" in room.name.lower()] == ["Radio studio"]

        def housing(prepared) -> list:
            return sorted(
                (room for room in prepared.capacity if room.name == "Living room" and room.coordinate_y == 3),
                key=lambda room: room.coordinate_x,
            )

        living = housing(standard)
        assert [(room.coordinate_x, room.size) for room in living] == [(7, 3), (10, 3)]
        assert living[0].coordinate_x + living[0].size == living[1].coordinate_x
        scenario_living = housing(scenario)
        assert [(room.coordinate_x, room.size) for room in scenario_living] == [(7, 3), (10, 3), (13, 3)]
        for left, right in pairwise(scenario_living):
            assert left.coordinate_x + left.size == right.coordinate_x

    async def test_boosted_seed_layout_rooms_and_outfits(self, boosted_seed: SimpleNamespace) -> None:
        seed = boosted_seed
        rooms = await crud.room.get_all_by_vault(seed.session, seed.vault.id)
        housing_floor = sorted((room for room in rooms if room.coordinate_y == 3), key=lambda room: room.coordinate_x)
        for left, right in pairwise(housing_floor):
            assert left.coordinate_x + left.size == right.coordinate_x
        living_rooms = [room for room in housing_floor if room.name == "Living room"]
        assert sorted(room.size for room in living_rooms) == [3, 3, 9]
        assert sorted(room.capacity for room in living_rooms) == [8, 8, 28]
        fused_capacity = 25 * 6 * (2 + 1)  # capacity_formula 25*S*(L+1) at size 6, tier 2
        power_rooms = [room for room in seed.created.production if room.name.lower().startswith("power")]
        assert len(power_rooms) == 1  # seeded directly at (0, 1), no fusion round-trip
        assert power_rooms[0].size == 6
        assert power_rooms[0].output == 70  # (2*6*(2+4))-2 at tier 2, size 6
        assert power_rooms[0].image_url == get_room_image_url("Power Generator", tier=2, size=6)
        assert seed.vault_obj.power_max == seed.base_power_max + fused_capacity
        persisted = [room for room in rooms if room.name.lower().startswith("power")]
        assert len(persisted) == 1
        generator_crew = [dweller for dweller in seed.dwellers if dweller.room_id == power_rooms[0].id]
        assert len([d for d in generator_crew if d.apprentice_stat is None]) == 5  # double crew minus apprentice slot
        assert len(generator_crew) == 6  # five adults plus the seeded family teen
        assert all(dweller.status == DwellerStatusEnum.WORKING for dweller in generator_crew)
        assert [d for d in generator_crew if d.apprentice_stat == SPECIALEnum.STRENGTH]  # the seeded family teen
        assert len(seed.dwellers) == 35  # non-legendary headcount (35 + 3 legendary = 38)
        ability_by_room = {room.id: room.ability for room in seed.created.production if room.ability is not None}
        outfitted = [
            d
            for d in seed.dwellers
            if d.room_id in ability_by_room and d.apprentice_stat is None and d.status == DwellerStatusEnum.WORKING
        ]
        assert len(outfitted) == 16  # 5 generator + 2 diner + 3 water + 3 medbay + 3 science
        for dweller in outfitted:
            ability = ability_by_room[dweller.room_id]
            outfit = await crud.outfit.get_equipped(seed.session, dweller.id)
            assert outfit is not None
            assert outfit.rarity == RarityEnum.COMMON
            assert getattr(outfit, ability.value.lower()) == 3

    @pytest.mark.parametrize("is_boosted", [True, False], ids=["boosted", "standard"])
    async def test_initiate_vault_start_resources(self, async_session, superuser, is_boosted: bool) -> None:
        """Starts preserve caps budgets and one active stage per achievement family."""
        await seed_objectives_from_json(async_session)
        result = await VaultService().initiate_vault(
            async_session,
            VaultNumber(number=random_vault_number(), boosted=is_boosted),
            superuser.id,
            is_boosted=is_boosted,
        )
        arena = next(room for room in (await get_static_game_data()).rooms if room.name.lower() == "arena")
        if is_boosted:
            # Boosted starts cover the Arena through T2; T3 is a later sink.
            assert result.bottle_caps >= arena.base_cost + arena.t2_upgrade_cost
        else:
            assert result.bottle_caps == 1_000
        objectives = await objective_crud.get_multi_for_vault(async_session, result.id)
        assert {"daily", "weekly", "achievement"} <= {o.category for o in objectives}
        achievements = [o for o in objectives if o.category == "achievement"]
        assert all(o.sequence == 1 for o in achievements if o.objective_type != "reach")
        unclaimed = [o for o in achievements if not o.is_completed]
        assert {o.track_key for o in achievements} == {o.track_key for o in unclaimed}
        assert len({o.track_key for o in unclaimed}) == len(unclaimed)
        state = await crud.game_state_crud.get_or_create(async_session, result.id)
        assert state.achievement_tracks_initialized
        assert state.daily_objectives_period is not None


class TestVaultStartConfig:
    def test_defaults_and_bounds(self) -> None:
        cfg = VaultStartConfig()
        assert cfg.initial_resource_pct == 0.5
        assert cfg.initial_stimpaks == 5
        assert cfg.initial_radaways == 5
        assert cfg.standard_rare_chance == 0.04
        assert cfg.boosted_rare_chance == 0.12
        with pytest.raises(ValidationError):
            VaultStartConfig(initial_resource_pct=1.5)
        with pytest.raises(ValidationError):
            VaultStartConfig(initial_stimpaks=-1)

    def test_loads_vault_start_values_from_dotenv(self, monkeypatch, tmp_path) -> None:
        (tmp_path / ".env").write_text("VAULT_START_INITIAL_RESOURCE_PCT=0.8\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("VAULT_START_INITIAL_RESOURCE_PCT", raising=False)
        assert VaultStartConfig().initial_resource_pct == 0.8


class TestSeededFamilies:
    @pytest.mark.parametrize(("mother_race", "family_event"), [("ghoul", "Adopted"), ("human", "was born")])
    async def test_seeded_family_story_matches_conception(
        self, async_session, vault, mother_race, family_event
    ) -> None:
        mother = await dweller_service.create_random_dweller(
            async_session,
            vault.id,
            DwellerCreateCommonOverride(
                gender=GenderEnum.FEMALE, visual_attributes=DwellerVisualAttributes(race=mother_race)
            ),
        )
        father = await dweller_service.create_random_dweller(
            async_session,
            vault.id,
            DwellerCreateCommonOverride(
                gender=GenderEnum.MALE, visual_attributes=DwellerVisualAttributes(race="human")
            ),
        )
        mother.age_group = father.age_group = AgeGroupEnum.ADULT
        async_session.add_all([mother, father])
        await async_session.commit()
        await seeding.seed_seeded_families(async_session, vault.id, [], [mother, father], [], is_boosted=False)
        children = await crud.dweller.get_children_of(async_session, vault_id=vault.id, parent_ids=[mother.id])
        assert len(children) == 1
        child = children[0]
        assert {child.parent_1_id, child.parent_2_id} == {mother.id, father.id}
        assert ("adopted" in child.bio.lower()) is (mother_race == "ghoul")
        for parent in (mother, father):
            updated = await crud.dweller.get(async_session, parent.id)
            assert any(family_event in text for text in _family_texts(updated))

    async def test_standard_vault_seeds_one_committed_family(self, async_session, vault) -> None:
        prod_rooms = await _rooms(
            async_session,
            vault.id,
            ("Power Generator", RoomTypeEnum.PRODUCTION, SPECIALEnum.STRENGTH, 3, 1),
            ("Diner", RoomTypeEnum.PRODUCTION, SPECIALEnum.AGILITY, 6, 1),
            ("Water Treatment", RoomTypeEnum.PRODUCTION, SPECIALEnum.PERCEPTION, 9, 1),
        )
        living_rooms = await _rooms(
            async_session, vault.id, ("Living Room", RoomTypeEnum.CAPACITY, SPECIALEnum.CHARISMA, 12, 1)
        )
        await seeding.create_initial_dwellers(
            async_session, vault.id, prod_rooms, [], [], living_rooms, is_boosted=False
        )
        # 6 production workers + 2 living dwellers + 1 family child.
        dwellers = await crud.dweller.get_multi_by_vault(async_session, vault.id)
        assert len(dwellers) == 9
        relationships = await relationship_crud.get_by_vault(async_session, vault.id)
        assert len(relationships) == 1
        rel = relationships[0]
        assert rel.relationship_type == RelationshipTypeEnum.MARRIED
        assert rel.affinity == 95
        first = await crud.dweller.get(async_session, rel.dweller_1_id)
        second = await crud.dweller.get(async_session, rel.dweller_2_id)
        assert first.partner_id == second.id
        assert second.partner_id == first.id
        children = [d for d in dwellers if d.parent_1_id is not None]
        assert len(children) == 1
        child = children[0]
        assert {child.parent_1_id, child.parent_2_id} == {first.id, second.id}
        assert child.age_group == AgeGroupEnum.TEEN
        assert child.room_id in {first.room_id, second.room_id}
        assert child.room_id in {r.id for r in prod_rooms}
        parent_room = next(r for r in prod_rooms if r.id == child.room_id)
        assert child.apprentice_stat == parent_room.ability
        assert child.apprentice_started_at is not None
        assert child.status == DwellerStatusEnum.WORKING
        lineage = await lineage_service.get_lineage(async_session, child.id)
        assert {p.id for p in lineage.parents} == {first.id, second.id}
        partner_lineage = await lineage_service.get_lineage(async_session, first.id)
        assert [p.id for p in partner_lineage.partners] == [second.id]
        assert [c.id for c in partner_lineage.children] == [child.id]
        assert any(second.first_name in text for text in _family_texts(first))
        assert any(first.first_name in text for text in _family_texts(second))
        assert any(child.first_name in text for text in _family_texts(first))
        assert any(child.first_name in text for text in _family_texts(second))
        origin_refs = [entry.get("ref") or {} for entry in child.bio_entries or [] if entry.get("source") == "template"]
        assert any(
            {ref.get("mother_id") or ref.get("parent_1_id"), ref.get("father_id") or ref.get("parent_2_id")}
            == {str(first.id), str(second.id)}
            for ref in origin_refs
        )

    async def test_boosted_vault_seeds_three_families_in_distinct_rooms(self, async_session, vault) -> None:
        prod_rooms = await _rooms(
            async_session,
            vault.id,
            ("Power Generator", RoomTypeEnum.PRODUCTION, SPECIALEnum.STRENGTH, 3, 1),
            ("Diner", RoomTypeEnum.PRODUCTION, SPECIALEnum.AGILITY, 6, 1),
            ("Water Treatment", RoomTypeEnum.PRODUCTION, SPECIALEnum.PERCEPTION, 9, 1),
            ("Medbay", RoomTypeEnum.PRODUCTION, SPECIALEnum.INTELLIGENCE, 12, 1),
            ("Science Lab", RoomTypeEnum.PRODUCTION, SPECIALEnum.INTELLIGENCE, 15, 1),
        )
        misc_rooms = await _rooms(
            async_session, vault.id, ("Radio Studio", RoomTypeEnum.MISC, SPECIALEnum.CHARISMA, 18, 1)
        )
        living_rooms = await _rooms(
            async_session, vault.id, ("Living Room", RoomTypeEnum.CAPACITY, SPECIALEnum.CHARISMA, 21, 1)
        )
        await seeding.create_initial_dwellers(
            async_session, vault.id, prod_rooms, [], misc_rooms, living_rooms, is_boosted=True
        )
        dwellers = await crud.dweller.get_multi_by_vault(async_session, vault.id)
        relationships = await relationship_crud.get_by_vault(async_session, vault.id)
        assert len(relationships) == 3
        assert all(rel.relationship_type == RelationshipTypeEnum.MARRIED for rel in relationships)
        children = [d for d in dwellers if d.parent_1_id is not None]
        assert len(children) == 3
        teens = [d for d in children if d.age_group == AgeGroupEnum.TEEN]
        assert len(teens) == 2
        apprentice_rooms = set()
        for child in teens:
            assert child.age_group == AgeGroupEnum.TEEN
            room = await crud.room.get(async_session, child.room_id)
            assert room.ability is not None
            assert child.apprentice_stat == room.ability
            apprentice_rooms.add(child.room_id)
        assert len(apprentice_rooms) == 2
        assert next(d for d in children if d.age_group == AgeGroupEnum.CHILD).room_id is None
        for room in prod_rooms:
            assert len([d for d in dwellers if d.room_id == room.id]) <= 3
        vault_after = await crud.vault.get(async_session, vault.id)
        assert vault_after.population_max >= len(dwellers)

    async def test_family_child_without_production_room_stays_child(self, async_session, vault) -> None:
        prod_rooms = await _rooms(
            async_session,
            vault.id,
            *[(f"Idle Room {i}", RoomTypeEnum.PRODUCTION, None, x, 1) for i, x in enumerate((3, 6, 9))],
        )
        living_rooms = await _rooms(
            async_session, vault.id, ("Living Room", RoomTypeEnum.CAPACITY, SPECIALEnum.CHARISMA, 12, 1)
        )
        await seeding.create_initial_dwellers(
            async_session, vault.id, prod_rooms, [], [], living_rooms, is_boosted=False
        )
        dwellers = await crud.dweller.get_multi_by_vault(async_session, vault.id)
        children = [d for d in dwellers if d.parent_1_id is not None]
        assert len(children) == 1
        assert children[0].age_group == AgeGroupEnum.CHILD
        assert children[0].apprentice_stat is None
        assert children[0].room_id is None

    async def test_pair_seeded_couple_applies_marriage_bonus(self, async_session, vault) -> None:
        first = await dweller_service.create_random_dweller(
            async_session, vault.id, DwellerCreateCommonOverride(gender=GenderEnum.MALE)
        )
        second = await dweller_service.create_random_dweller(
            async_session, vault.id, DwellerCreateCommonOverride(gender=GenderEnum.FEMALE)
        )
        assert first.happiness == 50
        await seeding.pair_seeded_couple(async_session, first, second)
        bonus = game_config.relationship.partner_happiness_bonus + game_config.relationship.married_happiness_bonus
        for dweller_id in (first.id, second.id):
            dweller = await crud.dweller.get(async_session, dweller_id)
            assert dweller.happiness == min(100, 50 + bonus)
        rel = await relationship_crud.get_by_dweller_pair(async_session, first.id, second.id)
        assert rel is not None
        assert rel.relationship_type == RelationshipTypeEnum.MARRIED


class TestDeleteVault:
    async def test_hard_delete_removes_broadcast_audio(self, async_session, vault):
        await create_broadcast(
            async_session,
            vault_id=vault.id,
            title="Old broadcast",
            script="Old script",
            audio_key="broadcasts/old.mp3",
        )
        await async_session.commit()
        client = MagicMock()
        client.delete_file.return_value = True
        with patch.object(broadcast_service, "get_storage_client", return_value=client):
            await vault_service.delete_vault(async_session, vault.id, soft=False)
        client.delete_file.assert_called_once_with(
            file_name="broadcasts/old.mp3", bucket_name=broadcast_service.BROADCAST_AUDIO_BUCKET
        )
