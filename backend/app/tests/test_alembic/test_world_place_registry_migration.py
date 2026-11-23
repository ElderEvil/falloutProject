import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_plugins = ["app.tests.test_alembic._support"]


async def _rows(engine: AsyncEngine, sql: str) -> list:
    async with engine.connect() as conn:
        return list((await conn.execute(text(sql))).all())


async def _scalar(engine: AsyncEngine, sql: str) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql))).scalar_one()


async def _tables(engine: AsyncEngine) -> set[str]:
    return {row[0] for row in await _rows(engine, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}


class TestWorldPlaceRegistryMigration:
    async def test_new_tables_exist(self, live_pg_engine: AsyncEngine) -> None:
        tables = await _tables(live_pg_engine)
        assert {"worldlocation", "vaultlocationstate"} <= tables, (
            f"Registry tables missing (run `uv run alembic upgrade head`): {sorted(tables)}"
        )

    async def test_old_table_dropped_and_fk_repointed(self, live_pg_engine: AsyncEngine) -> None:
        assert "wastelandlocation" not in await _tables(live_pg_engine), "phase 2 drops the retired per-vault table"
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

    async def test_home_markers_placed_on_grid(self, live_pg_engine: AsyncEngine) -> None:
        off_grid = await _scalar(
            live_pg_engine,
            "SELECT count(*) FROM worldlocation WHERE kind = 'VAULT' "
            "AND (coord_x < 0 OR coord_x > 100 OR coord_y < 0 OR coord_y > 100)",
        )
        assert off_grid == 0, "vault-kind registry rows must stay on the 0-100 grid"

    async def test_every_home_state_maps_to_a_vault_registry_row(self, live_pg_engine: AsyncEngine) -> None:
        mismatched = await _scalar(
            live_pg_engine,
            """
            SELECT count(*)
            FROM vaultlocationstate s
            JOIN vault v ON v.id = s.vault_id
            JOIN worldlocation gl ON gl.id = s.location_id
            WHERE s.type = 'HOME_VAULT'
              AND NOT (gl.kind = 'VAULT' AND gl.vault_number = v.number)
            """,
        )
        assert mismatched == 0, "every HOME_VAULT state must sit on a VAULT registry row with its vault number"

    async def test_place_coordinates_are_unique(self, live_pg_engine: AsyncEngine) -> None:
        duplicates = await _scalar(
            live_pg_engine,
            "SELECT count(*) FROM ("
            "  SELECT coord_x, coord_y FROM worldlocation WHERE kind = 'PLACE'"
            "  GROUP BY coord_x, coord_y HAVING count(*) > 1"
            ") duplicated",
        )
        assert duplicates == 0, "registry-level collision nudge must keep place coordinates unique"
