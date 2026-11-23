from uuid import UUID

from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db

DWELLER = "CREATE TABLE dweller (id TEXT PRIMARY KEY, age_group TEXT, gender TEXT, visual_attributes TEXT, image_url TEXT, thumbnail_url TEXT)"
GHOUL = '{"race":"ghoul","state_of_being":"sane"}'
GHOUL_IMAGE = "/static/dweller_images/base/FOS_Dw_Default_Ghoul_Male_Sane.webp"
GHOUL_THUMB = "/static/dweller_thumbnails/base/FOS_Dw_Default_Ghoul_Male_Sane.webp"
HUMAN_IMAGE = "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp"
HUMAN_THUMB = "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp"


def test_non_human_portrait_alternates():
    migration = load_migration(
        "2026_10_25_0004-b3d7e1f5a902_backfill_non_human_portrait_variants.py", "non_human_portrait_alts"
    )
    base_id, alt_id = str(UUID(int=1)), str(UUID(int=6))  # hash selects base vs alternate portrait
    custom_id, human_id = str(UUID(int=7)), str(UUID(int=8))
    rows = (
        (base_id, "ADULT", "male", GHOUL, GHOUL_IMAGE, GHOUL_THUMB),
        (alt_id, "ADULT", "male", GHOUL, GHOUL_IMAGE, GHOUL_THUMB),
        (custom_id, "ADULT", "female", GHOUL, "https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png"),
        (human_id, "ADULT", "male", '{"race":"human"}', HUMAN_IMAGE, HUMAN_THUMB),
    )
    with sqlite_db(DWELLER) as connection:
        for row in rows:
            connection.exec_driver_sql("INSERT INTO dweller VALUES (?, ?, ?, ?, ?, ?)", row)
        bind_op(migration, connection)
        migration.upgrade()
        result = {
            row[0]: (row[1], row[2])
            for row in connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller").all()
        }
        assert result[base_id] == (GHOUL_IMAGE, GHOUL_THUMB)
        assert result[alt_id] == (
            "/static/dweller_images/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp",
            "/static/dweller_thumbnails/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp",
        )
        assert result[custom_id] == ("https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png")
        assert result[human_id] == (HUMAN_IMAGE, HUMAN_THUMB)
        migration.upgrade()
        assert {
            row[0]: (row[1], row[2])
            for row in connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller").all()
        } == result
