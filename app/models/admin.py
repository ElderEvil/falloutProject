from sqladmin import ModelView

from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.quest import Quest
from app.models.room import Room
from app.models.user import User
from app.models.weapon import Weapon


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.email, User.is_active, User.is_superuser]

    can_create = False
    can_edit = False
    can_export = False
    can_delete = False


class DwellerAdmin(ModelView, model=Dweller):
    column_list = [
        Dweller.id,
        Dweller.first_name,
        Dweller.last_name,
        Dweller.gender,
        Dweller.rarity,
        Dweller.level,
        Dweller.experience,
        Dweller.max_health,
        Dweller.health,
        Dweller.happiness,
        Dweller.is_adult,
    ]


class JunkAdmin(ModelView, model=Junk):
    column_list = [Junk.id, Junk.name, Junk.rarity, Junk.value, Junk.junk_type, Junk.description]

    name = "Junk item"
    name_plural = "Junk"


class OutfitAdmin(ModelView, model=Outfit):
    column_list = [
        Outfit.id,
        Outfit.name,
        Outfit.rarity,
        Outfit.value,
        Outfit.outfit_type,
        Outfit.gender,
    ]


class QuestAdmin(ModelView, model=Quest):
    column_list = [
        Quest.id,
        Quest.title,
        Quest.description,
        Quest.completed,
    ]


class RoomAdmin(ModelView, model=Room):
    column_list = [
        Room.id,
        Room.name,
        Room.category,
        Room.ability,
        Room.population_required,
        Room.base_cost,
        Room.incremental_cost,
        Room.tier,
        Room.max_tier,
        Room.t2_upgrade_cost,
        Room.t3_upgrade_cost,
        Room.output,
        Room.size,
    ]


class WeaponAdmin(ModelView, model=Weapon):
    column_list = [
        Weapon.id,
        Weapon.name,
        Weapon.rarity,
        Weapon.value,
        Weapon.weapon_type,
        Weapon.weapon_subtype,
        Weapon.stat,
        Weapon.damage_min,
        Weapon.damage_max,
    ]
