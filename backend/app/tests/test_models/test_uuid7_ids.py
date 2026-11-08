"""Regression tests for the UUIDv7 id migration.

These fail if any generated id factory reverts to ``uuid4`` or if a schema/model
reintroduces ``pydantic.UUID4`` validation, which rejects v7 ids.
"""

from datetime import datetime
from uuid import UUID, uuid4, uuid7

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena_match_event import ArenaMatchEvent
from app.models.base import BaseUUIDModel
from app.models.incident_event import IncidentEvent
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward
from app.models.world_location import WorldLocation
from app.schemas.vault import VaultRead


def test_base_uuid_model_generates_v7() -> None:
    """The central id factory produces a UUIDv7."""
    assert BaseUUIDModel().id.version == 7


def test_custom_id_models_generate_v7() -> None:
    """Models that declare their own id column also default to UUIDv7."""
    quest_reward = QuestReward(quest_id=uuid7())
    quest_requirement = QuestRequirement(quest_id=uuid7())
    incident_event = IncidentEvent(incident_id=uuid7(), kind="test", message="test")
    arena_match_event = ArenaMatchEvent(room_id=uuid7(), kind="test", message="test")

    generated = [quest_reward, quest_requirement, incident_event, arena_match_event]
    assert [row.id.version for row in generated] == [7, 7, 7, 7]


async def test_v4_and_v7_ids_round_trip_through_database(async_session: AsyncSession) -> None:
    """Explicit v4 and v7 ids survive a real SQLite round trip unchanged."""
    v4_id = uuid4()
    v7_id = uuid7()

    async_session.add(WorldLocation(name="V4 Place", normalized_name="v4 place", coord_x=1.0, coord_y=2.0, id=v4_id))
    async_session.add(WorldLocation(name="V7 Place", normalized_name="v7 place", coord_x=3.0, coord_y=4.0, id=v7_id))
    await async_session.commit()

    # Drop identity-map copies so the reload below is served by the database.
    async_session.expunge_all()

    reloaded_v4 = await async_session.get(WorldLocation, v4_id)
    reloaded_v7 = await async_session.get(WorldLocation, v7_id)

    assert reloaded_v4 is not None
    assert reloaded_v7 is not None
    assert reloaded_v4.id == v4_id
    assert reloaded_v7.id == v7_id
    assert reloaded_v4.id.version == 4
    assert reloaded_v7.id.version == 7


def test_read_schema_accepts_v4_and_v7_ids() -> None:
    """A real read schema with a UUID field accepts both id versions."""
    now = datetime(2026, 1, 1, 12, 0, 0)
    payload = {"number": 42, "created_at": now, "updated_at": now}

    read_v4 = VaultRead.model_validate({**payload, "id": uuid4()})
    read_v7 = VaultRead.model_validate({**payload, "id": uuid7()})

    assert read_v4.id.version == 4
    assert read_v7.id.version == 7


def test_uuid7_burst_has_monotonic_timestamps() -> None:
    """A burst of v7 ids keeps non-decreasing 48-bit timestamps and version 7."""
    ids: list[UUID] = [uuid7() for _ in range(1_000)]

    timestamps = [value.int >> 80 for value in ids]
    assert timestamps == sorted(timestamps)
    assert all(value.version == 7 for value in ids)
