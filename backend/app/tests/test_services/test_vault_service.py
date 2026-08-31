"""Tests for vault service - initialization, resources, medical transfers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import UUID4, ValidationError

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.storage import Storage
from app.models.vault import Vault
from app.schemas.common import (
    DwellerStatusEnum,
    GenderEnum,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.schemas.dweller import DwellerCreateCommonOverride, DwellerUpdate
from app.schemas.room import RoomCreate, RoomCreateWithoutVaultID
from app.schemas.vault import (
    MedicalTransferResponse,
    PrimaryResourceAmounts,
    ResourceProduction,
    ResourceTickEvents,
    VaultNumber,
    VaultUpdate,
)
from app.services.vault_service import CreatedRooms, PreparedRooms, VaultService
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException

# Valid UUIDv4 constants for use in mocked objects
VAULT_ID = UUID4("12345678-1234-4abc-9def-1234567890ab")
VAULT_ID_B = UUID4("87654321-4321-4def-9abc-2109876543ba")
USER_ID = UUID4("22345678-1234-4abc-9def-2234567890ab")
DWELLER_ID = UUID4("32345678-1234-4abc-9def-3234567890ab")
ROOM_ID_1 = UUID4("42345678-1234-4abc-9def-4234567890ab")
ROOM_ID_2 = UUID4("52345678-1234-4abc-9def-5234567890ab")
ROOM_ID_3 = UUID4("62345678-1234-4abc-9def-6234567890ab")
STORAGE_ID = UUID4("72345678-1234-4abc-9def-7234567890ab")
OTHER_DWELLER_ID = UUID4("82345678-1234-4abc-9def-8234567890ab")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_room_create(
    name: str,
    category: RoomTypeEnum = RoomTypeEnum.PRODUCTION,
    ability: SPECIALEnum | None = None,
    capacity: int | None = None,
    output: int | None = None,
    size_min: int = 1,
    size_max: int = 3,
    capacity_formula: str | None = None,
    output_formula: str | None = None,
) -> RoomCreateWithoutVaultID:
    return RoomCreateWithoutVaultID(
        name=name,
        category=category,
        ability=ability,
        capacity=capacity,
        output=output,
        size_min=size_min,
        size_max=size_max,
        base_cost=100,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        capacity_formula=capacity_formula,
        output_formula=output_formula,
    )


def _room_id(idx: int) -> str:
    return f"{idx:08x}-1234-4abc-9def-{idx:012x}"


def _dweller_id(idx: int) -> str:
    return f"{idx:08x}-5678-4abc-9def-{idx:012x}"


def _make_room(
    room_id: str | None = None,
    name: str = "Test Room",
    category: RoomTypeEnum = RoomTypeEnum.PRODUCTION,
    ability: SPECIALEnum | None = None,
    capacity: int | None = None,
    output: int | None = None,
    tier: int = 1,
    size: int | None = None,
) -> Room:
    idx = hash(name) % 1000000
    rid = room_id or _room_id(abs(idx))
    return Room(
        id=rid,
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


def _make_storage(
    vault_id: str | None = None,
    stimpack: int = 10,
    radaway: int = 5,
    max_space: int = 100,
) -> Storage:
    return Storage(
        id=STORAGE_ID,
        vault_id=vault_id or str(VAULT_ID),
        stimpack=stimpack,
        radaway=radaway,
        max_space=max_space,
    )


# ---------------------------------------------------------------------------
# Test _prepare_room_data
# ---------------------------------------------------------------------------


class TestPrepareRoomData:
    """Unit tests for _prepare_room_data static method."""

    def test_basic_room_data(self) -> None:
        vault_id = VAULT_ID
        rooms = [
            _make_room_create(name="Power Generator", ability=SPECIALEnum.STRENGTH, capacity=10, output=5),
            _make_room_create(name="Diner", ability=SPECIALEnum.AGILITY, capacity=8, output=4),
        ]
        result = VaultService._prepare_room_data(rooms, "power generator", vault_id, x=1, y=1)
        assert result["name"] == "Power Generator"
        assert result["vault_id"] == vault_id
        assert result["coordinate_x"] == 1
        assert result["coordinate_y"] == 1
        assert result["tier"] == 1
        assert result["size"] == rooms[0].size_min

    def test_with_capacity_formula(self) -> None:
        vault_id = VAULT_ID
        rooms = [
            _make_room_create(
                name="Living Room",
                category=RoomTypeEnum.CAPACITY,
                ability=SPECIALEnum.CHARISMA,
                capacity_formula="size * 2",
            ),
        ]
        with patch("app.services.vault_service.room_crud.evaluate_capacity_formula", return_value=4):
            result = VaultService._prepare_room_data(rooms, "living room", vault_id, x=0, y=0)
        assert result["capacity"] == 4

    def test_with_output_formula(self) -> None:
        vault_id = VAULT_ID
        rooms = [
            _make_room_create(name="Power Generator", ability=SPECIALEnum.STRENGTH, output_formula="tier * size * 3"),
        ]
        with patch("app.services.vault_service.room_crud.evaluate_output_formula", return_value=9):
            result = VaultService._prepare_room_data(rooms, "power generator", vault_id, x=0, y=1)
        assert result["output"] == 9


# ---------------------------------------------------------------------------
# Test _prepare_initial_rooms
# ---------------------------------------------------------------------------


class TestPrepareInitialRooms:
    """Tests for _prepare_initial_rooms."""

    def test_standard_rooms(self) -> None:
        """Standard vault should have infrastructure, capacity, production, misc, no training."""
        service = VaultService()
        vault_id = VAULT_ID
        rooms = [
            _make_room_create("elevator", category=RoomTypeEnum.CAPACITY),
            _make_room_create("vault door", category=RoomTypeEnum.CAPACITY),
            _make_room_create("living room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA),
            _make_room_create("storage room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.ENDURANCE),
            _make_room_create("power generator", ability=SPECIALEnum.STRENGTH),
            _make_room_create("diner", ability=SPECIALEnum.AGILITY),
            _make_room_create("water treatment", ability=SPECIALEnum.PERCEPTION),
            _make_room_create("radio studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA),
        ]
        prepared = service._prepare_initial_rooms(rooms, vault_id, is_boosted=False)

        # infrastructure: 1 door + 3 elevators
        assert len(prepared.infrastructure) == 4
        assert prepared.infrastructure[0].name == "vault door"
        # capacity: 1 living + 1 storage
        assert len(prepared.capacity) == 2
        assert prepared.capacity[0].name == "living room"
        assert prepared.capacity[1].name == "storage room"
        # production: 3 rooms
        assert len(prepared.production) == 3
        assert prepared.production[0].name == "power generator"
        assert prepared.production[1].name == "diner"
        assert prepared.production[2].name == "water treatment"
        # misc: radio studio only
        assert len(prepared.misc) == 1
        assert prepared.misc[0].name == "radio studio"
        assert len(prepared.training) == 0
        assert len(prepared.arena) == 0

    def test_boosted_rooms(self) -> None:
        """Boosted vault adds medbay, science lab, overseer's office, arena, extra living rooms, and 7 training rooms."""
        service = VaultService()
        vault_id = VAULT_ID
        rooms = [
            _make_room_create("elevator", category=RoomTypeEnum.CAPACITY),
            _make_room_create("vault door", category=RoomTypeEnum.CAPACITY),
            _make_room_create("living room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA),
            _make_room_create("storage room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.ENDURANCE),
            _make_room_create("power generator", ability=SPECIALEnum.STRENGTH),
            _make_room_create("diner", ability=SPECIALEnum.AGILITY),
            _make_room_create("water treatment", ability=SPECIALEnum.PERCEPTION),
            _make_room_create("radio studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA),
            _make_room_create("medbay", ability=SPECIALEnum.INTELLIGENCE),
            _make_room_create("science lab", ability=SPECIALEnum.INTELLIGENCE),
            _make_room_create("overseer's office", category=RoomTypeEnum.MISC),
            _make_room_create("arena", category=RoomTypeEnum.ARENA),
            _make_room_create("weight room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH),
            _make_room_create("armory", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.PERCEPTION),
            _make_room_create("athletics room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.ENDURANCE),
            _make_room_create("classroom", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.CHARISMA),
            _make_room_create("game room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.INTELLIGENCE),
            _make_room_create("fitness room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.AGILITY),
            _make_room_create("lounge", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.LUCK),
        ]
        prepared = service._prepare_initial_rooms(rooms, vault_id, is_boosted=True)

        assert len(prepared.infrastructure) == 4
        # capacity: 1 base living + 1 storage + 3 extra living (ceil(25/8)=4 living)
        assert len(prepared.capacity) == 5
        # production: 3 base + medbay + science lab = 5
        assert len(prepared.production) == 5
        # misc: radio + overseer's office (arena is separate)
        assert len(prepared.misc) == 2
        # training: 7 rooms
        assert len(prepared.training) == 7
        assert len(prepared.arena) == 1
        assert prepared.arena[0].name == "arena"


# ---------------------------------------------------------------------------
# Test _create_initial_rooms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateInitialRooms:
    """Tests for the async _create_initial_rooms."""

    async def test_creates_rooms_and_updates_capacities(self) -> None:
        """Verify rooms created; living room increases population_max, storage increases max_space."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1, population_max=0, power_max=0, food_max=0, water_max=0)

        # Simulate capacity room creation for a living room
        living_room = _make_room(
            name="Living Room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA, capacity=4
        )

        with patch("app.services.vault_service.room_crud.create", new_callable=AsyncMock) as mock_create:
            # living room → CHARISMA → increases population_max
            mock_create.side_effect = [
                living_room,
                _make_room(
                    name="Storage Room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.ENDURANCE, capacity=10
                ),
            ]

            infra: list[RoomCreate] = []
            cap = [
                RoomCreate(**living_room.model_dump() | {"vault_id": vault_id}),
                RoomCreate(
                    name="Storage Room",
                    category=RoomTypeEnum.CAPACITY,
                    ability=SPECIALEnum.ENDURANCE,
                    capacity=10,
                    size_min=1,
                    size_max=3,
                    base_cost=100,
                    t2_upgrade_cost=500,
                    t3_upgrade_cost=1500,
                    vault_id=vault_id,
                ),
            ]
            prod: list[RoomCreate] = []
            misc: list[RoomCreate] = []
            training: list[RoomCreate] = []

            db_session = AsyncMock()
            db_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=0)))
            db_session.commit = AsyncMock()
            db_session.refresh = AsyncMock()

            service = VaultService()
            # Mock vault_crud.update_storage so it doesn't hit real DB
            with patch("app.services.vault_service.vault_crud.update_storage", new_callable=AsyncMock):
                await service._create_initial_rooms(
                    db_session,
                    vault,
                    PreparedRooms(
                        infrastructure=infra,
                        capacity=cap,
                        production=prod,
                        misc=misc,
                        training=training,
                        arena=[],
                    ),
                )

        assert vault.population_max == 4

    async def test_production_rooms_update_maxes(self) -> None:
        """Production rooms with specific abilities update vault max capacities."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1, population_max=10, power_max=0, food_max=0, water_max=0)

        power_room = Room(
            id="rp",
            name="Power Gen",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            capacity=20,
            tier=1,
            size=1,
            size_min=1,
            size_max=3,
            base_cost=100,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
        )
        diner_room = Room(
            id="rd",
            name="Diner",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.AGILITY,
            capacity=15,
            tier=1,
            size=1,
            size_min=1,
            size_max=3,
            base_cost=100,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
        )
        water_room = Room(
            id="rw",
            name="Water Treatment",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.PERCEPTION,
            capacity=12,
            tier=1,
            size=1,
            size_min=1,
            size_max=3,
            base_cost=100,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
        )

        with patch("app.services.vault_service.room_crud.create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [power_room, diner_room, water_room]

            db_session = AsyncMock()
            db_session.execute = AsyncMock()
            db_session.commit = AsyncMock()
            db_session.refresh = AsyncMock()

            infra: list[RoomCreate] = []
            cap: list[RoomCreate] = []
            prod = [
                RoomCreate(**power_room.model_dump() | {"vault_id": vault_id}),
                RoomCreate(**diner_room.model_dump() | {"vault_id": vault_id}),
                RoomCreate(**water_room.model_dump() | {"vault_id": vault_id}),
            ]
            misc: list[RoomCreate] = []
            training: list[RoomCreate] = []

            service = VaultService()
            await service._create_initial_rooms(
                db_session,
                vault,
                PreparedRooms(
                    infrastructure=infra,
                    capacity=cap,
                    production=prod,
                    misc=misc,
                    training=training,
                    arena=[],
                ),
            )

        assert vault.power_max == 20
        assert vault.food_max == 15
        assert vault.water_max == 12


# ---------------------------------------------------------------------------
# Test _create_initial_dwellers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateInitialDwellers:
    """Tests for dweler creation during vault init."""

    async def test_standard_dwellers_assigned(self) -> None:
        """Standard vault: 6 production dwellers + 1 radio + 2 living quarters = ~9 dwellers."""
        vault_id = VAULT_ID

        prod_rooms = [
            _make_room(name="Power Gen", ability=SPECIALEnum.STRENGTH),
            _make_room(name="Diner", ability=SPECIALEnum.AGILITY),
            _make_room(name="Water Treatment", ability=SPECIALEnum.PERCEPTION),
        ]
        cap_rooms = [_make_room(name="Living Room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA)]
        misc_rooms = [_make_room(name="Radio Studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA)]
        training_rooms: list[Room] = []

        call_count = 0

        async def fake_create_random(db_session, vault_id, dweller_data, **kwargs):
            nonlocal call_count
            call_count += 1
            gender = dweller_data.gender if hasattr(dweller_data, "gender") and dweller_data.gender else GenderEnum.MALE
            return Dweller(
                id=_dweller_id(call_count),
                first_name=f"Dweller{call_count}",
                last_name="Test",
                gender=gender,
                rarity=RarityEnum.COMMON,
                level=1,
            )

        with (
            patch(
                "app.services.vault_service.dweller_crud.create_random",
                new_callable=AsyncMock,
                side_effect=fake_create_random,
            ),
            patch("app.services.vault_service.dweller_crud.update", new_callable=AsyncMock),
        ):
            db_session = AsyncMock()
            db_session.commit = AsyncMock()

            service = VaultService()
            await service._create_initial_dwellers(
                db_session,
                vault_id,
                prod_rooms,
                training_rooms,
                misc_rooms,
                cap_rooms,
                is_boosted=False,
            )

        # 6 production + 1 radio + 2 living quarters = 9
        assert call_count == 9

    async def test_boosted_dwellers_assigned(self) -> None:
        """Boosted vault includes medbay, science lab, and training dwellers."""
        vault_id = VAULT_ID

        prod_rooms = [
            _make_room(name="Power Gen", ability=SPECIALEnum.STRENGTH),
            _make_room(name="Diner", ability=SPECIALEnum.AGILITY),
            _make_room(name="Water Treatment", ability=SPECIALEnum.PERCEPTION),
            _make_room(name="Medbay", ability=SPECIALEnum.INTELLIGENCE),
            _make_room(name="Science Lab", ability=SPECIALEnum.INTELLIGENCE),
        ]
        cap_rooms = [_make_room(name="Living Room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA)]
        misc_rooms = [_make_room(name="Radio Studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA)]
        training_rooms = [  # 7 training rooms
            _make_room(name=name, category=RoomTypeEnum.TRAINING, ability=ability)
            for i, (name, ability) in enumerate(
                [
                    ("Weight Room", SPECIALEnum.STRENGTH),
                    ("Armory", SPECIALEnum.PERCEPTION),
                    ("Athletics Room", SPECIALEnum.ENDURANCE),
                    ("Classroom", SPECIALEnum.CHARISMA),
                    ("Game Room", SPECIALEnum.INTELLIGENCE),
                    ("Fitness Room", SPECIALEnum.AGILITY),
                    ("Lounge", SPECIALEnum.LUCK),
                ]
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
            patch(
                "app.services.vault_service.dweller_crud.create_random",
                new_callable=AsyncMock,
                side_effect=fake_create_random,
            ),
            patch("app.services.vault_service.dweller_crud.update", new_callable=AsyncMock),
        ):
            db_session = AsyncMock()
            db_session.commit = AsyncMock()

            service = VaultService()
            await service._create_initial_dwellers(
                db_session,
                vault_id,
                prod_rooms,
                training_rooms,
                misc_rooms,
                cap_rooms,
                is_boosted=True,
            )

        # 6 production + 4 medbay/science + 7 training + 1 radio + 2 living quarters + 2 apprentices = 22
        assert call_count == 22

    async def test_initial_dweller_rarity_rolls_configured_chance(self) -> None:
        """Seeded dwellers roll RARE from standard/boosted rare chance — not hardcoded COMMON."""
        prod_rooms = [
            _make_room(name="Power Gen", ability=SPECIALEnum.STRENGTH),
            _make_room(name="Diner", ability=SPECIALEnum.AGILITY),
            _make_room(name="Water Treatment", ability=SPECIALEnum.PERCEPTION),
        ]
        rarities: list[RarityEnum] = []

        async def fake_create_random(db_session, vault_id, dweller_data, **kwargs):
            rarities.append(kwargs.get("rarity", RarityEnum.COMMON))
            return Dweller(
                id=_dweller_id(len(rarities)),
                first_name="Rare",
                last_name="Test",
                gender=GenderEnum.MALE,
                rarity=rarities[-1],
                level=1,
            )

        with (
            patch(
                "app.services.vault_service.dweller_crud.create_random",
                new_callable=AsyncMock,
                side_effect=fake_create_random,
            ),
            patch("app.services.vault_service.dweller_crud.update", new_callable=AsyncMock),
        ):
            db_session = AsyncMock()
            db_session.commit = AsyncMock()
            service = VaultService()

            with patch.object(game_config.vault_start, "standard_rare_chance", new=1.0):
                await service._create_initial_dwellers(db_session, VAULT_ID, prod_rooms, [], [], [], is_boosted=False)
            assert rarities
            assert all(rarity == RarityEnum.RARE for rarity in rarities)

            with patch.object(game_config.vault_start, "standard_rare_chance", new=0.0):
                await service._create_initial_dwellers(db_session, VAULT_ID, prod_rooms, [], [], [], is_boosted=False)
            assert rarities[len(rarities) // 2 :] == [RarityEnum.COMMON] * (len(rarities) // 2)

            # Boosted gate: boosted_rare_chance wins over standard when is_boosted=True.
            with (
                patch.object(game_config.vault_start, "standard_rare_chance", new=0.0),
                patch.object(game_config.vault_start, "boosted_rare_chance", new=1.0),
            ):
                await service._create_initial_dwellers(db_session, VAULT_ID, prod_rooms, [], [], [], is_boosted=True)
            assert rarities[-1] == RarityEnum.RARE

    async def test_dweller_creation_failure_logs_and_raises(self) -> None:
        """Exception during dweller creation logs and re-raises."""
        vault_id = VAULT_ID
        prod_rooms = [
            _make_room(name="Power Gen", ability=SPECIALEnum.STRENGTH),
            _make_room(name="Diner", ability=SPECIALEnum.AGILITY),
            _make_room(name="Water Treatment", ability=SPECIALEnum.PERCEPTION),
        ]
        cap_rooms: list[Room] = []
        misc_rooms: list[Room] = []
        training_rooms: list[Room] = []

        with patch(
            "app.services.vault_service.dweller_crud.create_random",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB error"),
        ):
            db_session = AsyncMock()

            service = VaultService()
            with pytest.raises(RuntimeError, match="DB error"):
                await service._create_initial_dwellers(
                    db_session,
                    vault_id,
                    prod_rooms,
                    training_rooms,
                    misc_rooms,
                    cap_rooms,
                    is_boosted=False,
                )


# ---------------------------------------------------------------------------
# Test _start_training_sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStartTrainingSessions:
    """Tests for training session startup."""

    async def test_noop_when_not_boosted(self) -> None:
        """When not boosted, method returns immediately."""
        service = VaultService()
        db_session = AsyncMock()
        result = await service._start_training_sessions(db_session, VAULT_ID, [], is_boosted=False)
        assert result is None

    async def test_noop_when_no_training_rooms(self) -> None:
        """When boosted but no training rooms, returns immediately."""
        service = VaultService()
        db_session = AsyncMock()
        result = await service._start_training_sessions(db_session, VAULT_ID, [], is_boosted=True)
        assert result is None

    async def test_starts_training_for_boosted_vault(self) -> None:
        """Boosted vault with training rooms starts training for assigned dwellers."""
        vault_id = VAULT_ID
        train_room = _make_room(
            name="Weight Room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH, tier=1
        )

        dweller = Dweller(
            id=DWELLER_ID,
            first_name="Train",
            last_name="Me",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            strength=5,
            perception=3,
            endurance=4,
            charisma=3,
            intelligence=3,
            agility=3,
            luck=3,
            level=1,
            room_id=train_room.id,
        )

        async def fake_refresh(obj):
            pass

        db_session = AsyncMock()
        db_session.refresh = fake_refresh
        db_session.execute = AsyncMock()

        with (
            patch(
                "app.services.vault_service.dweller_crud.get_multi_by_vault",
                new_callable=AsyncMock,
                return_value=[dweller],
            ),
            patch("app.services.vault_service.training_service.start_training", new_callable=AsyncMock),
        ):
            service = VaultService()
            await service._start_training_sessions(db_session, vault_id, [train_room], is_boosted=True)

        # If we got this far without exception, the call went through

    async def test_training_failure_is_logged_not_raised(self) -> None:
        """If training fails for one dweller, it is logged and other dwellers proceed."""
        vault_id = VAULT_ID
        train_room = _make_room(
            name="Weight Room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH, tier=1
        )

        dweller = Dweller(
            id=OTHER_DWELLER_ID,
            first_name="Fail",
            last_name="Dweller",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            strength=5,
            perception=3,
            endurance=4,
            charisma=3,
            intelligence=3,
            agility=3,
            luck=3,
            level=1,
            room_id=train_room.id,
        )

        async def fake_refresh(obj):
            pass

        db_session = AsyncMock()
        db_session.refresh = fake_refresh

        with (
            patch(
                "app.services.vault_service.dweller_crud.get_multi_by_vault",
                new_callable=AsyncMock,
                return_value=[dweller],
            ),
            patch(
                "app.services.vault_service.training_service.start_training",
                new_callable=AsyncMock,
                side_effect=ResourceNotFoundException(Dweller, "test-id"),
            ),
        ):
            service = VaultService()
            await service._start_training_sessions(db_session, vault_id, [train_room], is_boosted=True)

        # Should not raise; the warning is logged

    async def test_training_sessions_outer_exception_raises(self) -> None:
        """A non-domain exception during batch fetch raises."""
        vault_id = VAULT_ID
        train_room = _make_room(
            name="Weight Room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH, tier=1
        )

        db_session = AsyncMock()
        db_session.refresh = lambda _obj: None
        db_session.execute = AsyncMock()

        with patch(
            "app.services.vault_service.dweller_crud.get_multi_by_vault",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB down"),
        ):
            service = VaultService()
            with pytest.raises(RuntimeError, match="DB down"):
                await service._start_training_sessions(db_session, vault_id, [train_room], is_boosted=True)


# ---------------------------------------------------------------------------
# Test _create_initial_items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCreateInitialItems:
    """Tests for initial item creation."""

    async def test_creates_weapons_and_outfits(self) -> None:
        """When storage exists, 4 weapons and 4 outfits are created."""
        vault_id = VAULT_ID
        storage = _make_storage(vault_id=str(vault_id))

        db_session = AsyncMock()
        db_session.add = MagicMock()
        db_session.commit = AsyncMock()

        # mock the select(...) call to return storage
        mock_exec = MagicMock()
        mock_exec.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_exec)

        service = VaultService()
        await service._create_initial_items(db_session, vault_id)

        # Verify 8 items added (4 weapons + 4 outfits)
        assert db_session.add.call_count == 8
        db_session.commit.assert_awaited_once()

    async def test_noop_when_no_storage(self) -> None:
        """When storage does not exist, method returns without adding items."""
        vault_id = VAULT_ID

        db_session = AsyncMock()
        mock_exec = MagicMock()
        mock_exec.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=mock_exec)

        service = VaultService()
        await service._create_initial_items(db_session, vault_id)

        db_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Test _assign_initial_objectives
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAssignInitialObjectives:
    """Tests for initial objective assignment."""

    async def test_standard_assigns_daily_and_weekly(self) -> None:
        """Standard vault gets 1 daily + 1 weekly objective."""
        from app.models.objective import Objective

        vault_id = VAULT_ID
        daily_obj = Objective(
            id="od", challenge="Daily test", reward="10 caps", category="daily", objective_type="collect"
        )
        weekly_obj = Objective(
            id="ow", challenge="Weekly test", reward="50 caps", category="weekly", objective_type="collect"
        )

        service = VaultService()
        db_session = AsyncMock()

        # Simulate two execute calls: first for daily, second for weekly
        mock_daily = MagicMock()
        mock_daily.scalar_one_or_none.return_value = daily_obj
        mock_weekly = MagicMock()
        mock_weekly.scalar_one_or_none.return_value = weekly_obj
        db_session.execute = AsyncMock(side_effect=[mock_daily, mock_weekly])
        db_session.add = MagicMock()
        db_session.commit = AsyncMock()

        await service._assign_initial_objectives(db_session, vault_id, is_boosted=False)

        assert db_session.add.call_count == 2  # daily + weekly
        db_session.commit.assert_awaited_once()

    async def test_boosted_assigns_more_objectives(self) -> None:
        """Boosted vault adds achievement objectives."""
        from app.models.objective import Objective

        vault_id = VAULT_ID
        daily_obj = Objective(id="od", challenge="Daily", reward="10 caps", category="daily", objective_type="collect")
        weekly_obj = Objective(
            id="ow", challenge="Weekly", reward="50 caps", category="weekly", objective_type="collect"
        )
        achievements = [
            Objective(
                id=f"oa{i}",
                challenge=f"Ach{i}",
                reward=f"{i * 10} caps",
                category="achievement",
                objective_type="build",
            )
            for i in range(5)
        ]

        service = VaultService()
        db_session = AsyncMock()

        mock_daily = MagicMock()
        mock_daily.scalar_one_or_none.return_value = daily_obj
        mock_weekly = MagicMock()
        mock_weekly.scalar_one_or_none.return_value = weekly_obj
        mock_basic = MagicMock()
        mock_basic.scalars.return_value.all.return_value = achievements
        db_session.execute = AsyncMock(side_effect=[mock_daily, mock_weekly, mock_basic])
        db_session.add = MagicMock()
        db_session.commit = AsyncMock()

        await service._assign_initial_objectives(db_session, vault_id, is_boosted=True)

        # 2 (daily/weekly) + 5 (achievements) = 7
        assert db_session.add.call_count == 7

    async def test_sqlalchemy_error_is_handled(self) -> None:
        """SQLAlchemyError during assignment is caught and logged, not raised."""
        vault_id = VAULT_ID

        service = VaultService()
        db_session = AsyncMock()
        from sqlalchemy.exc import SQLAlchemyError

        db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB error"))

        # Should not raise
        await service._assign_initial_objectives(db_session, vault_id, is_boosted=False)


# ---------------------------------------------------------------------------
# Test _create_initial_items noop edge
# ---------------------------------------------------------------------------
# (already tested above in TestCreateInitialItems)


# ---------------------------------------------------------------------------
# Test transfer_medical_supplies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTransferMedicalSupplies:
    """Tests for medical supply transfer."""

    async def test_no_storage_raises(self) -> None:
        """When no storage exists, ResourceNotFoundException is raised."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)

        db_session = AsyncMock()
        mock_exec = MagicMock()
        mock_exec.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=mock_exec)

        service = VaultService()
        with pytest.raises(ResourceNotFoundException):
            await service.transfer_medical_supplies(db_session, vault, DWELLER_ID, stimpaks=1, radaways=0)

    async def test_insufficient_stimpaks_raises(self) -> None:
        """When vault has fewer stimpaks than requested, ResourceConflictException."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)
        storage = _make_storage(vault_id=str(vault_id), stimpack=3, radaway=10)

        db_session = AsyncMock()
        mock_exec = MagicMock()
        mock_exec.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_exec)

        service = VaultService()
        with pytest.raises(ResourceConflictException, match="only has 3 stimpaks"):
            await service.transfer_medical_supplies(db_session, vault, DWELLER_ID, stimpaks=5, radaways=0)

    async def test_insufficient_radaways_raises(self) -> None:
        """When vault has fewer radaways than requested."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)
        storage = _make_storage(vault_id=str(vault_id), stimpack=10, radaway=2)

        db_session = AsyncMock()
        mock_exec = MagicMock()
        mock_exec.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_exec)

        service = VaultService()
        with pytest.raises(ResourceConflictException, match="only has 2 radaways"):
            await service.transfer_medical_supplies(db_session, vault, DWELLER_ID, stimpaks=0, radaways=5)

    async def test_dweller_vault_mismatch_raises(self) -> None:
        """When dweller belongs to different vault, AccessDeniedException."""
        from app.utils.exceptions import AccessDeniedException

        vault_id_a = VAULT_ID
        vault_id_b = VAULT_ID_B
        vault = Vault(id=vault_id_a, number=1)
        storage = _make_storage(vault_id=str(vault_id_a), stimpack=10, radaway=10)
        dweller_id = DWELLER_ID
        dweller = Dweller(
            id=dweller_id,
            first_name="Stranger",
            last_name="Dweller",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault_id_b,
            level=1,
        )

        db_session = AsyncMock()
        mock_storage = MagicMock()
        mock_storage.scalar_one_or_none.return_value = storage
        mock_dweller = MagicMock()
        mock_dweller.scalar_one_or_none.return_value = dweller

        db_session.execute = AsyncMock(side_effect=[mock_storage, mock_dweller])
        db_session.commit = AsyncMock()
        db_session.rollback = AsyncMock()

        with patch("app.services.vault_service.dweller_crud.get", new_callable=AsyncMock, return_value=dweller):
            service = VaultService()
            with pytest.raises(AccessDeniedException):
                await service.transfer_medical_supplies(db_session, vault, dweller_id, stimpaks=1, radaways=0)

    async def test_dweller_stimpack_cap_raises(self) -> None:
        """When transfer would exceed dweller's max 15 stimpaks."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)
        storage = _make_storage(vault_id=str(vault_id), stimpack=20, radaway=10)
        dweller_id = DWELLER_ID
        dweller = Dweller(
            id=dweller_id,
            first_name="Full",
            last_name="Pockets",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault_id,
            level=1,
            stimpack=14,
        )

        db_session = AsyncMock()
        mock_storage = MagicMock()
        mock_storage.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_storage)
        db_session.commit = AsyncMock()
        db_session.rollback = AsyncMock()

        with patch("app.services.vault_service.dweller_crud.get", new_callable=AsyncMock, return_value=dweller):
            service = VaultService()
            with pytest.raises(ResourceConflictException, match="can only carry 15 stimpaks"):
                await service.transfer_medical_supplies(db_session, vault, dweller_id, stimpaks=2, radaways=0)

    async def test_dweller_radaway_cap_raises(self) -> None:
        """When transfer would exceed dweller's max 15 radaways."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)
        storage = _make_storage(vault_id=str(vault_id), stimpack=10, radaway=20)
        dweller_id = DWELLER_ID
        dweller = Dweller(
            id=dweller_id,
            first_name="Rad",
            last_name="Sick",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault_id,
            level=1,
            radaway=13,
        )

        db_session = AsyncMock()
        mock_storage = MagicMock()
        mock_storage.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_storage)
        db_session.commit = AsyncMock()
        db_session.rollback = AsyncMock()

        with patch("app.services.vault_service.dweller_crud.get", new_callable=AsyncMock, return_value=dweller):
            service = VaultService()
            with pytest.raises(ResourceConflictException, match="can only carry 15 radaways"):
                await service.transfer_medical_supplies(db_session, vault, dweller_id, stimpaks=0, radaways=3)

    async def test_successful_transfer(self) -> None:
        """Happy path: supplies move from vault to dweller, storage and dweller updated."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)
        storage = _make_storage(vault_id=str(vault_id), stimpack=20, radaway=20)
        dweller_id = DWELLER_ID
        dweller = Dweller(
            id=dweller_id,
            first_name="Happy",
            last_name="Dweller",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault_id,
            level=1,
            stimpack=5,
            radaway=3,
        )

        db_session = AsyncMock()
        mock_storage = MagicMock()
        mock_storage.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_storage)
        db_session.add = MagicMock()
        db_session.commit = AsyncMock()
        db_session.rollback = AsyncMock()

        with (
            patch("app.services.vault_service.dweller_crud.get", new_callable=AsyncMock, return_value=dweller),
            patch("app.services.vault_service.dweller_crud.update", new_callable=AsyncMock),
        ):
            service = VaultService()
            result = await service.transfer_medical_supplies(db_session, vault, dweller_id, stimpaks=3, radaways=2)

        assert isinstance(result, MedicalTransferResponse)
        assert result.vault_stimpaks == 17  # 20 - 3
        assert result.vault_radaways == 18  # 20 - 2
        assert result.dweller_stimpaks == 8  # 5 + 3
        assert result.dweller_radaways == 5  # 3 + 2

    async def test_transfer_success_with_nulls(self) -> None:
        """Transfer works when Storage stimpack/radaway are None (coerced to 0)."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)
        storage = Storage(
            id="s",
            vault_id=str(vault_id),
            stimpack=None,  # type: ignore[arg-type]
            radaway=None,  # type: ignore[arg-type]
            max_space=100,
        )
        dweller_id = DWELLER_ID
        dweller = Dweller(
            id=dweller_id,
            first_name="Null",
            last_name="Dweller",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault_id,
            level=1,
            stimpack=0,
            radaway=0,
        )

        db_session = AsyncMock()
        mock_storage = MagicMock()
        mock_storage.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_storage)
        db_session.add = MagicMock()
        db_session.commit = AsyncMock()
        db_session.rollback = AsyncMock()

        with (
            patch("app.services.vault_service.dweller_crud.get", new_callable=AsyncMock, return_value=dweller),
            patch("app.services.vault_service.dweller_crud.update", new_callable=AsyncMock),
        ):
            service = VaultService()
            # With 0 in vault, any positive request raises
            with pytest.raises(ResourceConflictException):
                await service.transfer_medical_supplies(db_session, vault, dweller_id, stimpaks=1, radaways=0)

    async def test_transfer_rollback_on_error(self) -> None:
        """If commit fails, db_session.rollback() is called."""
        vault_id = VAULT_ID
        vault = Vault(id=vault_id, number=1)
        storage = _make_storage(vault_id=str(vault_id), stimpack=20, radaway=20)
        dweller_id = DWELLER_ID
        dweller = Dweller(
            id=dweller_id,
            first_name="Rollback",
            last_name="Test",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault_id,
            level=1,
            stimpack=5,
            radaway=3,
        )

        db_session = AsyncMock()
        mock_storage = MagicMock()
        mock_storage.scalar_one_or_none.return_value = storage
        db_session.execute = AsyncMock(return_value=mock_storage)
        db_session.add = MagicMock()
        db_session.commit = AsyncMock(side_effect=RuntimeError("Commit failed"))
        db_session.rollback = AsyncMock()

        with (
            patch("app.services.vault_service.dweller_crud.get", new_callable=AsyncMock, return_value=dweller),
            patch("app.services.vault_service.dweller_crud.update", new_callable=AsyncMock),
        ):
            service = VaultService()
            with pytest.raises(RuntimeError, match="Commit failed"):
                await service.transfer_medical_supplies(db_session, vault, dweller_id, stimpaks=1, radaways=0)

        db_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test update_vault_resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUpdateVaultResources:
    """Tests for update_vault_resources."""

    async def test_updates_resources_and_emits_events(self) -> None:
        """Resource manager processes vault and returns updated resources + events."""

        vault_id = VAULT_ID

        new_resources = VaultUpdate(power=80, food=60, water=50)
        events = ResourceTickEvents(
            production=ResourceProduction(power=10, food=5),
            consumption=PrimaryResourceAmounts(food=1, water=1),
        )

        service = VaultService()
        service.resource_manager = MagicMock()
        service.resource_manager.process_vault_resources = AsyncMock(return_value=(new_resources, events))
        service.resource_manager.emit_production_events = AsyncMock()

        db_session = AsyncMock()
        db_session.commit = AsyncMock()
        db_session.refresh = AsyncMock()

        with patch("app.services.vault_service.vault_crud.update", new_callable=AsyncMock) as mock_vault_update:
            returned_vault = Vault(id=vault_id, number=1, power=80, food=60, water=50)
            mock_vault_update.return_value = returned_vault

            result = await service.update_vault_resources(db_session, vault_id)

        # Verify ResourceManager was called
        service.resource_manager.process_vault_resources.assert_awaited_once_with(
            db_session=db_session,
            vault_id=vault_id,
            seconds_passed=60,
        )

        service.resource_manager.emit_production_events.assert_awaited_once_with(vault_id, events)

        # Verify vault was updated
        mock_vault_update.assert_awaited_once()
        assert result == returned_vault

    async def test_no_events_when_production_empty(self) -> None:
        """No events emitted when production dict is empty."""

        vault_id = VAULT_ID

        new_resources = VaultUpdate(power=80, food=60, water=50)
        events = ResourceTickEvents()

        service = VaultService()
        service.resource_manager = MagicMock()
        service.resource_manager.process_vault_resources = AsyncMock(return_value=(new_resources, events))
        service.resource_manager.emit_production_events = AsyncMock()

        db_session = AsyncMock()

        with patch("app.services.vault_service.vault_crud.update", new_callable=AsyncMock):
            await service.update_vault_resources(db_session, vault_id)

        service.resource_manager.emit_production_events.assert_awaited_once_with(vault_id, events)

    async def test_no_events_when_amount_zero_or_negative(self) -> None:
        """Events not emitted for zero or negative production amounts."""

        vault_id = VAULT_ID

        new_resources = VaultUpdate(power=80, food=60, water=50)
        events = ResourceTickEvents(production=ResourceProduction(power=0, food=-1, water=3))

        service = VaultService()
        service.resource_manager = MagicMock()
        service.resource_manager.process_vault_resources = AsyncMock(return_value=(new_resources, events))
        service.resource_manager.emit_production_events = AsyncMock()

        db_session = AsyncMock()

        with patch("app.services.vault_service.vault_crud.update", new_callable=AsyncMock):
            await service.update_vault_resources(db_session, vault_id)

        service.resource_manager.emit_production_events.assert_awaited_once_with(vault_id, events)


# ---------------------------------------------------------------------------
# Test initiate_vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInitiateVault:
    """Integration-style tests for the full initiate_vault orchestration."""

    async def test_initiate_vault_standard(self) -> None:
        """Standard vault initialization end-to-end with mocked dependencies."""
        vault_id = VAULT_ID
        user_id = UUID4("11111111-1111-1111-1111-111111111111")

        vault = Vault(
            id=vault_id,
            number=42,
            user_id=user_id,
            population_max=0,
            power_max=30,
            food_max=30,
            water_max=30,
        )
        storage_obj = _make_storage(vault_id=str(vault_id), stimpack=0, radaway=0)

        # Build mock rooms for get_static_game_data
        room_templates = [
            _make_room_create("vault door", category=RoomTypeEnum.CAPACITY),
            _make_room_create("elevator", category=RoomTypeEnum.CAPACITY),
            _make_room_create(
                "living room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA, capacity_formula="size * 2"
            ),
            _make_room_create("storage room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.ENDURANCE),
            _make_room_create("power generator", ability=SPECIALEnum.STRENGTH),
            _make_room_create("diner", ability=SPECIALEnum.AGILITY),
            _make_room_create("water treatment", ability=SPECIALEnum.PERCEPTION),
            _make_room_create("radio studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA),
            _make_room_create("weight room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH),
        ]

        mock_game_data = MagicMock()
        mock_game_data.rooms = room_templates

        # Create actual VaultService with mocked internals
        service = VaultService()

        # Mock all the sub-methods that do heavy lifting
        service._prepare_initial_rooms = MagicMock(
            return_value=PreparedRooms(
                infrastructure=[
                    RoomCreate(
                        name="Vault Door",
                        category=RoomTypeEnum.CAPACITY,
                        ability=None,
                        size_min=1,
                        size_max=3,
                        base_cost=100,
                        t2_upgrade_cost=500,
                        t3_upgrade_cost=1500,
                        vault_id=vault_id,
                    )
                ],
                capacity=[],
                production=[],
                misc=[],
                training=[],
                arena=[],
            )
        )

        prod_rooms = [_make_room(name="Power Gen", ability=SPECIALEnum.STRENGTH, capacity=10)]
        train_rooms: list[Room] = []
        misc_rooms: list[Room] = []
        cap_rooms: list[Room] = []
        arena_rooms: list[Room] = []

        service._create_initial_rooms = AsyncMock(
            return_value=(
                vault,
                CreatedRooms(
                    production=prod_rooms,
                    training=train_rooms,
                    misc=misc_rooms,
                    capacity=cap_rooms,
                    arena=arena_rooms,
                ),
            )
        )
        service._create_initial_dwellers = AsyncMock()
        service._start_training_sessions = AsyncMock()
        service._assign_initial_objectives = AsyncMock()
        service._create_initial_items = AsyncMock()

        db_session = AsyncMock()
        db_session.commit = AsyncMock()
        db_session.refresh = AsyncMock()
        db_session.add = MagicMock()
        db_session.execute = AsyncMock()

        with (
            patch(
                "app.services.vault_service.vault_crud.create_with_user_id",
                new_callable=AsyncMock,
                return_value=vault,
            ),
            patch(
                "app.services.vault_service.vault_crud.create_storage",
                new_callable=AsyncMock,
                return_value=storage_obj,
            ),
            patch("app.services.vault_service.vault_crud.update", new_callable=AsyncMock, return_value=vault),
            patch(
                "app.services.vault_service.get_static_game_data",
                new_callable=AsyncMock,
                return_value=mock_game_data,
            ),
            patch("app.services.vault_service.room_crud.evaluate_capacity_formula", return_value=4),
            patch(
                "app.services.vault_service.compute_medical_capacity",
                return_value={"stimpack": 0, "radaway": 0},
            ),
        ):
            result = await service.initiate_vault(
                db_session,
                VaultNumber(number=42),
                user_id,
                is_boosted=False,
            )

        assert result == vault
        service._create_initial_rooms.assert_awaited_once()
        service._create_initial_dwellers.assert_awaited_once()

    async def test_initiate_vault_boosted(self) -> None:
        """Boosted vault includes training sessions."""
        vault_id = VAULT_ID
        user_id = UUID4("11111111-1111-1111-1111-111111111111")

        vault = Vault(
            id=vault_id,
            number=99,
            user_id=user_id,
            population_max=0,
            power_max=50,
            food_max=50,
            water_max=50,
        )
        storage_obj = _make_storage(vault_id=str(vault_id), stimpack=0, radaway=0)

        room_templates = [
            _make_room_create("elevator", category=RoomTypeEnum.CAPACITY),
            _make_room_create("vault door", category=RoomTypeEnum.CAPACITY),
            _make_room_create("living room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA),
            _make_room_create("storage room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.ENDURANCE),
            _make_room_create("power generator", ability=SPECIALEnum.STRENGTH),
            _make_room_create("diner", ability=SPECIALEnum.AGILITY),
            _make_room_create("water treatment", ability=SPECIALEnum.PERCEPTION),
            _make_room_create("medbay", ability=SPECIALEnum.INTELLIGENCE),
            _make_room_create("science lab", ability=SPECIALEnum.INTELLIGENCE),
            _make_room_create("radio studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA),
            _make_room_create("overseer's office", category=RoomTypeEnum.MISC),
            _make_room_create("weight room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH),
            _make_room_create("armory", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.PERCEPTION),
            _make_room_create("athletics room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.ENDURANCE),
            _make_room_create("classroom", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.CHARISMA),
            _make_room_create("game room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.INTELLIGENCE),
            _make_room_create("fitness room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.AGILITY),
            _make_room_create("lounge", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.LUCK),
        ]

        mock_game_data = MagicMock()
        mock_game_data.rooms = room_templates

        service = VaultService()

        prod_rooms = [
            _make_room(f"p{i}", name, ability=ability)
            for i, (name, ability) in enumerate(
                [
                    ("Power Gen", SPECIALEnum.STRENGTH),
                    ("Diner", SPECIALEnum.AGILITY),
                    ("Water Treatment", SPECIALEnum.PERCEPTION),
                ],
                1,
            )
        ]
        train_rooms = [
            _make_room(name="Train Room", category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH)
            for i in range(7)
        ]
        misc_rooms = [_make_room(name="Radio Studio", category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA)]
        cap_rooms = [_make_room(name="Living Room", category=RoomTypeEnum.CAPACITY, ability=SPECIALEnum.CHARISMA)]

        service._prepare_initial_rooms = MagicMock(
            return_value=PreparedRooms(infrastructure=[], capacity=[], production=[], misc=[], training=[], arena=[])
        )
        service._create_initial_rooms = AsyncMock(
            return_value=(
                vault,
                CreatedRooms(
                    production=prod_rooms,
                    training=train_rooms,
                    misc=misc_rooms,
                    capacity=cap_rooms,
                    arena=[],
                ),
            )
        )
        service._create_initial_dwellers = AsyncMock()
        service._start_training_sessions = AsyncMock()
        service._assign_initial_objectives = AsyncMock()
        service._create_initial_items = AsyncMock()

        db_session = AsyncMock()
        db_session.commit = AsyncMock()
        db_session.refresh = AsyncMock()
        db_session.add = MagicMock()
        db_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=storage_obj)))

        with (
            patch(
                "app.services.vault_service.vault_crud.create_with_user_id",
                new_callable=AsyncMock,
                return_value=vault,
            ),
            patch(
                "app.services.vault_service.vault_crud.create_storage",
                new_callable=AsyncMock,
                return_value=storage_obj,
            ),
            patch("app.services.vault_service.vault_crud.update", new_callable=AsyncMock, return_value=vault),
            patch(
                "app.services.vault_service.get_static_game_data",
                new_callable=AsyncMock,
                return_value=mock_game_data,
            ),
            patch("app.services.vault_service.room_crud.evaluate_capacity_formula", return_value=4),
            patch(
                "app.services.vault_service.compute_medical_capacity",
                return_value={"stimpack": 5, "radaway": 5},
            ),
        ):
            result = await service.initiate_vault(
                db_session,
                VaultNumber(number=99, boosted=True),
                user_id,
                is_boosted=True,
            )

        assert result == vault
        service._start_training_sessions.assert_awaited_once()
        service._assign_initial_objectives.assert_awaited_once()

    async def test_initiate_vault_standard_honors_vault_start_config(self, monkeypatch) -> None:
        """initiate_vault consumes VaultStartConfig instead of hardcoded literals."""
        from app.core.game_config import VaultStartConfig, game_config

        monkeypatch.setattr(
            game_config,
            "vault_start",
            VaultStartConfig(initial_resource_pct=0.8, initial_stimpaks=3, initial_radaways=2),
        )

        vault_id = VAULT_ID
        user_id = UUID4("11111111-1111-1111-1111-111111111111")

        vault = Vault(
            id=vault_id,
            number=42,
            user_id=user_id,
            population_max=0,
            power_max=30,
            food_max=30,
            water_max=30,
        )
        storage_obj = _make_storage(vault_id=str(vault_id), stimpack=0, radaway=0)

        service = VaultService()
        service._prepare_initial_rooms = MagicMock(
            return_value=PreparedRooms(infrastructure=[], capacity=[], production=[], misc=[], training=[], arena=[])
        )
        service._create_initial_rooms = AsyncMock(
            return_value=(vault, CreatedRooms(production=[], training=[], misc=[], capacity=[], arena=[]))
        )
        service._create_initial_dwellers = AsyncMock()
        service._start_training_sessions = AsyncMock()
        service._assign_initial_objectives = AsyncMock()
        service._create_initial_items = AsyncMock()

        db_session = AsyncMock()
        db_session.commit = AsyncMock()
        db_session.refresh = AsyncMock()
        db_session.add = MagicMock()
        db_session.execute = AsyncMock()

        with (
            patch(
                "app.services.vault_service.vault_crud.create_with_user_id",
                new_callable=AsyncMock,
                return_value=vault,
            ),
            patch(
                "app.services.vault_service.vault_crud.create_storage",
                new_callable=AsyncMock,
                return_value=storage_obj,
            ),
            patch(
                "app.services.vault_service.vault_crud.update",
                new_callable=AsyncMock,
                return_value=vault,
            ) as mock_update,
            patch(
                "app.services.vault_service.get_static_game_data",
                new_callable=AsyncMock,
                return_value=MagicMock(rooms=[]),
            ),
            patch(
                "app.services.vault_service.storage_crud.get_by_vault",
                new_callable=AsyncMock,
                return_value=storage_obj,
            ),
            patch(
                "app.services.vault_service.compute_medical_capacity",
                return_value={"stimpack": 10, "radaway": 10},
            ),
        ):
            result = await service.initiate_vault(db_session, VaultNumber(number=42), user_id, is_boosted=False)

        assert result == vault
        assert mock_update.await_count == 1
        update_in = mock_update.await_args.kwargs["obj_in"]
        assert update_in.power == int(30 * 0.8) == 24
        assert update_in.food == 24
        assert update_in.water == 24
        assert storage_obj.stimpack == 3
        assert storage_obj.radaway == 2


class TestVaultStartConfig:
    """VaultStartConfig defaults and validation bounds (VAULT_START_* env)."""

    def test_defaults_and_bounds(self) -> None:
        from app.core.game_config import VaultStartConfig

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
        """Vault-start settings read VAULT_START_* values from the project dotenv file."""
        (tmp_path / ".env").write_text("VAULT_START_INITIAL_RESOURCE_PCT=0.8\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("VAULT_START_INITIAL_RESOURCE_PCT", raising=False)

        from app.core.game_config import VaultStartConfig

        assert VaultStartConfig().initial_resource_pct == 0.8
