from sqladmin import ModelView

from app.models import LLMInteraction, Objective, Storage
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.prompt import Prompt
from app.models.quest import Quest, QuestChain, QuestObjective
from app.models.room import Room
from app.models.user import User
from app.models.vault import Vault
from app.models.weapon import Weapon


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.email, User.is_active, User.is_superuser]
    column_details_exclude_list = [User.hashed_password]

    icon = "fa-solid fa-user"

    can_create = False
    can_edit = False
    can_export = False
    can_delete = False


class VaultAdmin(ModelView, model=Vault):
    column_list = [
        Vault.id,
        Vault.name,
        Vault.bottle_caps,
        Vault.happiness,
        Vault.power,
        Vault.food,
        Vault.water,
        Vault.user,
    ]

    icon = "fa-solid fa-house-lock"


class StorageAdmin(ModelView, model=Storage):
    column_list = [
        Storage.id,
        Storage.vault,
        Storage.used_space,
        Storage.max_space,
    ]

    icon = "fa-solid fa-box"


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
        Dweller.vault,
    ]

    icon = "fa-solid fa-person"


class JunkAdmin(ModelView, model=Junk):
    column_list = [Junk.id, Junk.name, Junk.rarity, Junk.value, Junk.junk_type, Junk.description]

    name = "Junk item"
    name_plural = "Junk"

    icon = "fa-solid fa-trash"


class OutfitAdmin(ModelView, model=Outfit):
    column_list = [
        Outfit.id,
        Outfit.name,
        Outfit.rarity,
        Outfit.value,
        Outfit.outfit_type,
        Outfit.gender,
    ]

    icon = "fa-solid fa-tshirt"


class QuestChainAdmin(ModelView, model=QuestChain):
    column_list = [
        QuestChain.id,
        QuestChain.title,
    ]

    icon = "fa-solid fa-tasks"


class QuestAdmin(ModelView, model=Quest):
    column_list = [
        Quest.id,
        Quest.title,
        Quest.short_description,
    ]

    icon = "fa-solid fa-tasks"


class QuestObjectiveAdmin(ModelView, model=QuestObjective):
    column_list = [
        QuestObjective.id,
        QuestObjective.quest,
    ]

    icon = "fa-solid fa-tasks"


class ObjectiveAdmin(ModelView, model=Objective):
    column_list = [
        Objective.id,
        Objective.challenge,
        Objective.reward,
    ]

    icon = "fa-solid fa-tasks"


class RoomAdmin(ModelView, model=Room):
    column_list = [
        Room.id,
        Room.name,
        Room.category,
        Room.ability,
        Room.tier,
        Room.size,
        Room.vault,
    ]

    icon = "fa-solid fa-door-open"


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

    icon = "fa-solid fa-gun"


class PromptAdmin(ModelView, model=Prompt):
    column_list = [
        Prompt.id,
        Prompt.prompt_name,
        # Prompt.ai_model_type,
    ]

    icon = "fa-solid fa-comment-dots"


class LLInteractionAdmin(ModelView, model=LLMInteraction):
    name = "LLM Interaction"
    name_plural = "LLM Interactions"
    column_list = [
        LLMInteraction.id,
        # LLMInteraction.ai_model_type,
        LLMInteraction.prompt,
        LLMInteraction.user,
    ]

    icon = "fa-solid fa-comment-dots"
