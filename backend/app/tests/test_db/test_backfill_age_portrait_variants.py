"""Age portrait backfill only rewrites curated child/teen defaults."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_age_portrait_backfill(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_25_0002-a8c4d2e6f0b1_backfill_age_portrait_variants.py"
    spec = importlib.util.spec_from_file_location("age_portrait_backfill", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE dweller (id INTEGER PRIMARY KEY, age_group TEXT, gender TEXT, "
            "visual_attributes TEXT, image_url TEXT, thumbnail_url TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (1, 'CHILD', 'male', "
            '\'{"race":"human","skin_tone":"Pale","hair_color":"Blonde"}\', '
            "'/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp', "
            "'/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (2, 'ADULT', 'male', "
            '\'{"race":"human","skin_tone":"Pale","hair_color":"Blonde"}\', '
            "'/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp', "
            "'/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (3, 'CHILD', 'female', "
            '\'{"race":"human","skin_tone":"Pale","hair_color":"Blonde"}\', '
            "'https://cdn.example/custom.png', 'https://cdn.example/custom-thumb.png')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (4, 'CHILD', 'female', "
            '\'{"race":"human","skin_tone":"Pale","hair_color":"Blonde"}\', '
            "'/static/dweller_images/custom.png', '/static/dweller_thumbnails/custom.png')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (5, 'ELDER', 'male', "
            '\'{"race":"human","skin_tone":"Ebony","hair_color":"black"}\', '
            "'/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp', "
            "'/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp')"
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        rows = connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all()
        assert rows[0][1:] == (
            "/static/dweller_images/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp",
            "/static/dweller_thumbnails/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp",
        )
        assert rows[1][1:] == (
            "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp",
            "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp",
        )
        assert rows[2][1:] == ("https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png")
        assert rows[3][1:] == ("/static/dweller_images/custom.png", "/static/dweller_thumbnails/custom.png")
        assert rows[4][1:] == (
            "/static/dweller_images/variants/elder/FOS_Dw_Default_Human_Elder_Male_SkinEbony_HairGray.webp",
            "/static/dweller_thumbnails/variants/elder/FOS_Dw_Default_Human_Elder_Male_SkinEbony_HairGray.webp",
        )

        migration.upgrade()
        assert connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all() == rows
    engine.dispose()
