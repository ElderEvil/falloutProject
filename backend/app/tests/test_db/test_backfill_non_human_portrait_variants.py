"""Non-human portrait alternates are selected by stable dweller ID."""

import importlib.util
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_non_human_portrait_alternates(monkeypatch):
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/2026_10_25_0004-b3d7e1f5a902_backfill_non_human_portrait_variants.py"
    )
    spec = importlib.util.spec_from_file_location("non_human_portrait_alts", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    base_id = str(UUID(int=1))  # hash selects the base portrait
    alt_id = str(UUID(int=6))  # hash selects the alternate portrait
    custom_id = str(UUID(int=7))
    human_id = str(UUID(int=8))
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE dweller (id TEXT PRIMARY KEY, age_group TEXT, gender TEXT, "
            "visual_attributes TEXT, image_url TEXT, thumbnail_url TEXT)"
        )
        rows = [
            (
                base_id,
                "ADULT",
                "male",
                '{"race":"ghoul","state_of_being":"sane"}',
                "/static/dweller_images/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
                "/static/dweller_thumbnails/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
            ),
            (
                alt_id,
                "ADULT",
                "male",
                '{"race":"ghoul","state_of_being":"sane"}',
                "/static/dweller_images/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
                "/static/dweller_thumbnails/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
            ),
            (
                custom_id,
                "ADULT",
                "female",
                '{"race":"ghoul","state_of_being":"sane"}',
                "https://cdn.example/custom.png",
                "https://cdn.example/custom-thumb.png",
            ),
            (
                human_id,
                "ADULT",
                "male",
                '{"race":"human"}',
                "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp",
                "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp",
            ),
        ]
        connection.exec_driver_sql("INSERT INTO dweller VALUES (?, ?, ?, ?, ?, ?)", rows[0])
        for row in rows[1:]:
            connection.exec_driver_sql("INSERT INTO dweller VALUES (?, ?, ?, ?, ?, ?)", row)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        result = {
            row[0]: (row[1], row[2])
            for row in connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller").all()
        }
        assert result[base_id] == (
            "/static/dweller_images/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
            "/static/dweller_thumbnails/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
        )
        assert result[alt_id] == (
            "/static/dweller_images/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp",
            "/static/dweller_thumbnails/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp",
        )
        assert result[custom_id] == ("https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png")
        assert result[human_id] == (
            "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp",
            "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp",
        )

        migration.upgrade()
        assert {
            row[0]: (row[1], row[2])
            for row in connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller").all()
        } == result
    engine.dispose()
