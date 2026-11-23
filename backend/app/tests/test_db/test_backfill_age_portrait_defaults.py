from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db

DWELLER = "CREATE TABLE dweller (id INTEGER PRIMARY KEY, age_group TEXT, gender TEXT, visual_attributes TEXT, image_url TEXT, thumbnail_url TEXT)"
BASE_MALE = "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp"
THUMB_MALE = "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp"
SUPER_MUTANT = "/static/dweller_images/base/FOS_Dw_Default_SuperMutant_Male_Average.webp"


def test_age_portrait_defaults_backfill():
    migration = load_migration(
        "2026_10_25_0003-f2b8d4e6c0a1_backfill_age_portrait_defaults.py", "age_portrait_defaults"
    )
    rows = (
        (1, "CHILD", "male", "{}", BASE_MALE, THUMB_MALE),
        (
            2,
            "ELDER",
            "female",
            "{}",
            "/static/dweller_images/base/FOS_Dw_Default_Human_Female.webp",
            "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp",
        ),
        (
            4,
            "TEEN",
            "male",
            '{"race":"super_mutant","state_of_being":"average"}',
            SUPER_MUTANT,
            "/static/dweller_thumbnails/base/FOS_Dw_Default_SuperMutant_Male_Average.webp",
        ),
        (3, "ADULT", "male", "{}", BASE_MALE, THUMB_MALE),
    )
    with sqlite_db(DWELLER) as connection:
        for row in rows:
            connection.exec_driver_sql("INSERT INTO dweller VALUES (?, ?, ?, ?, ?, ?)", row)
        bind_op(migration, connection)
        migration.upgrade()
        images = connection.exec_driver_sql("SELECT id, image_url FROM dweller ORDER BY id").all()
        assert (
            images[0][1]
            == "/static/dweller_images/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBrown.webp"
        )
        assert (
            images[1][1]
            == "/static/dweller_images/variants/elder/FOS_Dw_Default_Human_Elder_Female_SkinPale_HairGray.webp"
        )
        assert images[2][1] == BASE_MALE
        assert images[3][1] == SUPER_MUTANT
