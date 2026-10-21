"""Grouped portrait migration rewrites only curated default URLs."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_grouped_portrait_migration(monkeypatch):
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/2026_10_25_0001-e3a7c1b9d5f2_group_default_portrait_directories.py"
    )
    spec = importlib.util.spec_from_file_location("grouped_portrait_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE dweller (id INTEGER PRIMARY KEY, image_url TEXT, thumbnail_url TEXT)")
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (1, '/static/dweller_images/FOS_Dw_Default_Human_Male.webp', "
            "'/static/dweller_thumbnails/FOS_Dw_Default_Human_Male.webp')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (2, '/static/dweller_images/variants/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp', "
            "'/static/dweller_thumbnails/variants/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (3, 'https://cdn.example/custom.png', 'https://cdn.example/custom-thumb.png')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (4, '/static/dweller_images/champ.png', '/static/dweller_images/champ-thumb.png')"
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        rows = connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all()
        assert rows[0][1:] == (
            "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp",
            "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp",
        )
        assert rows[1][1:] == (
            "/static/dweller_images/variants/adult/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp",
            "/static/dweller_thumbnails/variants/adult/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp",
        )
        assert rows[2][1:] == ("https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png")
        assert rows[3][1:] == ("/static/dweller_images/champ.png", "/static/dweller_images/champ-thumb.png")

        # Idempotent: a second pass leaves grouped URLs untouched.
        migration.upgrade()
        second = connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all()
        assert second == rows
    engine.dispose()
