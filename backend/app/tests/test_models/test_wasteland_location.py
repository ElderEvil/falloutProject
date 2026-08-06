"""Tests for WastelandLocation and DwellerLocation models."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.wasteland_location import (
    DwellerLocation,
    DwellerLocationRelationEnum,
    LocationTypeEnum,
    WastelandLocation,
)


class TestWastelandLocationModel:
    """Happy-path tests for WastelandLocation."""

    async def test_create_and_read(self, async_session: AsyncSession) -> None:
        """Create a WastelandLocation, persist, and read it back."""
        location = WastelandLocation(
            vault_id=uuid4(),
            name="Red Rocket",
            normalized_name="red_rocket",
            type=LocationTypeEnum.DISCOVERY,
            coord_x=42.5,
            coord_y=73.1,
            description="A pre-war gas station.",
        )
        async_session.add(location)
        await async_session.commit()
        await async_session.refresh(location)

        assert location.id is not None
        assert location.name == "Red Rocket"
        assert location.normalized_name == "red_rocket"
        assert location.type == LocationTypeEnum.DISCOVERY
        assert location.coord_x == 42.5
        assert location.coord_y == 73.1
        assert location.description == "A pre-war gas station."
        assert location.exploration_id is None

    async def test_enum_round_trip(self, async_session: AsyncSession) -> None:
        """Enum values persist correctly through the ORM."""
        for enum_member in LocationTypeEnum:
            location = WastelandLocation(
                vault_id=uuid4(),
                name=f"test_{enum_member.value}",
                normalized_name=f"test_{enum_member.value}",
                type=enum_member,
                coord_x=10.0,
                coord_y=20.0,
            )
            async_session.add(location)
            await async_session.commit()
            await async_session.refresh(location)

            assert location.type == enum_member
            assert location.type.value == enum_member.value

    def test_coord_x_has_ge_constraint(self) -> None:
        """coord_x field must have ge=0 constraint."""
        field = WastelandLocation.model_fields["coord_x"]
        assert any(hasattr(m, "ge") and m.ge == 0 for m in field.metadata), (
            f"No ge=0 constraint found in coord_x metadata: {field.metadata}"
        )

    def test_coord_x_has_le_constraint(self) -> None:
        """coord_x field must have le=100 constraint."""
        field = WastelandLocation.model_fields["coord_x"]
        assert any(hasattr(m, "le") and m.le == 100 for m in field.metadata), (
            f"No le=100 constraint found in coord_x metadata: {field.metadata}"
        )

    def test_coord_y_has_ge_constraint(self) -> None:
        """coord_y field must have ge=0 constraint."""
        field = WastelandLocation.model_fields["coord_y"]
        assert any(hasattr(m, "ge") and m.ge == 0 for m in field.metadata), (
            f"No ge=0 constraint found in coord_y metadata: {field.metadata}"
        )

    def test_coord_y_has_le_constraint(self) -> None:
        """coord_y field must have le=100 constraint."""
        field = WastelandLocation.model_fields["coord_y"]
        assert any(hasattr(m, "le") and m.le == 100 for m in field.metadata), (
            f"No le=100 constraint found in coord_y metadata: {field.metadata}"
        )

    async def test_coord_x_edge_100(self, async_session: AsyncSession) -> None:
        """coord_x=100 is valid."""
        location = WastelandLocation(
            vault_id=uuid4(),
            name="edge",
            normalized_name="edge_100",
            type=LocationTypeEnum.DISCOVERY,
            coord_x=100.0,
            coord_y=100.0,
        )
        async_session.add(location)
        await async_session.commit()

    async def test_unique_vault_normalized_name(self, async_session: AsyncSession) -> None:
        """Duplicate (vault_id, normalized_name) raises IntegrityError."""
        vault_id = uuid4()
        loc1 = WastelandLocation(
            vault_id=vault_id,
            name="Sanctuary Hills",
            normalized_name="sanctuary_hills",
            type=LocationTypeEnum.ORIGIN,
            coord_x=10.0,
            coord_y=20.0,
        )
        async_session.add(loc1)
        await async_session.commit()

        loc2 = WastelandLocation(
            vault_id=vault_id,
            name="Sanctuary Hills Copy",
            normalized_name="sanctuary_hills",  # same vault_id + same normalized_name
            type=LocationTypeEnum.VISITED,
            coord_x=30.0,
            coord_y=40.0,
        )
        async_session.add(loc2)
        with pytest.raises(IntegrityError):
            await async_session.commit()


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
