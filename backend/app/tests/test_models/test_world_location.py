from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum, PlaceKindEnum
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation

NOW = datetime(2026, 9, 26, 12, 0, 0)


def _location(**overrides) -> WorldLocation:
    return WorldLocation(
        **({"name": "Red Rocket", "normalized_name": "red rocket", "coord_x": 10.0, "coord_y": 20.0} | overrides)
    )


def _state(**overrides) -> VaultLocationState:
    return VaultLocationState(
        **({"vault_id": uuid4(), "location_id": uuid4(), "type": LocationTypeEnum.DISCOVERY} | overrides)
    )


async def _saved(session: AsyncSession, row):
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def test_create_and_read(async_session: AsyncSession) -> None:
    location = _location(coord_x=42.5, coord_y=73.1, description="A pre-war gas station.")
    await _saved(async_session, location)
    assert location.id is not None
    assert (location.name, location.normalized_name, location.kind) == ("Red Rocket", "red rocket", PlaceKindEnum.PLACE)
    assert location.vault_number is None
    assert (location.coord_x, location.coord_y) == (42.5, 73.1)
    assert (location.description, location.source) == ("A pre-war gas station.", "emergent")
    for enum_member in PlaceKindEnum:
        row = await _saved(
            async_session,
            _location(
                name=f"test_{enum_member.value}",
                normalized_name=f"test_{enum_member.value}",
                kind=enum_member,
                vault_number=7 if enum_member == PlaceKindEnum.VAULT else None,
            ),
        )
        assert (row.kind, row.kind.value) == (enum_member, enum_member.value)


@pytest.mark.parametrize(
    ("field", "attr", "bound"),
    [("coord_x", "ge", 0), ("coord_x", "le", 100), ("coord_y", "ge", 0), ("coord_y", "le", 100)],
)
def test_coord_fields_carry_bound_constraints(field: str, attr: str, bound: int) -> None:
    metadata = WorldLocation.model_fields[field].metadata
    assert any(hasattr(m, attr) and getattr(m, attr) == bound for m in metadata), (
        f"No {attr}={bound} constraint in {field} metadata: {metadata}"
    )


async def test_coord_edge_100_and_unique_normalized_name(async_session: AsyncSession) -> None:
    async_session.add(_location(name="edge", normalized_name="edge_100", coord_x=100.0, coord_y=100.0))
    await async_session.commit()
    await _saved(async_session, _location(name="Sanctuary Hills", normalized_name="sanctuary hills"))
    async_session.add(
        _location(name="Sanctuary Hills Copy", normalized_name="sanctuary hills", coord_x=30.0, coord_y=40.0)
    )
    with pytest.raises(IntegrityError):
        await async_session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "Out of Bounds", "normalized_name": "out_of_bounds", "coord_x": -1.0, "coord_y": 50.0},
        {"name": "Out of Bounds", "normalized_name": "out_of_bounds_2", "coord_x": 50.0, "coord_y": 101.0},
        {
            "name": "Vault 101",
            "normalized_name": "vault 101",
            "kind": PlaceKindEnum.VAULT,
            "coord_x": 50.0,
            "coord_y": 50.0,
        },
        {
            "name": "Numbered Place",
            "normalized_name": "numbered place",
            "vault_number": 9,
            "coord_x": 10.0,
            "coord_y": 10.0,
        },
    ],
)
async def test_invalid_location_rows_are_rejected_at_db(async_session: AsyncSession, overrides: dict) -> None:
    async_session.add(_location(**overrides))
    with pytest.raises(IntegrityError):
        await async_session.commit()


async def test_utc_datetime_round_trip_preserves_instant(async_session: AsyncSession) -> None:
    instant = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    offset_value = instant.astimezone(timezone(timedelta(hours=5, minutes=45)))
    location = _location(
        name="Timezone Round Trip",
        normalized_name=f"timezone-round-trip-{uuid4().hex}",
        created_at=offset_value,
        updated_at=offset_value,
    )
    assert location.created_at == offset_value
    async_session.add(location)
    await async_session.flush()
    assert location.created_at == offset_value
    await async_session.commit()
    location_id = location.id
    async_session.expunge_all()
    reloaded = await async_session.get(WorldLocation, location_id)
    assert reloaded is not None
    assert (reloaded.created_at, reloaded.created_at.utcoffset()) == (instant, timedelta(0))
    result = await async_session.exec(
        select(WorldLocation).where(WorldLocation.created_at <= instant + timedelta(minutes=15))
    )
    assert result.first() is not None


