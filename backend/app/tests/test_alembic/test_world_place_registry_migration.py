"""PostgreSQL integration checks for the shared world-place registry.

Skips unless a live PostgreSQL database is configured and reachable (the default
CI suite is SQLite-backed), mirroring ``test_enum_drift``'s live-PG fixture.
Read-only: asserts the registry invariants on the migrated database.
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
    async def test_old_table_dropped_and_fk_repointed(self, live_pg_engine: AsyncEngine) -> None:
        tables = {
            row[0]
            for row in (
                await _scalar_all(
                    live_pg_engine,
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
                )
            )
        }
        assert "wastelandlocation" not in tables, "phase 2 drops the retired per-vault table"
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
        assert fk_target == "worldlocation", "phase 2 repoints the dwellerlocation FK at the registry"

    @pytest.mark.asyncio
    async def test_every_state_and_link_resolves(self, live_pg_engine: AsyncEngine) -> None:
        orphan_states = await _scalar(
            live_pg_engine,
            "SELECT count(*) FROM vaultlocationstate s LEFT JOIN worldlocation gl ON gl.id = s.location_id "
            "WHERE gl.id IS NULL",
        )
        orphan_links = await _scalar(
            live_pg_engine,
            "SELECT count(*) FROM dwellerlocation dl LEFT JOIN worldlocation gl ON gl.id = dl.location_id "
            "WHERE gl.id IS NULL",
        )
        assert orphan_states == 0, "every fog state must resolve to a registry row"
        assert orphan_links == 0, "every dweller link must resolve to a registry row"

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
    async def test_every_home_state_maps_to_a_vault_registry_row(self, live_pg_engine: AsyncEngine) -> None:
        mismatched = await _scalar(
            live_pg_engine,
            """
            SELECT count(*)
            FROM vaultlocationstate s
            JOIN vault v ON v.id = s.vault_id
            JOIN worldlocation gl ON gl.id = s.location_id
            WHERE s.type = 'HOME_VAULT'
              AND NOT (gl.kind = 'VAULT' AND gl.vault_number = v.number
                       AND gl.coord_x = 50.0 AND gl.coord_y = 50.0)
            """,
        )
        assert mismatched == 0, (
            "every HOME_VAULT state must sit on a VAULT registry row with its vault number at (50, 50)"
        )

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


async def _scalar_all(engine: AsyncEngine, sql: str) -> list:
    async with engine.connect() as conn:
        return list((await conn.execute(text(sql))).all())
