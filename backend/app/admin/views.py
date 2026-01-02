from sqladmin import ModelView

from app.models import LLMInteraction, Objective, Storage
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.incident import Incident
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.pregnancy import Pregnancy
from app.models.prompt import Prompt
from app.models.quest import Quest
from app.models.relationship import Relationship
from app.models.room import Room
from app.models.training import Training
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.vault import Vault
from app.models.weapon import Weapon


class UserAdmin(ModelView, model=User):
    column_list = [
        User.id,
        User.username,
        User.email,
        User.is_active,
        User.is_superuser,
        User.created_at,
        User.updated_at,
    ]
    column_details_exclude_list = [User.hashed_password]

    icon = "fa-solid fa-user"

    can_create = False
    can_edit = False
    can_export = False
    can_delete = False


class UserProfileAdmin(ModelView, model=UserProfile):
    column_list = [
        UserProfile.id,
        UserProfile.user,
        UserProfile.bio,
        UserProfile.avatar_url,
        UserProfile.total_dwellers_created,
        UserProfile.total_caps_earned,
        UserProfile.total_explorations,
        UserProfile.total_rooms_built,
        UserProfile.created_at,
        UserProfile.updated_at,
    ]

    name = "User Profile"
    name_plural = "User Profiles"

    icon = "fa-solid fa-id-card"

    can_create = False
    can_delete = False


class VaultAdmin(ModelView, model=Vault):
    column_list = [
        Vault.id,
        Vault.number,
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
        Dweller.age_group,
        Dweller.rarity,
        Dweller.status,
        Dweller.level,
        Dweller.experience,
        Dweller.max_health,
        Dweller.health,
        Dweller.happiness,
        Dweller.partner_id,
        Dweller.parent_1_id,
        Dweller.parent_2_id,
        Dweller.vault,
        Dweller.room,
        Dweller.created_at,
        Dweller.updated_at,
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


class QuestAdmin(ModelView, model=Quest):
    column_list = [
        Quest.id,
        Quest.title,
        Quest.short_description,
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
        LLMInteraction.usage,
        LLMInteraction.prompt,
        LLMInteraction.user,
    ]

    icon = "fa-solid fa-comment-dots"


class RelationshipAdmin(ModelView, model=Relationship):
    column_list = [
        Relationship.id,
        Relationship.dweller_1_id,
        Relationship.dweller_2_id,
        Relationship.relationship_type,
        Relationship.affinity,
        Relationship.created_at,
        Relationship.updated_at,
    ]

    name = "Relationship"
    name_plural = "Relationships"
    icon = "fa-solid fa-heart"

    can_create = False
    can_delete = False


class PregnancyAdmin(ModelView, model=Pregnancy):
    column_list = [
        Pregnancy.id,
        Pregnancy.mother_id,
        Pregnancy.father_id,
        Pregnancy.conceived_at,
        Pregnancy.due_at,
        Pregnancy.status,
        Pregnancy.created_at,
        Pregnancy.updated_at,
    ]

    name = "Pregnancy"
    name_plural = "Pregnancies"
    icon = "fa-solid fa-baby"

    can_create = False
    can_delete = False


class TrainingAdmin(ModelView, model=Training):
    column_list = [
        Training.id,
        Training.dweller_id,
        Training.room_id,
        Training.vault_id,
        Training.stat_being_trained,
        Training.current_stat_value,
        Training.target_stat_value,
        Training.progress,
        Training.status,
        Training.started_at,
        Training.estimated_completion_at,
        Training.completed_at,
        Training.created_at,
        Training.updated_at,
    ]

    name = "Training"
    name_plural = "Training Sessions"
    icon = "fa-solid fa-dumbbell"

    can_create = False
    can_edit = True
    can_delete = False


class IncidentAdmin(ModelView, model=Incident):
    column_list = [
        Incident.id,
        Incident.vault_id,
        Incident.room_id,
        Incident.type,
        Incident.status,
        Incident.difficulty,
        Incident.start_time,
        Incident.end_time,
        Incident.duration,
        Incident.damage_dealt,
        Incident.created_at,
        Incident.updated_at,
    ]

    name = "Incident"
    name_plural = "Incidents"
    icon = "fa-solid fa-exclamation-triangle"

    can_create = False
    can_edit = True
    can_delete = False


class ExplorationAdmin(ModelView, model=Exploration):
    column_list = [
        Exploration.id,
        Exploration.vault_id,
        Exploration.dweller_id,
        Exploration.status,
        Exploration.duration,
        Exploration.start_time,
        Exploration.end_time,
        Exploration.total_distance,
        Exploration.total_caps_found,
        Exploration.enemies_encountered,
        Exploration.created_at,
        Exploration.updated_at,
    ]

    name = "Exploration"
    name_plural = "Explorations"
    icon = "fa-solid fa-map-marked-alt"

    can_create = False
    can_edit = True
    can_delete = False
