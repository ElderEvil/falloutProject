"""Runtime coverage for data migrations: seed legacy rows, migrate for real, assert the shape.

The fragment tests in ``test_db`` pin what a migration *says*; these run it. Two migrations
shipped with defects that only review caught - a roster backfill that handed out a fourth
active place and left slot-less active rows, and an outfit backfill whose guard was never
exercised - so each case seeds the legacy state, upgrades, and asserts the migrated shape
before reversing the migration and asserting the inverse.

Every case runs in its own scratch database: a real upgrade chain is destructive, and the
application database must never be the subject.
"""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

pytestmark = pytest.mark.integration

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"

HAZARD_PARENT = "b7c8d9e0f1a2"
HAZARD_REVISION = "c9d8e7f6a5b4"
OUTFIT_PARENT = "f6e5d4c3b2a1"
OUTFIT_REVISION = "b7c8d9e0f1a2"

#: Every dweller column that has no server default at this revision, plus the flags the
#: assertions read. Plain literal (no interpolation) so the statement stays parameterised.
_INSERT_DWELLER = (
    "INSERT INTO dweller ("
    "id, vault_id, first_name, is_adult, age_group, gender, rarity, level, experience, "
    "max_health, health, radiation, happiness, stimpack, radaway, status, is_deleted, "
    "strength, perception, endurance, charisma, intelligence, agility, luck"
    ") VALUES ("
    ":id, :vault_id, :first_name, true, 'ADULT', 'MALE', 'COMMON', 1, 0, "
    "100, 100, 0, 50, 0, 0, :status, false, "
    "1, 1, 1, 1, 1, 1, 1"
    ")"
)


