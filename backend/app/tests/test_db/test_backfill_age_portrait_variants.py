from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db

DWELLER = "CREATE TABLE dweller (id INTEGER PRIMARY KEY, age_group TEXT, gender TEXT, visual_attributes TEXT, image_url TEXT, thumbnail_url TEXT)"
HUMAN_PALE = '{"race":"human","skin_tone":"Pale","hair_color":"Blonde"}'
IMAGE = "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp"
THUMBNAIL = "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp"


def test_age_portrait_backfill():
    migration = load_migration(
        "2026_10_25_0002-a8c4d2e6f0b1_backfill_age_portrait_variants.py", "age_portrait_backfill"
    )
    rows = (
        (1, "CHILD", "male", HUMAN_PALE, IMAGE, THUMBNAIL),
        (2, "ADULT", "male", HUMAN_PALE, IMAGE, THUMBNAIL),
        (3, "CHILD", "female", HUMAN_PALE, "https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png"),
        (
            4,
            "CHILD",
            "female",
            HUMAN_PALE,
            "/static/dweller_images/custom.png",
            "/static/dweller_thumbnails/custom.png",
        ),
        (
            6,
            "CHILD",
            "male",
            '{"race":"ghoul","state_of_being":"sane"}',
            "/static/dweller_images/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
            "/static/dweller_thumbnails/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
        ),
        (5, "ELDER", "male", '{"race":"human","skin_tone":"Ebony","hair_color":"black"}', IMAGE, THUMBNAIL),
    )
    with sqlite_db(DWELLER) as connection:
        for row in rows:
            connection.exec_driver_sql("INSERT INTO dweller VALUES (?, ?, ?, ?, ?, ?)", row)
        bind_op(migration, connection)
        migration.upgrade()
        portraits = connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all()
        assert portraits[0][1:] == (
            "/static/dweller_images/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp",
            "/static/dweller_thumbnails/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp",
        )
        assert portraits[1][1:] == (IMAGE, THUMBNAIL)
        assert portraits[2][1:] == ("https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png")
        assert portraits[3][1:] == ("/static/dweller_images/custom.png", "/static/dweller_thumbnails/custom.png")
        assert portraits[4][1:] == (
            "/static/dweller_images/variants/elder/FOS_Dw_Default_Human_Elder_Male_SkinEbony_HairGray.webp",
            "/static/dweller_thumbnails/variants/elder/FOS_Dw_Default_Human_Elder_Male_SkinEbony_HairGray.webp",
        )
        assert portraits[5][1:] == (
            "/static/dweller_images/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
            "/static/dweller_thumbnails/base/FOS_Dw_Default_Ghoul_Male_Sane.webp",
        )
        migration.upgrade()
        assert (
            connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all()
            == portraits
        )
