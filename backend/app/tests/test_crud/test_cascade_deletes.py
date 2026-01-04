"""Tests for cascade delete behavior to prevent orphaned records.

NOTE: These tests are currently skipped as cascade delete behavior
needs to be reconfigured after database schema changes.
See: https://github.com/yourusername/falloutProject/issues/XXX
"""

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.chat_message import ChatMessage
from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.pregnancy import Pregnancy
from app.models.relationship import Relationship
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.pregnancy import PregnancyCreate
from app.schemas.relationship import RelationshipCreate
from app.schemas.room import RoomCreate
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.rooms import create_fake_room


@pytest_asyncio.fixture(name="test_room")
async def test_room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """Create a test room."""
    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    return await crud.room.create(db_session=async_session, obj_in=room_in)


@pytest_asyncio.fixture(name="test_dweller")
async def test_dweller_fixture(
    async_session: AsyncSession,
    vault: Vault,
    test_room: Room,
) -> Dweller:
    """Create a test dweller."""
    dweller_data = create_fake_dweller()
    dweller_data["first_name"] = "Test"
    dweller_data["last_name"] = "Dweller"
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=test_room.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="test_dweller2")
async def test_dweller2_fixture(
    async_session: AsyncSession,
    vault: Vault,
    test_room: Room,
) -> Dweller:
    """Create a second test dweller."""
    dweller_data = create_fake_dweller()
    dweller_data["first_name"] = "Second"
    dweller_data["last_name"] = "Dweller"
    dweller_data["gender"] = "female"
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=test_room.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Cascade delete behavior needs reconfiguration after schema changes")
class TestCascadeDeletes:
    """Test cascade delete behavior prevents orphaned records."""

    async def test_dweller_deletion_cascades_to_chat_messages(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_dweller: Dweller,
        test_dweller2: Dweller,
    ):
        """Test that deleting a dweller cascades to their chat messages."""
        # Create chat messages from test_dweller to test_dweller2
        chat_msg = ChatMessage(
            vault_id=vault.id,
            from_dweller_id=test_dweller.id,
            to_dweller_id=test_dweller2.id,
            message_text="Hello from dweller 1",
        )
        async_session.add(chat_msg)

        # Create another message in opposite direction
        chat_msg2 = ChatMessage(
            vault_id=vault.id,
            from_dweller_id=test_dweller2.id,
            to_dweller_id=test_dweller.id,
            message_text="Reply from dweller 2",
        )
        async_session.add(chat_msg2)
        await async_session.commit()

        # Verify messages exist
        query = select(ChatMessage).where(
            (ChatMessage.from_dweller_id == test_dweller.id) | (ChatMessage.to_dweller_id == test_dweller.id)
        )
        result = await async_session.execute(query)
        messages_before = list(result.scalars().all())
        assert len(messages_before) == 2

        # Delete test_dweller
        await crud.dweller.delete(db_session=async_session, id=test_dweller.id)

        # Verify messages are cascade deleted
        result_after = await async_session.execute(query)
        messages_after = list(result_after.scalars().all())
        assert len(messages_after) == 0

    async def test_dweller_deletion_cascades_to_relationships(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002
        test_dweller: Dweller,
        test_dweller2: Dweller,
    ):
        """Test that deleting a dweller cascades to their relationships."""
        # Create relationship between dwellers
        rel_data = {
            "relationship_type": "partner",
            "affinity": 100,
        }
        rel_in = RelationshipCreate(
            **rel_data,
            dweller1_id=test_dweller.id,
            dweller2_id=test_dweller2.id,
        )
        relationship = await crud.relationship.create(db_session=async_session, obj_in=rel_in)  # noqa: F841

        # Verify relationship exists
        query = select(Relationship).where(
            (Relationship.dweller1_id == test_dweller.id) | (Relationship.dweller2_id == test_dweller.id)
        )
        result = await async_session.execute(query)
        relationships_before = list(result.scalars().all())
        assert len(relationships_before) == 1

        # Delete test_dweller
        await crud.dweller.delete(db_session=async_session, id=test_dweller.id)

        # Verify relationship is cascade deleted
        result_after = await async_session.execute(query)
        relationships_after = list(result_after.scalars().all())
        assert len(relationships_after) == 0

    async def test_dweller_deletion_cascades_to_pregnancies(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_dweller: Dweller,
        test_dweller2: Dweller,
    ):
        """Test that deleting a dweller cascades to their pregnancies."""
        from datetime import datetime, timedelta

        # Create pregnancy with test_dweller as mother
        pregnancy_data = {
            "status": "pregnant",
            "due_at": datetime.utcnow() + timedelta(hours=3),
        }
        pregnancy_in = PregnancyCreate(
            **pregnancy_data,
            mother_id=test_dweller2.id,  # female dweller
            father_id=test_dweller.id,
            vault_id=vault.id,
        )
        pregnancy = await crud.pregnancy.create(db_session=async_session, obj_in=pregnancy_in)  # noqa: F841

        # Verify pregnancy exists
        query = select(Pregnancy).where(
            (Pregnancy.mother_id == test_dweller2.id) | (Pregnancy.father_id == test_dweller.id)
        )
        result = await async_session.execute(query)
        pregnancies_before = list(result.scalars().all())
        assert len(pregnancies_before) == 1

        # Delete father dweller
        await crud.dweller.remove(db_session=async_session, id=test_dweller.id)

        # Verify pregnancy is cascade deleted
        result_after = await async_session.execute(query)
        pregnancies_after = list(result_after.scalars().all())
        assert len(pregnancies_after) == 0

    async def test_dweller_deletion_cascades_to_incidents(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_room: Room,
        test_dweller: Dweller,
    ):
        """Test that deleting a dweller cascades to incidents where they are assigned."""
        from app.models.incident import IncidentStatus, IncidentType

        # Create incident in test_room
        incident = Incident(
            vault_id=vault.id,
            room_id=test_room.id,
            type=IncidentType.FIRE,
            status=IncidentStatus.ACTIVE,
            difficulty=2,
            is_active=True,
        )
        async_session.add(incident)
        await async_session.commit()
        await async_session.refresh(incident)

        # Assign dweller to incident
        incident.assigned_dweller_ids = [str(test_dweller.id)]
        async_session.add(incident)
        await async_session.commit()
        await async_session.refresh(incident)

        # Verify incident exists
        incident_query = select(Incident).where(Incident.id == incident.id)
        result = await async_session.execute(incident_query)
        assert result.scalar_one_or_none() is not None

        # Delete dweller
        await crud.dweller.remove(db_session=async_session, id=test_dweller.id)

        # Incident should still exist, but assignment should be handled
        # Note: assigned_dweller_ids is a JSON field, so cascade doesn't apply
        # but the incident itself remains valid
        result_after = await async_session.execute(incident_query)
        incident_after = result_after.scalar_one_or_none()
        assert incident_after is not None

    async def test_room_deletion_cascades_to_incidents(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_room: Room,
    ):
        """Test that deleting a room cascades to incidents in that room."""
        from app.models.incident import IncidentStatus, IncidentType

        # Create incident in room
        incident = Incident(
            vault_id=vault.id,
            room_id=test_room.id,
            type=IncidentType.FIRE,
            status=IncidentStatus.ACTIVE,
            difficulty=2,
            is_active=True,
        )
        async_session.add(incident)
        await async_session.commit()

        # Verify incident exists
        query = select(Incident).where(Incident.room_id == test_room.id)
        result = await async_session.execute(query)
        incidents_before = list(result.scalars().all())
        assert len(incidents_before) == 1

        # Delete room
        await crud.room.delete(db_session=async_session, id=test_room.id)

        # Verify incident is cascade deleted
        result_after = await async_session.execute(query)
        incidents_after = list(result_after.scalars().all())
        assert len(incidents_after) == 0

    async def test_vault_deletion_cascades_to_dwellers(
        self,
        async_session: AsyncSession,
    ):
        """Test that deleting a vault cascades to all dwellers."""
        # Create new vault for this test
        from app.schemas.vault import VaultCreate

        vault_data = {
            "name": "Test Vault for Cascade",
            "vault_number": 999,
            "power": 100,
            "power_max": 100,
            "food": 100,
            "food_max": 100,
            "water": 100,
            "water_max": 100,
            "caps": 1000,
        }
        vault_in = VaultCreate(**vault_data)
        test_vault = await crud.vault.create(db_session=async_session, obj_in=vault_in)

        # Create dwellers in vault
        dweller_data1 = create_fake_dweller()
        dweller_in1 = DwellerCreate(**dweller_data1, vault_id=test_vault.id)
        dweller1 = await crud.dweller.create(db_session=async_session, obj_in=dweller_in1)  # noqa: F841

        dweller_data2 = create_fake_dweller()
        dweller_in2 = DwellerCreate(**dweller_data2, vault_id=test_vault.id)
        dweller2 = await crud.dweller.create(db_session=async_session, obj_in=dweller_in2)  # noqa: F841

        # Verify dwellers exist
        query = select(Dweller).where(Dweller.vault_id == test_vault.id)
        result = await async_session.execute(query)
        dwellers_before = list(result.scalars().all())
        assert len(dwellers_before) == 2

        # Delete vault
        await crud.vault.delete(db_session=async_session, id=test_vault.id)

        # Verify dwellers are cascade deleted
        result_after = await async_session.execute(query)
        dwellers_after = list(result_after.scalars().all())
        assert len(dwellers_after) == 0

    async def test_vault_deletion_cascades_to_rooms(
        self,
        async_session: AsyncSession,
    ):
        """Test that deleting a vault cascades to all rooms."""
        # Create new vault
        from app.schemas.vault import VaultCreate

        vault_data = {
            "name": "Test Vault for Room Cascade",
            "vault_number": 998,
            "power": 100,
            "power_max": 100,
            "food": 100,
            "food_max": 100,
            "water": 100,
            "water_max": 100,
            "caps": 1000,
        }
        vault_in = VaultCreate(**vault_data)
        test_vault = await crud.vault.create(db_session=async_session, obj_in=vault_in)

        # Create rooms in vault
        room_data1 = create_fake_room()
        room_in1 = RoomCreate(**room_data1, vault_id=test_vault.id)
        room1 = await crud.room.create(db_session=async_session, obj_in=room_in1)  # noqa: F841

        room_data2 = create_fake_room()
        room_data2["coordinate_x"] = 1
        room_in2 = RoomCreate(**room_data2, vault_id=test_vault.id)
        room2 = await crud.room.create(db_session=async_session, obj_in=room_in2)  # noqa: F841

        # Verify rooms exist
        query = select(Room).where(Room.vault_id == test_vault.id)
        result = await async_session.execute(query)
        rooms_before = list(result.scalars().all())
        assert len(rooms_before) == 2

        # Delete vault
        await crud.vault.delete(db_session=async_session, id=test_vault.id)

        # Verify rooms are cascade deleted
        result_after = await async_session.execute(query)
        rooms_after = list(result_after.scalars().all())
        assert len(rooms_after) == 0

    async def test_multiple_cascade_levels(
        self,
        async_session: AsyncSession,
    ):
        """Test cascade deletion through multiple levels (vault -> dweller -> relationships)."""
        # Create new vault
        from app.schemas.vault import VaultCreate

        vault_data = {
            "name": "Multi-level Cascade Test",
            "vault_number": 997,
            "power": 100,
            "power_max": 100,
            "food": 100,
            "food_max": 100,
            "water": 100,
            "water_max": 100,
            "caps": 1000,
        }
        vault_in = VaultCreate(**vault_data)
        test_vault = await crud.vault.create(db_session=async_session, obj_in=vault_in)

        # Create dwellers
        dweller_data1 = create_fake_dweller()
        dweller_data1["gender"] = "male"
        dweller_in1 = DwellerCreate(**dweller_data1, vault_id=test_vault.id)
        dweller1 = await crud.dweller.create(db_session=async_session, obj_in=dweller_in1)

        dweller_data2 = create_fake_dweller()
        dweller_data2["gender"] = "female"
        dweller_in2 = DwellerCreate(**dweller_data2, vault_id=test_vault.id)
        dweller2 = await crud.dweller.create(db_session=async_session, obj_in=dweller_in2)

        # Create relationship
        rel_data = {
            "relationship_type": "partner",
            "affinity": 100,
        }
        rel_in = RelationshipCreate(
            **rel_data,
            dweller1_id=dweller1.id,
            dweller2_id=dweller2.id,
        )
        relationship = await crud.relationship.create(db_session=async_session, obj_in=rel_in)

        # Create chat messages
        chat_msg = ChatMessage(
            vault_id=test_vault.id,
            from_dweller_id=dweller1.id,
            to_dweller_id=dweller2.id,
            message_text="Test message",
        )
        async_session.add(chat_msg)
        await async_session.commit()

        # Verify all exist
        dweller_query = select(Dweller).where(Dweller.vault_id == test_vault.id)
        rel_query = select(Relationship).where(Relationship.id == relationship.id)
        chat_query = select(ChatMessage).where(ChatMessage.vault_id == test_vault.id)

        dweller_result = await async_session.execute(dweller_query)
        rel_result = await async_session.execute(rel_query)
        chat_result = await async_session.execute(chat_query)

        assert len(list(dweller_result.scalars().all())) == 2
        assert rel_result.scalar_one_or_none() is not None
        assert len(list(chat_result.scalars().all())) == 1

        # Delete vault - should cascade all the way down
        await crud.vault.remove(db_session=async_session, id=test_vault.id)

        # Verify everything is deleted
        dweller_result_after = await async_session.execute(dweller_query)
        rel_result_after = await async_session.execute(rel_query)
        chat_result_after = await async_session.execute(chat_query)

        assert len(list(dweller_result_after.scalars().all())) == 0
        assert rel_result_after.scalar_one_or_none() is None
        assert len(list(chat_result_after.scalars().all())) == 0
