from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import crud
from app.core.enums import RoomTypeEnum
from app.core.grid_config import ELEVATOR_UNITS, FLOOR_UNITS, GRID_BUILD_X_MAX, SHAFT_X, UNITS_PER_ROOM
from app.crud.user_profile import profile_crud
from app.models.vault import Vault
from app.schemas.room import RoomBuild, RoomCreate, RoomUpdate
from app.schemas.vault import VaultUpdate
from app.services.room_service import room_service
from app.tests.factory.rooms import create_fake_room
from app.tests.utils.user import authentication_token_from_email

ROOM_FIELDS = (
    "id",
    "name",
    "category",
    "ability",
    "population_required",
    "base_cost",
    "incremental_cost",
    "tier",
    "t2_upgrade_cost",
    "t3_upgrade_cost",
    "output",
    "size_min",
    "size_max",
)


async def _styled_room(session, vault, *, tier: int = 3, room_style: str = "default"):
    data = create_fake_room() | {
        "name": "Diner",
        "category": RoomTypeEnum.PRODUCTION,
        "tier": tier,
        "room_style": room_style,
    }
    return await crud.room.create(session, obj_in=RoomCreate(**data, vault_id=vault.id))


async def _set_caps(session, vault, caps: int) -> None:
    await crud.vault.update(session, vault.id, VaultUpdate(bottle_caps=caps))
    await session.refresh(vault)


async def _upgrade_ready(session, vault, room_data, caps, **overrides):
    room_data.update(
        {"tier": 1, "t2_upgrade_cost": 500, "t3_upgrade_cost": 1500, "capacity": 10, "output": 20} | overrides
    )
    await _set_caps(session, vault, caps)
    return await crud.room.create(session, RoomCreate(**room_data, vault_id=vault.id))


@pytest.mark.smoke
async def test_read_room_list(async_client, async_session, room, superuser_token_headers) -> None:
    await crud.room.create(async_session, RoomCreate(**create_fake_room(), vault_id=room.vault_id))
    response = await async_client.get("/rooms/", headers=superuser_token_headers)
    rooms = response.json()
    assert response.status_code == 200
    assert len(rooms) == 2
    for room_row in rooms:
        assert set(ROOM_FIELDS) <= set(room_row)

    detail = await async_client.get(f"/rooms/{room.id}", headers=superuser_token_headers)
    assert detail.status_code == 200
    for field in ROOM_FIELDS[1:]:
        assert detail.json()[field] == getattr(room, field)


async def test_get_buildable_rooms_awaits_static_game_data() -> None:
    game_data = MagicMock()
    game_data.get_buildable_rooms.return_value = ["power generator"]
    with (
        patch("app.core.game_data.get_static_game_data", new=AsyncMock(return_value=game_data)),
        patch(
            "app.services.room_service.crud.room.get_maxed_unique_room_names",
            new=AsyncMock(return_value={"vault door"}),
        ),
    ):
        buildable_rooms = await room_service.get_buildable_rooms(MagicMock(), uuid4())
    assert buildable_rooms == ["power generator"]


@pytest.mark.smoke
async def test_build_room_uses_backend_template(async_client, superuser_token_headers, vault, async_session) -> None:
    from app.utils.static_data import game_data_store

    # Seed the elevator infrastructure the real game creates at vault init
    template = game_data_store.get_room("Elevator")
    await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(**template.model_dump() | {"vault_id": vault.id, "coordinate_x": 0, "coordinate_y": 2}),
    )
    payload = {"vault_id": str(vault.id), "room_name": "Power Generator", "coordinate_x": 1, "coordinate_y": 2}
    response = await async_client.post("/rooms/build/", json=payload, headers=superuser_token_headers)
    assert response.status_code == 200
    built = response.json()
    assert built["base_cost"] == 100
    assert built["category"] == "production"
    assert built["tier"] == 1
    assert built["size"] == 3
    assert built["image_url"]

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


async def test_build_room_rejects_unknown_or_infrastructure_template(
    async_client, superuser_token_headers, vault
) -> None:
    for room_name in ("Unknown Room", "Vault Door"):
        response = await async_client.post(
            "/rooms/build/",
            json={"vault_id": str(vault.id), "room_name": room_name, "coordinate_x": 3, "coordinate_y": 2},
            headers=superuser_token_headers,
        )
        assert response.status_code == 400


