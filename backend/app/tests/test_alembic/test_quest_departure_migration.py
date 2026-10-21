"""Recover legacy parties without releasing missions still in flight."""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import DwellerStatusEnum, GenderEnum, RarityEnum
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.team import Team, TeamMember
from app.models.vault_quest import VaultQuestCompletionLink
from app.tests.test_alembic import test_data_migrations as legacy

harness = legacy.harness
REVISION = "d9e2f4a6b801"
PARENT = "b6d8f0a2c913"


@pytest.mark.integration
def test_recovers_orphaned_questing_dwellers_and_preserves_active_parties(harness):
    harness.upgrade(PARENT)
    vault_id = UUID(legacy._seed_vault(harness, number=929))

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
            return ids
        finally:
            await engine.dispose()

    ids = asyncio.run(seed())
    harness.upgrade(REVISION)

    def assert_recovered():
        for state, dweller_id in ids.items():
            expected = (
                "QUESTING" if state in ("outbound", "returning") else "EXPLORING" if state == "exploring" else "IDLE"
            )
            assert harness.fetch("SELECT status::text, room_id FROM dweller WHERE id = :id", id=dweller_id) == [
                (expected, None)
            ]
        assert harness.scalar("SELECT COUNT(*) FROM team_member") == 6

    assert_recovered()
    harness.downgrade(PARENT)  # Recovery cannot safely be reversed.
    assert_recovered()
    harness.upgrade(REVISION)  # Re-running the data update is harmless.
    assert_recovered()
