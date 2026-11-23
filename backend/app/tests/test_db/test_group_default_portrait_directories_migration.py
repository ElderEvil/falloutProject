from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db

BASE = "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp"
THUMB = "/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Male.webp"


def test_grouped_portrait_migration():
    migration = load_migration(
        "2026_10_25_0001-e3a7c1b9d5f2_group_default_portrait_directories.py", "grouped_portrait_migration"
    )
    rows = (
        (
            1,
            "/static/dweller_images/FOS_Dw_Default_Human_Male.webp",
            "/static/dweller_thumbnails/FOS_Dw_Default_Human_Male.webp",
        ),
        (
            2,
            "/static/dweller_images/variants/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp",
            "/static/dweller_thumbnails/variants/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp",
        ),
        (3, "https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png"),
        (4, "/static/dweller_images/champ.png", "/static/dweller_images/champ-thumb.png"),
    )
    with sqlite_db("CREATE TABLE dweller (id INTEGER PRIMARY KEY, image_url TEXT, thumbnail_url TEXT)") as connection:
        for row in rows:
            connection.exec_driver_sql("INSERT INTO dweller VALUES (?, ?, ?)", row)
        bind_op(migration, connection)
        migration.upgrade()
        portraits = connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all()
        assert portraits[0][1:] == (BASE, THUMB)
        assert portraits[1][1:] == (
            "/static/dweller_images/variants/adult/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp",
            "/static/dweller_thumbnails/variants/adult/FOS_Dw_Default_Human_Male_SkinPale_HairBrown.webp",
        )
        assert portraits[2][1:] == ("https://cdn.example/custom.png", "https://cdn.example/custom-thumb.png")
        assert portraits[3][1:] == ("/static/dweller_images/champ.png", "/static/dweller_images/champ-thumb.png")
        migration.upgrade()
        assert (
            connection.exec_driver_sql("SELECT id, image_url, thumbnail_url FROM dweller ORDER BY id").all()
            == portraits
        )
