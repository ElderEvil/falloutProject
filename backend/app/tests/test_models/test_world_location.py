"""Tests for WorldLocation, VaultLocationState and DwellerLocation models."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum, PlaceKindEnum
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation


class TestWorldLocationModel:
    """Happy-path tests for the canonical registry."""

    async def test_create_and_read(self, async_session: AsyncSession) -> None:
        """Create a WorldLocation, persist, and read it back."""
        location = WorldLocation(
            name="Red Rocket",
            normalized_name="red rocket",
            coord_x=42.5,
            coord_y=73.1,
            description="A pre-war gas station.",
        )
        async_session.add(location)
        await async_session.commit()
        await async_session.refresh(location)

        assert location.id is not None
        assert location.name == "Red Rocket"
        assert location.normalized_name == "red rocket"
        assert location.kind == PlaceKindEnum.PLACE
        assert location.vault_number is None
        assert location.coord_x == 42.5
        assert location.coord_y == 73.1
        assert location.description == "A pre-war gas station."
        assert location.source == "emergent"

    async def test_kind_round_trip(self, async_session: AsyncSession) -> None:
        """Enum values persist correctly through the ORM."""
        for enum_member in PlaceKindEnum:
            location = WorldLocation(
                name=f"test_{enum_member.value}",
                normalized_name=f"test_{enum_member.value}",
                kind=enum_member,
                vault_number=7 if enum_member == PlaceKindEnum.VAULT else None,
                coord_x=10.0,
                coord_y=20.0,
            )
            async_session.add(location)
            await async_session.commit()
            await async_session.refresh(location)

            assert location.kind == enum_member
            assert location.kind.value == enum_member.value

    def test_coord_x_has_ge_constraint(self) -> None:
        """coord_x field must have ge=0 constraint."""
        field = WorldLocation.model_fields["coord_x"]
        assert any(hasattr(m, "ge") and m.ge == 0 for m in field.metadata), (
            f"No ge=0 constraint found in coord_x metadata: {field.metadata}"
        )

    def test_coord_x_has_le_constraint(self) -> None:
        """coord_x field must have le=100 constraint."""
        field = WorldLocation.model_fields["coord_x"]
        assert any(hasattr(m, "le") and m.le == 100 for m in field.metadata), (
            f"No le=100 constraint found in coord_x metadata: {field.metadata}"
        )

    def test_coord_y_has_ge_constraint(self) -> None:
        """coord_y field must have ge=0 constraint."""
        field = WorldLocation.model_fields["coord_y"]
        assert any(hasattr(m, "ge") and m.ge == 0 for m in field.metadata), (
            f"No ge=0 constraint found in coord_y metadata: {field.metadata}"
        )

    def test_coord_y_has_le_constraint(self) -> None:
        """coord_y field must have le=100 constraint."""
        field = WorldLocation.model_fields["coord_y"]
        assert any(hasattr(m, "le") and m.le == 100 for m in field.metadata), (
            f"No le=100 constraint found in coord_y metadata: {field.metadata}"
        )

    async def test_coord_edge_100(self, async_session: AsyncSession) -> None:
        """coord 100 is valid."""
        location = WorldLocation(
            name="edge",
            normalized_name="edge_100",
            coord_x=100.0,
            coord_y=100.0,
        )
        async_session.add(location)
        await async_session.commit()

    async def test_unique_normalized_name(self, async_session: AsyncSession) -> None:
        """Duplicate normalized_name raises IntegrityError (global merge key)."""
        loc1 = WorldLocation(
            name="Sanctuary Hills",
            normalized_name="sanctuary hills",
            coord_x=10.0,
            coord_y=20.0,
        )
        async_session.add(loc1)
        await async_session.commit()

        loc2 = WorldLocation(
            name="Sanctuary Hills Copy",
            normalized_name="sanctuary hills",
            coord_x=30.0,
            coord_y=40.0,
        )
        async_session.add(loc2)
        with pytest.raises(IntegrityError):
            await async_session.commit()

    async def test_coord_x_below_zero_rejected_at_db(self, async_session: AsyncSession) -> None:
        """DB CHECK constraint rejects coord_x < 0 at commit time."""
        location = WorldLocation(
            name="Out of Bounds",
            normalized_name="out_of_bounds",
            coord_x=-1.0,
            coord_y=50.0,
        )
        async_session.add(location)
        with pytest.raises(IntegrityError):
            await async_session.commit()

    async def test_coord_y_above_hundred_rejected_at_db(self, async_session: AsyncSession) -> None:
        """DB CHECK constraint rejects coord_y > 100 at commit time."""
        location = WorldLocation(
            name="Out of Bounds",
            normalized_name="out_of_bounds_2",
            coord_x=50.0,
            coord_y=101.0,
        )
        async_session.add(location)
        with pytest.raises(IntegrityError):
            await async_session.commit()

    async def test_vault_kind_requires_number(self, async_session: AsyncSession) -> None:
        """A VAULT row without vault_number violates the kind CHECK."""
        location = WorldLocation(
            name="Vault 101",
            normalized_name="vault 101",
            kind=PlaceKindEnum.VAULT,
            coord_x=50.0,
            coord_y=50.0,
        )
        async_session.add(location)
        with pytest.raises(IntegrityError):
            await async_session.commit()

    async def test_place_kind_rejects_number(self, async_session: AsyncSession) -> None:
        """A PLACE row with vault_number set violates the kind CHECK."""
        location = WorldLocation(
            name="Numbered Place",
            normalized_name="numbered place",
            vault_number=9,
            coord_x=10.0,
            coord_y=10.0,
        )
        async_session.add(location)
        with pytest.raises(IntegrityError):
            await async_session.commit()


class TestVaultLocationStateModel:
    """Happy-path and constraint tests for per-vault fog entries."""

    async def test_create_and_read(self, async_session: AsyncSession) -> None:
        """Create a state row and read it back."""
        vault_id = uuid4()
        location_id = uuid4()

        state = VaultLocationState(
            vault_id=vault_id,
            location_id=location_id,
            type=LocationTypeEnum.DISCOVERY,
            description="Spotted on patrol.",
        )
        async_session.add(state)
        await async_session.commit()
        await async_session.refresh(state)

        assert state.id is not None
        assert state.vault_id == vault_id
        assert state.location_id == location_id
        assert state.type == LocationTypeEnum.DISCOVERY
        assert state.description == "Spotted on patrol."
        assert state.exploration_id is None

    async def test_type_round_trip(self, async_session: AsyncSession) -> None:
        """Every LocationTypeEnum member persists through the ORM."""
        for enum_member in LocationTypeEnum:
            state = VaultLocationState(
                vault_id=uuid4(),
                location_id=uuid4(),
                type=enum_member,
            )
            async_session.add(state)
            await async_session.commit()
            await async_session.refresh(state)

            assert state.type == enum_member
            assert state.type.value == enum_member.value

    async def test_unique_vault_location(self, async_session: AsyncSession) -> None:
        """Duplicate (vault_id, location_id) raises IntegrityError."""
        vault_id = uuid4()
        location_id = uuid4()

        state1 = VaultLocationState(
            vault_id=vault_id,
            location_id=location_id,
            type=LocationTypeEnum.ORIGIN,
        )
        async_session.add(state1)
        await async_session.commit()

        state2 = VaultLocationState(
            vault_id=vault_id,
            location_id=location_id,
            type=LocationTypeEnum.VISITED,
        )
        async_session.add(state2)
        with pytest.raises(IntegrityError):
            await async_session.commit()


class TestVaultLocationStateClearHelpers:
    """Truth table for the map-point clear helpers (issue 772)."""

    def test_defaults_are_never_cleared(self) -> None:
        """A fresh row is never cleared: NULL timestamps and zero count."""
        state = VaultLocationState(
            vault_id=uuid4(),
            location_id=uuid4(),
            type=LocationTypeEnum.DISCOVERY,
        )
        assert state.cleared_at is None
        assert state.reclear_available_at is None
        assert state.clear_count == 0

    def test_clear_count_has_ge_constraint(self) -> None:
        """clear_count must not accept negative values."""
        field = VaultLocationState.model_fields["clear_count"]
        assert any(hasattr(m, "ge") and m.ge == 0 for m in field.metadata), (
            f"No ge=0 constraint found in clear_count metadata: {field.metadata}"
        )

    def test_never_cleared_helpers(self) -> None:
        """reclear_available_at is None: not cleared, no time remaining."""
        state = VaultLocationState(
            vault_id=uuid4(),
            location_id=uuid4(),
            type=LocationTypeEnum.DISCOVERY,
        )
        now = datetime(2026, 9, 26, 12, 0, 0)
        assert state.is_cleared(now) is False
        assert state.time_remaining_seconds(now) == 0
        assert state.is_dispatchable(clearable=True, now=now) is True
        assert state.is_dispatchable(clearable=False, now=now) is False

    def test_cleared_before_available(self) -> None:
        """now < reclear_available_at: cleared, positive time remaining, not dispatchable."""
        now = datetime(2026, 9, 26, 12, 0, 0)
        state = VaultLocationState(
            vault_id=uuid4(),
            location_id=uuid4(),
            type=LocationTypeEnum.DISCOVERY,
            cleared_at=now - timedelta(hours=1),
            reclear_available_at=now + timedelta(hours=5),
            clear_count=1,
        )
        assert state.is_cleared(now) is True
        assert state.time_remaining_seconds(now) == 5 * 3600
        assert state.is_dispatchable(clearable=True, now=now) is False
        assert state.is_dispatchable(clearable=False, now=now) is False

    def test_cleared_at_available_boundary(self) -> None:
        """now == reclear_available_at: no longer cleared, zero time remaining."""
        now = datetime(2026, 9, 26, 12, 0, 0)
        state = VaultLocationState(
            vault_id=uuid4(),
            location_id=uuid4(),
            type=LocationTypeEnum.DISCOVERY,
            cleared_at=now - timedelta(hours=5),
            reclear_available_at=now,
            clear_count=1,
        )
        assert state.is_cleared(now) is False
        assert state.time_remaining_seconds(now) == 0
        assert state.is_dispatchable(clearable=True, now=now) is True

    def test_cleared_after_available(self) -> None:
        """now > reclear_available_at: available again, dispatchable when group allows."""
        now = datetime(2026, 9, 26, 12, 0, 0)
        state = VaultLocationState(
            vault_id=uuid4(),
            location_id=uuid4(),
            type=LocationTypeEnum.DISCOVERY,
            cleared_at=now - timedelta(hours=10),
            reclear_available_at=now - timedelta(hours=1),
            clear_count=2,
        )
        assert state.is_cleared(now) is False
        assert state.time_remaining_seconds(now) == 0
        assert state.is_dispatchable(clearable=True, now=now) is True
        assert state.is_dispatchable(clearable=False, now=now) is False


class TestDwellerLocationModel:
    """Happy-path and constraint tests for DwellerLocation."""

    async def test_create_and_read(self, async_session: AsyncSession) -> None:
        """Create a DwellerLocation link and read it back."""
        dweller_id = uuid4()
        location_id = uuid4()

        link = DwellerLocation(
            dweller_id=dweller_id,
            location_id=location_id,
            relation=DwellerLocationRelationEnum.VISITED,
        )
        async_session.add(link)
        await async_session.commit()
        await async_session.refresh(link)

        assert link.id is not None
        assert link.dweller_id == dweller_id
        assert link.location_id == location_id
        assert link.relation == DwellerLocationRelationEnum.VISITED

    async def test_unique_dweller_location_relation(self, async_session: AsyncSession) -> None:
        """Duplicate (dweller_id, location_id, relation) raises IntegrityError."""
        dweller_id = uuid4()
        location_id = uuid4()

        link1 = DwellerLocation(
            dweller_id=dweller_id,
            location_id=location_id,
            relation=DwellerLocationRelationEnum.VISITED,
        )
        async_session.add(link1)
        await async_session.commit()

        link2 = DwellerLocation(
            dweller_id=dweller_id,
            location_id=location_id,
            relation=DwellerLocationRelationEnum.VISITED,  # same triple
        )
        async_session.add(link2)
        with pytest.raises(IntegrityError):
            await async_session.commit()

    async def test_different_relation_allowed(self, async_session: AsyncSession) -> None:
        """Same dweller+location with different relation is allowed."""
        dweller_id = uuid4()
        location_id = uuid4()

        link1 = DwellerLocation(
            dweller_id=dweller_id,
            location_id=location_id,
            relation=DwellerLocationRelationEnum.ORIGIN,
        )
        async_session.add(link1)
        await async_session.commit()

        link2 = DwellerLocation(
            dweller_id=dweller_id,
            location_id=location_id,
            relation=DwellerLocationRelationEnum.VISITED,  # different relation
        )
        async_session.add(link2)
        await async_session.commit()  # should NOT raise


class TestLocationTypeEnum:
    """Enum value tests."""

    def test_member_names_are_uppercase(self) -> None:
        """Python member names are uppercase (PG labels match these)."""
        members = list(LocationTypeEnum)
        for member in members:
            assert member.name == member.name.upper()

    def test_member_values_are_lowercase(self) -> None:
        """Python values are lowercase."""
        assert LocationTypeEnum.ORIGIN.value == "origin"
        assert LocationTypeEnum.VISITED.value == "visited"
        assert LocationTypeEnum.DISCOVERY.value == "discovery"
        assert LocationTypeEnum.HOME_VAULT.value == "home_vault"

    def test_no_vault_member(self) -> None:
        """VAULT must not exist as a row-level type."""
        members = [m.name for m in LocationTypeEnum]
        assert "VAULT" not in members


class TestPlaceKindEnum:
    """Registry-kind enum tests."""

    def test_member_names_are_uppercase(self) -> None:
        """Python member names are uppercase (PG labels match these)."""
        for member in PlaceKindEnum:
            assert member.name == member.name.upper()

    def test_member_values_are_lowercase(self) -> None:
        """Python values are lowercase."""
        assert PlaceKindEnum.PLACE.value == "place"
        assert PlaceKindEnum.VAULT.value == "vault"
