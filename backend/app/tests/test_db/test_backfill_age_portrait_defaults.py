"""Age portrait defaults backfill covers legacy rows without skin/hair fields."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_age_portrait_defaults_backfill(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_25_0003-f2b8d4e6c0a1_backfill_age_portrait_defaults.py"
    spec = importlib.util.spec_from_file_location("age_portrait_defaults", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE dweller (id INTEGER PRIMARY KEY, age_group TEXT, gender TEXT, "
            "visual_attributes TEXT, image_url TEXT, thumbnail_url TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (1, 'CHILD', 'male', '{}', "
            "'/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp', "
            "'/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (2, 'ELDER', 'female', '{}', "
            "'/static/dweller_images/base/FOS_Dw_Default_Human_Female.webp', "
            "'/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (4, 'TEEN', 'male', "
            '\'{"race":"super_mutant","state_of_being":"average"}\', '
            "'/static/dweller_images/base/FOS_Dw_Default_SuperMutant_Male_Average.webp', "
            "'/static/dweller_thumbnails/base/FOS_Dw_Default_SuperMutant_Male_Average.webp')"
        )
        connection.exec_driver_sql(
            "INSERT INTO dweller VALUES (3, 'ADULT', 'male', '{}', "
            "'/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp', "
            "'/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp')"
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        rows = connection.exec_driver_sql("SELECT id, image_url FROM dweller ORDER BY id").all()
        assert rows[0][1] == (
            "/static/dweller_images/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBrown.webp"
        )
        assert rows[1][1] == (
            "/static/dweller_images/variants/elder/FOS_Dw_Default_Human_Elder_Female_SkinPale_HairGray.webp"
        )
        assert rows[2][1] == "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp"
        assert rows[3][1] == ("/static/dweller_images/base/FOS_Dw_Default_SuperMutant_Male_Average.webp")
    engine.dispose()
