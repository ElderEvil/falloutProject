from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.grid_config import ELEVATOR_UNITS, FLOOR_UNITS, GRID_BUILD_X_MAX, SHAFT_X, UNITS_PER_ROOM
from app.crud.user_profile import profile_crud
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomBuild, RoomCreate, RoomUpdate
from app.schemas.vault import VaultUpdate
from app.services.room_service import room_service
from app.tests.factory.rooms import create_fake_room
from app.tests.utils.user import authentication_token_from_email, user_authentication_headers


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_read_room_list(
    async_client: AsyncClient, async_session: AsyncSession, room: Room, superuser_token_headers: dict[str, str]
):
    room_2_data = create_fake_room()
    room_2 = RoomCreate(**room_2_data, vault_id=room.vault_id)
    await crud.room.create(async_session, room_2)
    response = await async_client.get("/rooms/", headers=superuser_token_headers)
    rooms = response.json()
    assert response.status_code == 200
    assert len(rooms) == 2
    for r in rooms:
        assert "id" in r
        assert "name" in r
        assert "category" in r
        assert "ability" in r
        assert "population_required" in r
        assert "base_cost" in r
        assert "incremental_cost" in r
        assert "tier" in r
        assert "t2_upgrade_cost" in r
        assert "t3_upgrade_cost" in r
        assert "output" in r
        assert "size_min" in r
        assert "size_max" in r


