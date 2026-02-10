from sqladmin import ModelView

from app.models import LLMInteraction, Objective, Storage
from app.models.chat_message import ChatMessage
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.incident import Incident
from app.models.junk import Junk
from app.models.notification import Notification
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

TRUNCATE_LENGTH = 50


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
        Vault.power_max,
        Vault.food,
        Vault.food_max,
        Vault.water,
        Vault.water_max,
        Vault.population_max,
        Vault.radio_mode,
        Vault.user,
        Vault.created_at,
        Vault.updated_at,
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
        Dweller.radiation,
        Dweller.happiness,
        Dweller.stimpack,
        Dweller.radaway,
        Dweller.is_dead,
        Dweller.death_cause,
        Dweller.vault,
        Dweller.room,
        Dweller.created_at,
        Dweller.updated_at,
    ]

    column_formatters = {
        Dweller.bio: lambda m, a: (  # noqa: ARG005
            (m.bio[:TRUNCATE_LENGTH] + "...") if m.bio and len(m.bio) > TRUNCATE_LENGTH else m.bio
        ),
    }

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
        Quest.requirements,
        Quest.rewards,
        Quest.created_at,
        Quest.updated_at,
    ]
    column_searchable_list = [Quest.title, Quest.short_description]
    column_sortable_list = [Quest.title, Quest.created_at]
    column_default_sort = [(Quest.created_at, True)]

    icon = "fa-solid fa-book-open"

    can_create = True
    can_edit = True
    can_delete = True
    can_export = True


class ObjectiveAdmin(ModelView, model=Objective):
    column_list = [
        Objective.id,
        Objective.challenge,
        Objective.reward,
    ]
    column_searchable_list = [Objective.challenge, Objective.reward]
    column_sortable_list = [Objective.challenge]

    icon = "fa-solid fa-bullseye"

    can_create = True
    can_edit = True
    can_delete = True
    can_export = True


class RoomAdmin(ModelView, model=Room):
    column_list = [
        Room.id,
        Room.name,
        Room.category,
        Room.ability,
        Room.tier,
        Room.size,
        Room.coordinate_x,
        Room.coordinate_y,
        Room.base_cost,
        Room.speedup_multiplier,
        Room.vault,
        Room.created_at,
        Room.updated_at,
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
    can_delete = True


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


class ChatMessageAdmin(ModelView, model=ChatMessage):
    column_list = [
        ChatMessage.id,
        ChatMessage.vault_id,
        ChatMessage.from_user_id,
        ChatMessage.from_dweller_id,
        ChatMessage.to_user_id,
        ChatMessage.to_dweller_id,
        ChatMessage.message_text,
        ChatMessage.happiness_delta,
        ChatMessage.happiness_reason,
        ChatMessage.audio_url,
        ChatMessage.audio_duration,
        ChatMessage.llm_interaction_id,
        ChatMessage.created_at,
    ]
    column_searchable_list = [ChatMessage.message_text, ChatMessage.happiness_reason]
    column_sortable_list = [ChatMessage.created_at, ChatMessage.happiness_delta]
    column_default_sort = [(ChatMessage.created_at, True)]

    column_formatters = {
        ChatMessage.message_text: lambda m, a: (  # noqa: ARG005
            m.message_text[:TRUNCATE_LENGTH] + "..."
            if m.message_text and len(m.message_text) > TRUNCATE_LENGTH
            else m.message_text
        ),
        ChatMessage.happiness_reason: lambda m, a: (  # noqa: ARG005
            m.happiness_reason[:TRUNCATE_LENGTH] + "..."
            if m.happiness_reason and len(m.happiness_reason) > TRUNCATE_LENGTH
            else m.happiness_reason
        ),
    }

    name = "Chat Message"
    name_plural = "Chat Messages"
    icon = "fa-solid fa-message"

    can_create = False
    can_edit = False
    can_delete = True


class NotificationAdmin(ModelView, model=Notification):
    column_list = [
        Notification.id,
        Notification.user_id,
        Notification.vault_id,
        Notification.from_dweller_id,
        Notification.notification_type,
        Notification.priority,
        Notification.title,
        Notification.message,
        Notification.is_read,
        Notification.is_dismissed,
        Notification.created_at,
        Notification.read_at,
    ]
    column_searchable_list = [Notification.title, Notification.message]
    column_sortable_list = [Notification.created_at, Notification.priority, Notification.notification_type]
    column_default_sort = [(Notification.created_at, True)]

    column_formatters = {
        Notification.message: lambda m, a: (  # noqa: ARG005
            m.message[:TRUNCATE_LENGTH] + "..." if m.message and len(m.message) > TRUNCATE_LENGTH else m.message
        ),
    }

    name = "Notification"
    name_plural = "Notifications"
    icon = "fa-solid fa-bell"

    can_create = False
    can_edit = True
    can_delete = True