@pytest.mark.smoke
async def test_apply_room_style_endpoint(async_client, superuser_token_headers, async_session, vault) -> None:
    room = await _styled_room(async_session, vault)
    await crud.vault_theme.mark_crafted(async_session, vault_id=vault.id, style="party")
    await async_session.commit()

    response = await async_client.post(
        f"/rooms/style/{room.id}", json={"style": "party"}, headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["room_style"] == "party"
    assert response.json()["image_url"] == "/static/room_images/FOS Diner Party.png"


@pytest.mark.parametrize(
    ("tier", "preset", "style", "status", "detail"),
    [
        (2, "default", "party", 400, "tier 3"),
        (3, "default", "halloween", 400, "Craft the halloween theme"),
        (1, "party", "default", 200, None),
    ],
)
async def test_apply_room_style_rules(
    async_client, superuser_token_headers, async_session, vault, tier, preset, style, status, detail
) -> None:
    room = await _styled_room(async_session, vault, tier=tier, room_style=preset)
    await crud.vault_theme.mark_crafted(async_session, vault_id=vault.id, style="party")
    await async_session.commit()

    response = await async_client.post(
        f"/rooms/style/{room.id}", json={"style": style}, headers=superuser_token_headers
    )
    assert response.status_code == status
    if detail:
        assert detail in response.json()["detail"]
    else:
        assert response.json()["room_style"] == style


@pytest.mark.skip(reason="Flaky in the full suite (400 only then); disabling until root-caused.")
async def test_upgrade_room_tiers(
    async_client, superuser_token_headers, async_session, vault_with_caps, room_data
) -> None:
    vault = vault_with_caps
    room = await _upgrade_ready(async_session, vault, room_data, 2500, size=2)
    initial_caps, initial_capacity, initial_output = vault.bottle_caps, room.capacity, room.output

    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    upgraded_room = response.json()
    assert upgraded_room["tier"] == 2
    assert upgraded_room["id"] == str(room.id)
    assert upgraded_room["capacity"] > initial_capacity
    assert upgraded_room["output"] > initial_output
    vault = await async_session.get(Vault, vault.id)
    assert vault.bottle_caps == initial_caps - 500

    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["tier"] == 3
    vault = await async_session.get(Vault, vault.id)
    assert vault.bottle_caps == initial_caps - 2000


async def test_upgrade_room_no_t2_cost(async_client, superuser_token_headers, async_session, vault, room_data) -> None:
    room = await _upgrade_ready(async_session, vault, room_data, 10000, t2_upgrade_cost=None, t3_upgrade_cost=None)

    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code in {422, 400}


async def test_upgrade_room_capacity_calculation(
    async_client, superuser_token_headers, async_session, vault, room_data
) -> None:
    room = await _upgrade_ready(
        async_session,
        vault,
        room_data,
        1000,
        size=2,
        category="production",
        ability="strength",
        capacity=15,
        output=30,
    )

    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    upgraded_room = response.json()
    # Expected tier ratio: (2+4)/(1+4) = 6/5 = 1.2
    assert upgraded_room["capacity"] == int(15 * 1.2)
    assert upgraded_room["output"] == int(30 * 1.2)


async def test_get_buildable_rooms_offers_unique_until_max_footprint(
    async_client, superuser_token_headers, async_session, vault
) -> None:
    response = await async_client.get(f"/rooms/buildable/{vault.id}/", headers=superuser_token_headers)
    assert response.status_code == 200
    initial_buildable = response.json()

    # The station is the growable unique room (3..9); a fresh vault can always build it.
    growable = next(r for r in initial_buildable if r.get("incremental_cost") is None and r["size_max"] > r["size_min"])
    assert growable is not None, "the fixture vault should always have a growable unique room"
    assert (growable["size_min"], growable["size_max"]) == (3, 9)

    drop = ("capacity_formula", "output_formula", "size", "coordinate_x", "coordinate_y")
    payload = {**{k: v for k, v in growable.items() if k not in drop}, "vault_id": vault.id}
    room = await crud.room.create(async_session, RoomCreate(**payload, size=3, coordinate_x=5, coordinate_y=5))

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


async def test_cannot_destroy_vault_door(async_client, superuser_token_headers, async_session, vault) -> None:
    door_data = {"name": "Vault Door", "category": RoomTypeEnum.MISC, "ability": None}
    door_data.update(base_cost=100, incremental_cost=25, t2_upgrade_cost=500, t3_upgrade_cost=2000)
    door_data.update(size_min=6, size_max=6, size=6, coordinate_x=0, coordinate_y=0, vault_id=vault.id)
    door = await crud.room.create(async_session, RoomCreate(**door_data))
    response = await async_client.delete(f"/rooms/destroy/{door.id}", headers=superuser_token_headers)
    assert response.status_code == 400
    assert "vault door" in response.json()["detail"].lower()
    assert await crud.room.get(async_session, door.id) is not None


@pytest.mark.parametrize(
    ("coordinate_x", "coordinate_y", "accepted"),
    [(0, 0, True), (7, 15, True), (-1, 0, False), (GRID_BUILD_X_MAX + 1, 0, False), (0, -1, False), (0, 16, False)],
)
def test_build_coordinates_must_stay_on_rendered_grid(coordinate_x: int, coordinate_y: int, accepted: bool) -> None:
    if accepted:
        room = RoomBuild(
            vault_id=uuid4(), room_name="Power Generator", coordinate_x=coordinate_x, coordinate_y=coordinate_y
        )
        assert (room.coordinate_x, room.coordinate_y) == (coordinate_x, coordinate_y)
    else:
        with pytest.raises(ValidationError):
            RoomBuild(
                vault_id=uuid4(), room_name="Power Generator", coordinate_x=coordinate_x, coordinate_y=coordinate_y
            )


async def test_grid_config_is_served_from_backend_constants(async_client, superuser_token_headers) -> None:
    response = await async_client.get("/rooms/grid-config/", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    for field, expected in (
        ("units_per_room", UNITS_PER_ROOM),
        ("elevator_units", ELEVATOR_UNITS),
        ("floor_units", FLOOR_UNITS),
        ("shaft_x", SHAFT_X),
    ):
        assert data[field] == expected
    assert data["right_slot_starts"][0] == SHAFT_X + ELEVATOR_UNITS
    assert len(data["left_slot_starts"]) == 2


async def test_split_and_merge_room_endpoints(async_client, async_session, vault, superuser_token_headers) -> None:
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


async def test_build_endpoint_extends_upgraded_radio_studio(
    async_client, superuser_token_headers, async_session, vault
) -> None:
    from app.schemas.dweller import DwellerCreate
    from app.tests.factory.dwellers import create_random_common_dweller
    from app.tests.test_services.test_room_service import _create_elevator, _create_radio_studio

    await _set_caps(async_session, vault, 10_000)
    for _ in range(20):
        await crud.dweller.create(
            async_session, obj_in=DwellerCreate(**create_random_common_dweller(), vault_id=vault.id)
        )
    studio = await _create_radio_studio(async_session, vault.id, coordinate_x=1, coordinate_y=1)
    await _create_elevator(async_session, vault.id, 1, coordinate_x=0)
    await room_service.upgrade_room(async_session, studio.id)
    await async_session.refresh(vault)
    starting_caps = vault.bottle_caps

    response = await async_client.post(
        "/rooms/build/",
        json={"vault_id": str(vault.id), "room_name": "Radio studio", "coordinate_x": 4, "coordinate_y": 1},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    grown = response.json()
    assert grown["id"] == str(studio.id)
    assert grown["tier"] == 2
    assert grown["size"] == 6
    await async_session.refresh(vault)
    # Catalog pricing: base 600 + one segment * incremental 150, plus 1500 to raise the added segment to tier 2.
    assert vault.bottle_caps == starting_caps - 2250
    assert (await crud.room.get_names_by_vault(async_session, vault.id)).count("Radio studio") == 1


@pytest.mark.parametrize("action", ["split", "merge"])
async def test_room_remodel_requires_ownership(async_client, async_session, vault, action) -> None:
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
