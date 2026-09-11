"""PostgreSQL integration checks for the phase-1 world-place registry migration.

Skips unless a live PostgreSQL database is configured and reachable (the default
CI suite is SQLite-backed), mirroring ``test_enum_drift``'s live-PG fixture.
Read-only: asserts the backfill parity invariants and the additive-only contract
on the migrated database.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping registry migration check")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    return engine


async def _scalar(engine: AsyncEngine, sql: str) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql))).scalar_one()


class TestWorldPlaceRegistryMigration:
    """The backfill must preserve every row and keep the old schema intact."""

    @pytest.mark.asyncio
    async def test_new_tables_exist(self, live_pg_engine: AsyncEngine) -> None:
        tables = {
            row[0]
            for row in (
                await _scalar_all(
                    live_pg_engine,
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
                )
            )
        }
        assert {"worldlocation", "vaultlocationstate"} <= tables, (
            f"Registry tables missing (run `uv run alembic upgrade head`): {sorted(tables)}"
        )

    @pytest.mark.asyncio
    async def test_backfill_row_count_parity(self, live_pg_engine: AsyncEngine) -> None:
        old_rows = await _scalar(live_pg_engine, "SELECT count(*) FROM wastelandlocation")
        state_rows = await _scalar(live_pg_engine, "SELECT count(*) FROM vaultlocationstate")
        registry_rows = await _scalar(live_pg_engine, "SELECT count(*) FROM worldlocation")
        distinct_names = await _scalar(live_pg_engine, "SELECT count(DISTINCT normalized_name) FROM worldlocation")

        assert state_rows == old_rows, "every wastelandlocation row must map to exactly one state row"
        assert registry_rows == distinct_names, "registry must be deduped on normalized_name"
        assert registry_rows <= old_rows, "registry cannot exceed the source row count"

    @pytest.mark.asyncio
    async def test_home_markers_pinned_and_coords_on_grid(self, live_pg_engine: AsyncEngine) -> None:
        bad_home = await _scalar(
            live_pg_engine,
            "SELECT count(*) FROM worldlocation WHERE kind = 'VAULT' AND (coord_x <> 50.0 OR coord_y <> 50.0)",
        )
        out_of_range = await _scalar(
            live_pg_engine,
            "SELECT count(*) FROM worldlocation WHERE coord_x < 0 OR coord_x > 100 OR coord_y < 0 OR coord_y > 100",
        )
        assert bad_home == 0, "vault-kind registry rows must sit at (50, 50)"
        assert out_of_range == 0, "registry coordinates must stay on the 0-100 grid"

    @pytest.mark.asyncio
    async def test_place_coordinates_are_unique(self, live_pg_engine: AsyncEngine) -> None:
        duplicates = await _scalar(
            live_pg_engine,
            "SELECT count(*) FROM ("
            "  SELECT coord_x, coord_y FROM worldlocation WHERE kind = 'PLACE'"
            "  GROUP BY coord_x, coord_y HAVING count(*) > 1"
            ") duplicated",
        )
        assert duplicates == 0, "registry-level collision nudge must keep place coordinates unique"

    @pytest.mark.asyncio
    async def test_phase1_leaves_dwellerlocation_fk_on_old_table(self, live_pg_engine: AsyncEngine) -> None:
        async with live_pg_engine.connect() as conn:
            fk_target = (
                await conn.execute(
                    text(
                        """
                        SELECT confrelid::regclass::text
                        FROM pg_constraint
                        WHERE conrelid = 'dwellerlocation'::regclass
                          AND contype = 'f'
                          AND conkey = ARRAY[
                              (SELECT attnum FROM pg_attribute
                               WHERE attrelid = 'dwellerlocation'::regclass AND attname = 'location_id')
                          ]
                        """
                    )
                )
            ).scalar_one()
        assert fk_target == "wastelandlocation", (
            "phase 1 is additive only; the dwellerlocation FK is repointed in phase 2"
        )


async def _scalar_all(engine: AsyncEngine, sql: str) -> list:
    async with engine.connect() as conn:
        return list((await conn.execute(text(sql))).all())