async def _run_sql(url: str, sql: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


class MigrationHarness:
    """Apply real migrations against a scratch database and read the result."""

    def __init__(self, url: str) -> None:
        self.url = url

    def upgrade(self, revision: str) -> None:
        self._alembic(command.upgrade, revision)

    def downgrade(self, revision: str) -> None:
        self._alembic(command.downgrade, revision)

    def execute(self, sql: str, **params: object) -> None:
        asyncio.run(self._run(sql, params, fetch=False))

    def fetch(self, sql: str, **params: object) -> list[tuple]:
        return asyncio.run(self._run(sql, params, fetch=True))

    def scalar(self, sql: str, **params: object) -> object:
        rows = self.fetch(sql, **params)
        return rows[0][0] if rows else None

    @staticmethod
    def _alembic(action, revision: str) -> None:
        config = Config()
        config.set_main_option("script_location", str(ALEMBIC_DIR))
        action(config, revision)

    async def _run(self, sql: str, params: dict, *, fetch: bool):
        engine = create_async_engine(self.url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                return [tuple(row) for row in result] if fetch else []
        finally:
            await engine.dispose()


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[MigrationHarness]:
    """A scratch database with the app's own credentials; dropped afterwards."""
    if make_url(str(settings.ASYNC_DATABASE_URI)).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping the migration harness")

    app_url = str(settings.ASYNC_DATABASE_URI)
    base_url = make_url(app_url)
    name = f"fallout_migration_test_{uuid.uuid4().hex[:12]}"
    # str(URL) renders the password as ***, which authenticates as the literal password.
    scratch_url = base_url.set(database=name).render_as_string(hide_password=False)

    try:
        asyncio.run(_run_sql(app_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        asyncio.run(_run_sql(app_url, f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # broad by design: any connection problem means "no database here"
        pytest.skip(f"PostgreSQL unavailable: {exc}")

    monkeypatch.setattr(settings, "ASYNC_DATABASE_URI", scratch_url)
    try:
        yield MigrationHarness(scratch_url)
    finally:
        asyncio.run(_run_sql(app_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def _seed_vault(harness: MigrationHarness, *, number: int) -> str:
    user_id = str(uuid.uuid4())
    vault_id = str(uuid.uuid4())
    harness.execute(
        'INSERT INTO "user" (id, username, hashed_password, is_active, is_superuser, email_verified, is_deleted) '
        "VALUES (:id, :username, 'x', true, false, true, false)",
        id=user_id,
        username=f"migration-{user_id[:8]}",
    )
    harness.execute(
        "INSERT INTO vault (id, user_id, number, bottle_caps, happiness, power, power_max, food, food_max, water, water_max) "
        "VALUES (:id, :user_id, :number, 0, 50, 0, 100, 0, 100, 0, 100)",
        id=vault_id,
        user_id=user_id,
        number=number,
    )
    return vault_id


def _seed_dweller(harness: MigrationHarness, *, vault_id: str, first_name: str, is_dead: bool) -> str:
    dweller_id = str(uuid.uuid4())
    harness.execute(
        _INSERT_DWELLER,
        id=dweller_id,
        vault_id=vault_id,
        first_name=first_name,
        status="DEAD" if is_dead else "IDLE",
    )
    return dweller_id


class TestHazardConsolidationMigration:
    """The earned rosters move onto team/team_member without breaking the roster invariant."""

    def test_backfills_without_exceeding_the_roster_or_stranding_a_slot(self, harness: MigrationHarness) -> None:
        harness.upgrade(HAZARD_PARENT)
        vault_id = _seed_vault(harness, number=901)

        living = [_seed_dweller(harness, vault_id=vault_id, first_name=f"Living{i}", is_dead=False) for i in range(4)]
        fallen = _seed_dweller(harness, vault_id=vault_id, first_name="Fallen", is_dead=True)

        # Four living active members exceed the three-place roster, and the fallen one holds
        # an active place that a revival would count as a responder.
        for index, dweller_id in enumerate([*living, fallen]):
            harness.execute(
                "INSERT INTO hazard_team_member (id, vault_id, dweller_id, team, status, created_at, updated_at) "
                "VALUES (:id, :vault_id, :dweller_id, 'FIRE', 'active', :created_at, :created_at)",
                id=str(uuid.uuid4()),
                vault_id=vault_id,
                dweller_id=dweller_id,
                created_at=datetime(2026, 1, index + 1),
            )

        harness.upgrade(HAZARD_REVISION)

        rows = harness.fetch(
            "SELECT tm.dweller_id::text, tm.slot_number, tm.status FROM team_member tm "
            "JOIN team t ON t.id = tm.team_id WHERE t.vault_id = :vault_id AND t.hazard_team = 'FIRE'",
            vault_id=vault_id,
        )
        by_dweller = {row[0]: (row[1], row[2]) for row in rows}
        assert len(by_dweller) == 5

        # The three most senior living members hold the places; the fourth is benched.
        assert by_dweller[living[0]] == (1, "active")
        assert by_dweller[living[1]] == (2, "active")
        assert by_dweller[living[2]] == (3, "active")
        assert by_dweller[living[3]] == (None, "reserve")
        # A fallen member must not keep an active place either.
        assert by_dweller[fallen] == (None, "reserve")

        assert (
            harness.scalar(
                "SELECT count(*) FROM team_member tm JOIN team t ON t.id = tm.team_id "
                "WHERE t.hazard_team IS NOT NULL AND tm.slot_number IS NOT NULL AND tm.slot_number NOT IN (1, 2, 3)"
            )
            == 0
        )
        assert (
            harness.scalar(
                "SELECT count(*) FROM team WHERE vault_id = :vault_id AND hazard_team = 'FIRE'", vault_id=vault_id
            )
            == 1
        )
        # Seniority and history survive the move.
        assert harness.scalar(
            "SELECT min(tm.created_at)::text FROM team_member tm JOIN team t ON t.id = tm.team_id WHERE t.vault_id = :vault_id",
            vault_id=vault_id,
        ).startswith("2026-01-01")

    def test_downgrade_restores_the_legacy_rows(self, harness: MigrationHarness) -> None:
        harness.upgrade(HAZARD_PARENT)
        vault_id = _seed_vault(harness, number=902)
        dweller_id = _seed_dweller(harness, vault_id=vault_id, first_name="Solo", is_dead=False)
        harness.execute(
            "INSERT INTO hazard_team_member (id, vault_id, dweller_id, team, status, created_at, updated_at) "
            "VALUES (:id, :vault_id, :dweller_id, 'RADIATION', 'reserve', now(), now())",
            id=str(uuid.uuid4()),
            vault_id=vault_id,
            dweller_id=dweller_id,
        )

        harness.upgrade(HAZARD_REVISION)
        harness.downgrade(HAZARD_PARENT)

        assert harness.fetch(
            "SELECT team::text, status, dweller_id::text FROM hazard_team_member WHERE vault_id = :vault_id",
            vault_id=vault_id,
        ) == [("RADIATION", "reserve", dweller_id)]
        # hazard_team no longer exists at this revision; the hazard teams must be gone,
        # so every remaining team row still carries one of the two older purposes.
        assert (
            harness.scalar(
                "SELECT count(*) FROM team WHERE vault_id = :vault_id AND quest_id IS NULL AND incident_id IS NULL",
                vault_id=vault_id,
            )
            == 0
        )


class TestOutfitSpecialBackfillMigration:
    """The SPECIAL backfill fills only rows still at the all-zero default."""

    def test_fills_defaulted_rows_and_leaves_populated_ones_alone(self, harness: MigrationHarness) -> None:
        harness.upgrade(OUTFIT_PARENT)
        empty_id = str(uuid.uuid4())
        populated_id = str(uuid.uuid4())
        harness.execute(
            "INSERT INTO outfit (id, name, rarity, strength, perception, endurance, intelligence, agility, luck, charisma) "
            "VALUES (:id, 'T-51b Power Armor', 'LEGENDARY', 0, 0, 0, 0, 0, 0, 0)",
            id=empty_id,
        )
        harness.execute(
            "INSERT INTO outfit (id, name, rarity, strength) VALUES (:id, 'Metal Armor', 'RARE', 9)",
            id=populated_id,
        )

        harness.upgrade(OUTFIT_REVISION)

        assert harness.fetch(
            "SELECT strength, perception, endurance, luck FROM outfit WHERE id = :id", id=empty_id
        ) == [(3, 1, 2, 0)]
        # The all-zero guard: a row that already carries a bonus is never overwritten.
        assert harness.scalar("SELECT strength FROM outfit WHERE id = :id", id=populated_id) == 9

        harness.downgrade(OUTFIT_PARENT)

        assert harness.scalar("SELECT strength FROM outfit WHERE id = :id", id=empty_id) == 3
        assert harness.scalar("SELECT strength FROM outfit WHERE id = :id", id=populated_id) == 9
