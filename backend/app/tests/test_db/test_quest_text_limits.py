"""Quest text length contract: seeder output must round-trip the read schema.

The catalog grew past the original VARCHAR(255)/(64) limits and PostgreSQL
enforced them at seed time while SQLite silently did not, so the suite stayed
green while production crashed on boot. The PostgreSQL round-trip skips when
no live server is available; the catalog-level check runs everywhere.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.quest import Quest
from app.schemas.quest import QuestRead
from app.utils.load_quests import load_all_quest_chain_files
from app.utils.seed_quests import seed_quests_from_json


def _quest_read_payload(quest: Quest) -> dict:
    return {
        "id": quest.id,
        "title": quest.title,
        "short_description": quest.short_description,
        "long_description": quest.long_description,
        "requirements": quest.requirements,
        "rewards": quest.rewards,
        "quest_type": quest.quest_type,
        "quest_category": quest.quest_category,
        "chain_id": quest.chain_id,
        "chain_order": quest.chain_order,
        "duration_minutes": quest.duration_minutes,
    }


def test_all_authored_quest_texts_fit_schema_limits() -> None:
    """Every quest text in the JSON catalog must satisfy QuestBase's Field limits.

    Runs everywhere (no DB needed): validates the catalog the way the seeder
    persists it, so Pydantic raises before PostgreSQL ever sees the row.
    """
    for chain in load_all_quest_chain_files():
        for quest in chain.quests:
            assert len(quest.short_description) <= 128, f"{quest.quest_name}: short_description over 128"
            assert len(quest.long_description) <= 500, f"{quest.quest_name}: long_description over 500"
            requirements = quest.requirements if isinstance(quest.requirements, str) else ""
            requirements = requirements or "No prerequisites"
            assert len(requirements) <= 500, f"{quest.quest_name}: requirements over 500"
            assert len(quest.rewards) <= 500, f"{quest.quest_name}: rewards over 500"
            rewards = quest.rewards or "None"

            QuestRead.model_validate(
                {
                    "id": "00000000-0000-4000-8000-000000000000",
                    "title": quest.quest_name,
                    "short_description": quest.short_description,
                    "long_description": quest.long_description,
                    "requirements": requirements,
                    "rewards": rewards,
                    "quest_type": quest.quest_type or "side",
                    "quest_category": quest.quest_category,
                    "chain_id": chain.chain_id,
                    "chain_order": quest.chain_order,
                    "duration_minutes": quest.duration_minutes,
                }
            )


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to live PostgreSQL (schema migrated), skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping quest seed round-trip")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seeder_round_trips_full_catalog_through_postgres(live_pg_engine: AsyncEngine) -> None:
    """Seed the real catalog through PostgreSQL and read every row back through QuestRead.

    Fails under the pre-fix schema with StringDataRightTruncationError (seeder)
    or a Pydantic string_too_long ValidationError (read path) — the exact
    production failure mode SQLite cannot reproduce. Assumes migrations are
    applied (CI applies them before the suite; run `alembic upgrade head` on a
    scratch DB locally).

    The session class must be SQLModel's, not the raw SQLAlchemy one the app's
    tick path uses: the seeder issues ``.exec()``, which only SQLModel adds.

    Seeding runs twice: production re-seeds on every boot, so the second pass
    exercises the existing-quest sync path. A fresh database only ever runs the
    create path, which is how the sync path was able to blank ``rewards`` for the
    24 catalog quests that carry no authored "Rewards" text.
    """
    session_factory = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        for _pass_number in (1, 2):
            await seed_quests_from_json(session, quest_dir=Path(__file__).parents[2] / "data" / "quests")
            await session.commit()

        rows = (await session.execute(select(Quest))).scalars().all()
        assert len(rows) >= 35, f"expected the full catalog, got {len(rows)} quests"

        for quest in rows:
            QuestRead.model_validate(_quest_read_payload(quest))