async def test_vault_location_state(async_session: AsyncSession) -> None:
    vault_id, location_id = uuid4(), uuid4()
    state = await _saved(
        async_session,
        VaultLocationState(
            vault_id=vault_id,
            location_id=location_id,
            type=LocationTypeEnum.DISCOVERY,
            description="Spotted on patrol.",
        ),
    )
    assert state.id is not None
    assert (state.vault_id, state.location_id, state.type) == (vault_id, location_id, LocationTypeEnum.DISCOVERY)
    assert (state.description, state.exploration_id) == ("Spotted on patrol.", None)
    for enum_member in LocationTypeEnum:
        row = await _saved(async_session, _state(type=enum_member))
        assert (row.type, row.type.value) == (enum_member, enum_member.value)
    other_vault, other_location = uuid4(), uuid4()
    await _saved(
        async_session,
        VaultLocationState(vault_id=other_vault, location_id=other_location, type=LocationTypeEnum.ORIGIN),
    )
    async_session.add(
        VaultLocationState(vault_id=other_vault, location_id=other_location, type=LocationTypeEnum.VISITED)
    )
    with pytest.raises(IntegrityError):
        await async_session.commit()


def test_clear_defaults_and_boundary_helpers() -> None:
    state = _state()
    assert (state.cleared_at, state.reclear_available_at, state.clear_count) == (None, None, 0)
    assert (state.is_cleared(NOW), state.time_remaining_seconds(NOW), state.is_dispatchable(NOW)) == (False, 0, True)
    metadata = VaultLocationState.model_fields["clear_count"].metadata
    assert any(hasattr(m, "ge") and m.ge == 0 for m in metadata), f"No ge=0 constraint in {metadata}"


@pytest.mark.parametrize(
    ("cleared_hours_ago", "reclear_hours", "clear_count", "is_cleared", "remaining", "dispatchable"),
    [(1, 5, 1, True, 5 * 3600, False), (5, 0, 1, False, 0, True), (10, -1, 2, False, 0, True)],
)
def test_cleared_state_helpers(
    cleared_hours_ago: int,
    reclear_hours: int,
    clear_count: int,
    is_cleared: bool,
    remaining: int,
    dispatchable: bool,
) -> None:
    state = _state(
        cleared_at=NOW - timedelta(hours=cleared_hours_ago),
        reclear_available_at=NOW + timedelta(hours=reclear_hours),
        clear_count=clear_count,
    )
    assert (state.is_cleared(NOW), state.time_remaining_seconds(NOW), state.is_dispatchable(NOW)) == (
        is_cleared,
        remaining,
        dispatchable,
    )


async def test_dweller_location_links(async_session: AsyncSession) -> None:
    dweller_id, location_id = uuid4(), uuid4()
    link = await _saved(
        async_session,
        DwellerLocation(dweller_id=dweller_id, location_id=location_id, relation=DwellerLocationRelationEnum.VISITED),
    )
    assert link.id is not None
    assert (link.dweller_id, link.location_id, link.relation) == (
        dweller_id,
        location_id,
        DwellerLocationRelationEnum.VISITED,
    )
    async_session.add(
        DwellerLocation(dweller_id=dweller_id, location_id=location_id, relation=DwellerLocationRelationEnum.VISITED)
    )
    with pytest.raises(IntegrityError):
        await async_session.commit()
    await async_session.rollback()
    async_session.add(
        DwellerLocation(dweller_id=dweller_id, location_id=location_id, relation=DwellerLocationRelationEnum.ORIGIN)
    )
    await async_session.commit()  # a different relation is allowed


@pytest.mark.parametrize("enum_cls", [LocationTypeEnum, PlaceKindEnum])
def test_member_names_are_uppercase(enum_cls: type) -> None:
    for member in enum_cls:
        assert member.name == member.name.upper()


@pytest.mark.parametrize(
    ("member", "value"),
    [
        (LocationTypeEnum.ORIGIN, "origin"),
        (LocationTypeEnum.VISITED, "visited"),
        (LocationTypeEnum.DISCOVERY, "discovery"),
        (LocationTypeEnum.HOME_VAULT, "home_vault"),
        (PlaceKindEnum.PLACE, "place"),
        (PlaceKindEnum.VAULT, "vault"),
    ],
)
def test_member_values_are_lowercase(member, value: str) -> None:
    assert member.value == value


def test_no_vault_member() -> None:
    assert "VAULT" not in [m.name for m in LocationTypeEnum]
