import json

from sqlmodel import Session

from app.crud import junk
from app.crud.weapon import weapon
from app.models.weapon import WeaponCreate


def populate_junk(db: Session):
    with open("fixtures/junk.json", "r") as f:
        junk_items_data = json.load(f)
        for junk_item_data in junk_items_data:
            junk.create(db, junk_item_data)


def populate_weapons(db: Session):
    with open("fixtures/weapons.json", "r") as f:
        weapons_data = json.load(f)
        for weapon_data in weapons_data:
            weapon_data["damage_min"], weapon_data["damage_max"] = weapon_data.pop("damage_range")
            weapon_obj = WeaponCreate(**weapon_data)
            weapon.create(db, weapon_obj)


def init_db(db: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next line
    # Base.metadata.create_all(bind=engine)
    ...
