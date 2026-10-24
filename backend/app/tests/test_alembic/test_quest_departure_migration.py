"""Recover legacy parties without releasing missions still in flight."""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import DwellerStatusEnum, GenderEnum, RarityEnum
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.team import Team, TeamMember
from app.models.vault_quest import VaultQuestCompletionLink
from app.tests.factory.rooms import create_overseers_office
from app.tests.test_alembic import test_data_migrations as legacy

harness = legacy.harness
REVISION = "d9e2f4a6b801"
PARENT = "b6d8f0a2c913"


@pytest.mark.integration
def test_recovers_orphaned_questing_dwellers_and_preserves_active_parties(harness):
    harness.upgrade(PARENT)
    vault_id = UUID(legacy._seed_vault(harness, number=929))
    office = create_overseers_office()
    room_id = str(uuid4())
    now = datetime.utcnow()
    harness.execute(
        "INSERT INTO room (id, vault_id, name, category, ability, base_cost, tier, size_min, size_max, size, "
        "speedup_multiplier, created_at, updated_at) "
        "VALUES (:id, :vault_id, :name, :category, :ability, :base_cost, :tier, :size_min, :size_max, :size, "
        "1.0, :created_at, :updated_at)",
        id=room_id,
        vault_id=str(vault_id),
        name=office["name"],
        category=office["category"].name,
        ability=None,
        base_cost=office["base_cost"],
        tier=office["tier"],
        size_min=office["size_min"],
        size_max=office["size_max"],
        size=office["size"],
        created_at=now,
        updated_at=now,
    )

    async def seed():
        engine = create_async_engine(harness.url)
        ids = {}
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                for state in (
                    "orphan",
                    "unlinked",
                    "unstarted",
                    "outbound",
                    "returning",
                    "ready",
                    "completed",
                    "exploring",
                ):
                    dweller = Dweller(
                        first_name=state,
                        vault_id=vault_id,
                        gender=GenderEnum.MALE,
                        rarity=RarityEnum.COMMON,
                        status=DwellerStatusEnum.EXPLORING if state == "exploring" else DwellerStatusEnum.QUESTING,
                        room_id=UUID(room_id) if state in ("orphan", "outbound") else None,
                    )
                    db.add(dweller)
                    await db.flush()
                    ids[state] = str(dweller.id)
                    if state in ("orphan", "exploring"):
                        continue
                    quest = Quest(
                        title=state,
                        short_description="Legacy party",
                        long_description="Recovery fixture",
                        requirements="None",
                        rewards="None",
                        duration_minutes=60,
                    )
                    db.add(quest)
                    await db.flush()
                    team = Team(vault_id=vault_id, quest_id=quest.id)
                    db.add(team)
                    await db.flush()
                    db.add(TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"))
                    if state != "unlinked":
                        db.add(
                            VaultQuestCompletionLink(
                                vault_id=vault_id,
                                quest_id=quest.id,
                                started_at=None if state == "unstarted" else datetime.utcnow() - timedelta(hours=1),
                                return_completes_at=datetime.utcnow() + timedelta(minutes=10)
                                if state == "returning"
                                else None,
                                is_reward_ready=state == "ready",
                                is_completed=state == "completed",
                            )
                        )
                await db.commit()
            return ids, room_id
        finally:
            await engine.dispose()

    ids, room_id = asyncio.run(seed())
    harness.upgrade(REVISION)

    def assert_recovered():
        for state, dweller_id in ids.items():
            expected = (
                "QUESTING" if state in ("outbound", "returning") else "EXPLORING" if state == "exploring" else "IDLE"
            )
            assert harness.fetch("SELECT status::text, room_id::text FROM dweller WHERE id = :id", id=dweller_id) == [
                (expected, room_id if state == "outbound" else None)
            ]
        assert harness.scalar("SELECT COUNT(*) FROM team_member") == 6

    assert_recovered()
    harness.downgrade(PARENT)  # Recovery cannot safely be reversed.
    assert_recovered()
    harness.upgrade(REVISION)  # Re-running the data update is harmless.
    assert_recovered()