@pytest.mark.asyncio
async def test_get_buildable_rooms_awaits_static_game_data() -> None:
    """The room service awaits the async static-data provider."""
    game_data = MagicMock()
    game_data.get_buildable_rooms.return_value = ["power generator"]

    with (
        patch("app.core.game_data.get_static_game_data", new_callable=AsyncMock, return_value=game_data),
        patch(
            "app.services.room_service.crud.room.get_maxed_unique_room_names",
            new_callable=AsyncMock,
            return_value={"vault door"},
        ),
    ):
        buildable_rooms = await room_service.get_buildable_rooms(MagicMock(), uuid4())

    assert buildable_rooms == ["power generator"]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_build_room_uses_backend_template(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    vault: Vault,
    async_session: AsyncSession,
):
    """The build endpoint derives every room attribute from its template."""
    from app.schemas.room import RoomCreate
    from app.utils.static_data import game_data_store

    # Seed the elevator infrastructure the real game creates at vault init
    elevator_template = game_data_store.get_room("Elevator")
    elevator_in = RoomCreate(
        **elevator_template.model_dump() | {"vault_id": vault.id, "coordinate_x": 0, "coordinate_y": 2}
    )
    await crud.room.create(db_session=async_session, obj_in=elevator_in)

    payload = {
        "vault_id": str(vault.id),
        "room_name": "Power Generator",
        "coordinate_x": 1,
        "coordinate_y": 2,
    }
    response = await async_client.post(
        "/rooms/build/",
        json=payload,
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    room = response.json()
    assert room["base_cost"] == 100
    assert room["category"] == "production"
    assert room["tier"] == 1
    assert room["size"] == 3
    assert room["image_url"]

    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile is not None
    assert profile.total_rooms_built == 1

    expansion = await async_client.post("/rooms/build/", json=payload, headers=superuser_token_headers)
    assert expansion.status_code == 200

    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile is not None
    assert profile.total_rooms_built == 1

    response = await async_client.post(
        "/rooms/build/", json=payload | {"base_cost": 1}, headers=superuser_token_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_build_room_rejects_unknown_or_infrastructure_template(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    vault: Vault,
):
    for room_name in ("Unknown Room", "Vault Door"):
        response = await async_client.post(
            "/rooms/build/",
            json={
                "vault_id": str(vault.id),
                "room_name": room_name,
                "coordinate_x": 3,
                "coordinate_y": 2,
            },
            headers=superuser_token_headers,
        )

        assert response.status_code == 400


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_read_room(async_client: AsyncClient, superuser_token_headers: dict[str, str], room: Room):
    response = await async_client.get(f"/rooms/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    response_room = response.json()
    assert response_room["name"] == room.name
    assert response_room["category"] == room.category
    assert response_room["ability"] == room.ability
    assert response_room["population_required"] == room.population_required
    assert response_room["base_cost"] == room.base_cost
    assert response_room["incremental_cost"] == room.incremental_cost
    assert response_room["tier"] == room.tier
    assert response_room["t2_upgrade_cost"] == room.t2_upgrade_cost
    assert response_room["t3_upgrade_cost"] == room.t3_upgrade_cost
    assert response_room["output"] == room.output
    assert response_room["size_min"] == room.size_min
    assert response_room["size_max"] == room.size_max


async def _styled_room(
    async_session: AsyncSession, vault: Vault, *, tier: int = 3, room_style: str = "default"
) -> Room:
    return await crud.room.create(
        async_session,
        obj_in=RoomCreate(
            **(
                create_fake_room()
                | {
                    "name": "Diner",
                    "category": RoomTypeEnum.PRODUCTION,
                    "tier": tier,
                    "room_style": room_style,
                }
            ),
            vault_id=vault.id,
        ),
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_apply_room_style_endpoint(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A crafted theme on a tier-3 room updates the style and sprite URL."""
    room = await _styled_room(async_session, vault)
    await crud.vault_theme.mark_crafted(async_session, vault_id=vault.id, style="party")
    await async_session.commit()

    response = await async_client.post(
        f"/rooms/style/{room.id}",
        json={"style": "party"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["room_style"] == "party"
    assert response.json()["image_url"] == "/static/room_images/FOS Diner Party.png"


@pytest.mark.asyncio
async def test_apply_room_style_rejects_rooms_below_tier_three(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    room = await _styled_room(async_session, vault, tier=2)
    await crud.vault_theme.mark_crafted(async_session, vault_id=vault.id, style="party")
    await async_session.commit()

    response = await async_client.post(
        f"/rooms/style/{room.id}",
        json={"style": "party"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    assert "tier 3" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_room_style_rejects_uncrafted_themes(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    room = await _styled_room(async_session, vault)

    response = await async_client.post(
        f"/rooms/style/{room.id}",
        json={"style": "halloween"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    assert "Craft the halloween theme" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_room_style_resets_to_standard_at_any_tier(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    room = await _styled_room(async_session, vault, tier=1, room_style="party")

    response = await async_client.post(
        f"/rooms/style/{room.id}",
        json={"style": "default"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["room_style"] == "default"


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Flaky: fails with 400 only when run in the full suite (passes in isolation and "
    "file-level runs). Likely shared-state pollution from earlier tests; disable until root-caused."
)
async def test_upgrade_room_tier_1_to_2(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault_with_caps: Vault,
    room_data: dict,
):
    """Test upgrading a room from tier 1 to tier 2."""
    room_data.update(
        {
            "tier": 1,
            "size": 2,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
            "capacity": 10,
            "output": 20,
        }
    )

    vault_update = VaultUpdate(bottle_caps=1000)
    vault = await crud.vault.update(async_session, vault_with_caps.id, vault_update)
    await async_session.refresh(vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    initial_caps = vault.bottle_caps
    initial_capacity = room.capacity
    initial_output = room.output

    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200

    upgraded_room = response.json()
    assert upgraded_room["tier"] == 2
    assert upgraded_room["id"] == str(room.id)

    assert upgraded_room["capacity"] > initial_capacity
    assert upgraded_room["output"] > initial_output

    vault = await async_session.get(Vault, vault.id)
    assert vault.bottle_caps == initial_caps - 500


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Flaky: fails with 400 only when run in the full suite (passes in isolation and file-level "
    "runs). Likely shared-state pollution from earlier tests; disable until root-caused."
)
async def test_upgrade_room_tier_2_to_3(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault_with_caps: Vault,
    room_data: dict,
):
    """Test upgrading a room from tier 2 to tier 3."""
    room_data.update(
        {
            "tier": 1,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
            "capacity": 10,
            "output": 20,
        }
    )

    vault_update = VaultUpdate(bottle_caps=2500)
    vault = await crud.vault.update(async_session, vault_with_caps.id, vault_update)
    await async_session.refresh(vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    tier2_room = response.json()
    assert tier2_room["tier"] == 2

    vault = await async_session.get(Vault, vault.id)
    caps_after_first_upgrade = vault.bottle_caps

    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200

    upgraded_room = response.json()
    assert upgraded_room["tier"] == 3

    vault = await async_session.get(Vault, vault.id)
    assert vault.bottle_caps == caps_after_first_upgrade - 1500


@pytest.mark.asyncio
async def test_upgrade_room_no_t2_cost(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test that upgrading fails when room has no t2_upgrade_cost defined."""
    room_data.update(
        {
            "tier": 1,
            "t2_upgrade_cost": None,
            "t3_upgrade_cost": None,
        }
    )

    vault.bottle_caps = 10000
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # Attempt to upgrade room with no upgrade cost
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 422 or response.status_code == 400


@pytest.mark.asyncio
async def test_upgrade_room_capacity_calculation(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test that capacity is calculated correctly after upgrade."""
    room_data.update(
        {
            "tier": 1,
            "size": 2,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
            "capacity": 15,  # Known starting capacity
            "output": 30,
            "category": "production",
            "ability": "strength",
        }
    )

    vault.bottle_caps = 1000
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # Upgrade room
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200

    upgraded_room = response.json()

    # Expected tier ratio: (2+4)/(1+4) = 6/5 = 1.2
    expected_capacity = int(15 * 1.2)  # 18
    expected_output = int(30 * 1.2)  # 36

    assert upgraded_room["capacity"] == expected_capacity
    assert upgraded_room["output"] == expected_output


@pytest.mark.asyncio
async def test_get_buildable_rooms_offers_unique_until_max_footprint(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
):
    """A unique room stays buildable while it can still merge, and disappears at size_max."""
    response = await async_client.get(f"/rooms/buildable/{vault.id}/", headers=superuser_token_headers)
    assert response.status_code == 200
    initial_buildable = response.json()

    # The station is the growable unique room (3..9); a fresh vault can always build it.
    growable = next(
        (
            room
            for room in initial_buildable
            if room.get("incremental_cost") is None and room["size_max"] > room["size_min"]
        ),
        None,
    )
    assert growable is not None, "the fixture vault should always have a growable unique room"
    assert (growable["size_min"], growable["size_max"]) == (3, 9)

    exclude_fields = ("capacity_formula", "output_formula", "size", "coordinate_x", "coordinate_y")
    room_dict = {k: v for k, v in growable.items() if k not in exclude_fields}
    room = await crud.room.create(
        async_session,
        RoomCreate(**room_dict, vault_id=vault.id, size=3, coordinate_x=5, coordinate_y=5),
    )

    async def buildable_names() -> list[str]:
        listing = await async_client.get(f"/rooms/buildable/{vault.id}/", headers=superuser_token_headers)
        assert listing.status_code == 200
        return [r["name"].lower() for r in listing.json()]

    name = growable["name"].lower()
    assert room.size == 3
    assert name in await buildable_names(), "size 3: a mergeable segment must stay offered"

    await crud.room.update(db_session=async_session, id=room.id, obj_in=RoomUpdate(size=6))
    assert name in await buildable_names(), "size 6: a mergeable segment must stay offered"

    await crud.room.update(db_session=async_session, id=room.id, obj_in=RoomUpdate(size=9))
    assert name not in await buildable_names(), "size 9: at size_max the unique room is hidden"


class TestVaultDoorProtection:
    """Tests for vault door protection (v2.4.0 bug fix #1)."""

    @pytest.mark.asyncio
    async def test_cannot_destroy_vault_door(
        self,
        async_client: AsyncClient,
        superuser_token_headers: dict[str, str],
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test that vault door cannot be destroyed."""
        # Create a vault door
        vault_door = RoomCreate(
            name="Vault Door",
            category=RoomTypeEnum.MISC,
            ability=None,
            base_cost=100,
            incremental_cost=25,
            t2_upgrade_cost=500,
            t3_upgrade_cost=2000,
            size_min=6,
            size_max=6,
            vault_id=vault.id,
            size=6,
            coordinate_x=0,
            coordinate_y=0,
        )
        door_room = await crud.room.create(async_session, vault_door)

        # Attempt to destroy via API
        response = await async_client.delete(f"/rooms/destroy/{door_room.id}", headers=superuser_token_headers)
        assert response.status_code == 400
        assert "vault door" in response.json()["detail"].lower()

        # Verify it still exists
        existing_door = await crud.room.get(async_session, door_room.id)
        assert existing_door is not None


class TestRoomBuildValidation:
    @pytest.mark.parametrize(("coordinate_x", "coordinate_y"), [(0, 0), (7, 15)])
    def test_build_accepts_rendered_grid_limits(self, coordinate_x: int, coordinate_y: int) -> None:
        room = RoomBuild(
            vault_id=uuid4(), room_name="Power Generator", coordinate_x=coordinate_x, coordinate_y=coordinate_y
        )
        assert (room.coordinate_x, room.coordinate_y) == (coordinate_x, coordinate_y)

    @pytest.mark.parametrize(("coordinate_x", "coordinate_y"), [(-1, 0), (GRID_BUILD_X_MAX + 1, 0), (0, -1), (0, 16)])
    def test_build_rejects_coordinates_outside_rendered_grid(self, coordinate_x: int, coordinate_y: int) -> None:
        with pytest.raises(ValidationError):
            RoomBuild(
                vault_id=uuid4(), room_name="Power Generator", coordinate_x=coordinate_x, coordinate_y=coordinate_y
            )


@pytest.mark.asyncio
async def test_grid_config_is_served_from_backend_constants(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """The vault grid geometry is owned by the backend and served to the UI."""
    response = await async_client.get("/rooms/grid-config/", headers=superuser_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["units_per_room"] == UNITS_PER_ROOM
    assert data["elevator_units"] == ELEVATOR_UNITS
    assert data["floor_units"] == FLOOR_UNITS
    assert data["shaft_x"] == SHAFT_X
    assert data["right_slot_starts"][0] == SHAFT_X + ELEVATOR_UNITS
    assert len(data["left_slot_starts"]) == 2


async def test_split_and_merge_room_endpoints(async_client, async_session, vault, superuser_token_headers):
    from app.tests.test_services.test_room_service import _create_existing_room

    source = await _create_existing_room(async_session, vault.id, coordinate_x=7, size=6)
    split = await async_client.post(f"/rooms/split/{source.id}", headers=superuser_token_headers)
    assert split.status_code == 200
    pieces = split.json()
    assert [r["size"] for r in pieces] == [3, 3]
    merge = await async_client.post(
        f"/rooms/merge/{pieces[1]['id']}", json={"other_room_id": pieces[0]["id"]}, headers=superuser_token_headers
    )
    assert merge.status_code == 200
    assert merge.json()["id"] == str(source.id)
    assert merge.json()["size"] == 6


@pytest.mark.parametrize("action", ["split", "merge"])
async def test_room_remodel_requires_ownership(async_client, async_session, vault, action):
    from app.tests.test_services.test_room_service import _create_existing_room

    source = await _create_existing_room(async_session, vault.id, coordinate_x=7, size=6)
    headers = await authentication_token_from_email(
        client=async_client, email="remodel-visitor@example.com", db_session=async_session
    )
    response = await async_client.post(
        f"/rooms/{action}/{source.id}",
        json={"other_room_id": str(source.id)} if action == "merge" else {},
        headers=headers,
    )
    assert response.status_code == 403
    await async_session.refresh(source)
    assert source.size == 6
