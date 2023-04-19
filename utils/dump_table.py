import json

from fastapi import Depends
from sqlmodel import Session

from app.api.crud.junk import junk
from app.api.crud.weapon import weapon
from app.db.base import get_session


def dump_junk(db: Session = Depends(get_session)):
    junk_items = junk.get_multi(db, skip=0, limit=1000)
    junk_data = [junk_item.to_dict() for junk_item in junk_items]
    with open("fixtures/junk.json", "w") as f:
        json.dump(junk_data, f)


def dump_weapons(db: Session = Depends(get_session)):
    weapon_items = weapon.get_multi(db, skip=0, limit=1000)
    weapons_data = [weapon_item.to_dict() for weapon_item in weapon_items]
    with open("fixtures/weapons.json", "w") as f:
        json.dump(weapons_data, f)
