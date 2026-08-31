from typing import ClassVar

from sqladmin import ModelView, action
from sqladmin.filters import AllUniqueStringValuesFilter, BooleanFilter
from sqlmodel import select
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.models import AISettings, LLMInteraction, Objective, Storage
from app.models.chat_message import ChatMessage
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.game_state import GameState
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


def _truncate(value: str | None) -> str | None:
    return f"{value[:TRUNCATE_LENGTH]}..." if value and len(value) > TRUNCATE_LENGTH else value


class AdminModelView(ModelView):
    """Safe defaults for administrative data views."""

    can_delete = False
    page_size = 50


class UserAdmin(AdminModelView, model=User):
    column_list: ClassVar[list] = [
        User.id,
        User.username,
        User.email,
        User.is_active,
        User.is_superuser,
        User.created_at,
        User.updated_at,
    ]
    column_details_exclude_list: ClassVar[list] = [
        User.hashed_password,
        User.email_verification_token,
        User.password_reset_token,
        User.password_reset_expires,
    ]
    column_searchable_list: ClassVar[list] = [User.username, User.email]
    column_labels: ClassVar[dict] = {User.is_active: "Active", User.is_superuser: "Superuser"}

    icon = "fa-solid fa-user"

    can_create = False
    can_edit = False
    can_export = False
    can_delete = False

    @action(
        name="verify-email",
        label="Verify email",
        confirmation_message="Mark the selected users' email addresses as verified?",
    )
    async def verify_email(self, request: Request) -> RedirectResponse:
        """Mark selected users' email addresses as verified."""
        user_ids = request.query_params.get("pks", "").split(",")
        async with self.session_maker() as session:
            users = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars()
            for user in users:
                user.email_verified = True
                user.email_verification_token = None
            await session.commit()
        return RedirectResponse(request.headers.get("Referer", "/admin/user/list"), status_code=303)


class UserProfileAdmin(AdminModelView, model=UserProfile):
    column_list: ClassVar[list] = [
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


class VaultAdmin(AdminModelView, model=Vault):
    column_list: ClassVar[list] = [
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
    column_searchable_list: ClassVar[list] = [Vault.number]
    column_labels: ClassVar[dict] = {Vault.bottle_caps: "Caps", Vault.population_max: "Population limit"}

    icon = "fa-solid fa-house-lock"


class StorageAdmin(AdminModelView, model=Storage):
    column_list: ClassVar[list] = [
        Storage.id,
        Storage.vault,
        Storage.used_space,
        Storage.max_space,
    ]

    icon = "fa-solid fa-box"


class DwellerAdmin(AdminModelView, model=Dweller):
    column_list: ClassVar[list] = [
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
        Dweller.bio,
        Dweller.vault,
        Dweller.room,
        Dweller.created_at,
        Dweller.updated_at,
    ]
    column_searchable_list: ClassVar[list] = [Dweller.first_name, Dweller.last_name]
    column_labels: ClassVar[dict] = {Dweller.max_health: "Max HP", Dweller.health: "HP"}

    column_formatters: ClassVar[dict] = {
        Dweller.bio: lambda m, _attribute: _truncate(m.bio),
    }

    icon = "fa-solid fa-person"


class JunkAdmin(AdminModelView, model=Junk):
    column_list: ClassVar[list] = [Junk.id, Junk.name, Junk.rarity, Junk.value, Junk.junk_type, Junk.description]

    name = "Junk item"
    name_plural = "Junk"

    icon = "fa-solid fa-trash"


class OutfitAdmin(AdminModelView, model=Outfit):
    column_list: ClassVar[list] = [
        Outfit.id,
        Outfit.name,
        Outfit.rarity,
        Outfit.value,
        Outfit.outfit_type,
        Outfit.gender,
    ]

    icon = "fa-solid fa-tshirt"


class QuestAdmin(AdminModelView, model=Quest):
    column_list: ClassVar[list] = [
        Quest.id,
        Quest.title,
        Quest.short_description,
        Quest.requirements,
        Quest.rewards,
        Quest.created_at,
        Quest.updated_at,
    ]
    column_searchable_list: ClassVar[list] = [Quest.title, Quest.short_description]
    column_sortable_list: ClassVar[list] = [Quest.title, Quest.created_at]
    column_default_sort: ClassVar[list] = [(Quest.created_at, True)]

    icon = "fa-solid fa-book-open"

    can_create = False
    can_edit = False
    can_export = True


class ObjectiveAdmin(AdminModelView, model=Objective):
    column_list: ClassVar[list] = [
        Objective.id,
        Objective.challenge,
        Objective.reward,
    ]
    column_searchable_list: ClassVar[list] = [Objective.challenge, Objective.reward]
    column_sortable_list: ClassVar[list] = [Objective.challenge]

    icon = "fa-solid fa-bullseye"

    can_create = False
    can_edit = False
    can_export = True


class RoomAdmin(AdminModelView, model=Room):
    column_list: ClassVar[list] = [
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

    can_create = False
    can_edit = False
    can_delete = False


class WeaponAdmin(AdminModelView, model=Weapon):
    column_list: ClassVar[list] = [
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


class PromptAdmin(AdminModelView, model=Prompt):
    column_list: ClassVar[list] = [
        Prompt.id,
        Prompt.prompt_name,
        Prompt.version,
        Prompt.is_active,
        Prompt.description,
        Prompt.entity_id,
    ]
    # Templates are a constrained interface: details previews the raw template;
    # edits go through the deferred copy-as-new-version flow, never in place.
    column_details_exclude_list: ClassVar[list] = [Prompt.llm_interactions]
    column_searchable_list: ClassVar[list] = [Prompt.prompt_name, Prompt.description]
    column_filters: ClassVar[list] = [
        BooleanFilter(Prompt.is_active),
        AllUniqueStringValuesFilter(Prompt.version),
    ]
    column_default_sort: ClassVar[list] = [(Prompt.is_active, True), (Prompt.version, True)]

    icon = "fa-solid fa-comment-dots"

    can_create = False
    can_edit = False
    can_export = False


class AISettingsAdmin(AdminModelView, model=AISettings):
    column_list: ClassVar[list] = [
        AISettings.id,
        AISettings.provider,
        AISettings.model,
        AISettings.base_url,
        AISettings.gateway_route,
        AISettings.updated_at,
    ]
    can_create = False
    can_edit = False

    name = "AI Setting"
    name_plural = "AI Settings"
    icon = "fa-solid fa-robot"


class GameStateAdmin(AdminModelView, model=GameState):
    column_list: ClassVar[list] = [
        GameState.id,
        GameState.vault_id,
        GameState.is_active,
        GameState.is_paused,
        GameState.total_game_time,
        GameState.last_tick_time,
        GameState.last_activity_time,
    ]
    can_create = False
    can_edit = False

    name = "Game State"
    name_plural = "Game States"
    icon = "fa-solid fa-clock"


class LLInteractionAdmin(AdminModelView, model=LLMInteraction):
    name = "LLM Interaction"
    name_plural = "LLM Interactions"
    column_list: ClassVar[list] = [
        LLMInteraction.id,
        LLMInteraction.usage,
        LLMInteraction.prompt,
        LLMInteraction.user,
        LLMInteraction.provider,
        LLMInteraction.model,
        LLMInteraction.prompt_tokens,
        LLMInteraction.completion_tokens,
        LLMInteraction.total_tokens,
        LLMInteraction.instructions_hash,
        LLMInteraction.created_at,
    ]
    column_searchable_list: ClassVar[list] = [LLMInteraction.usage]
    column_filters: ClassVar[list] = [
        AllUniqueStringValuesFilter(LLMInteraction.usage),
        AllUniqueStringValuesFilter(LLMInteraction.provider),
        AllUniqueStringValuesFilter(LLMInteraction.model),
    ]
    column_sortable_list: ClassVar[list] = [
        LLMInteraction.usage,
        LLMInteraction.created_at,
        LLMInteraction.total_tokens,
    ]
    column_default_sort: ClassVar[list] = [(LLMInteraction.created_at, True)]

    icon = "fa-solid fa-comment-dots"

    can_create = False
    can_edit = False
    can_export = False


class RelationshipAdmin(AdminModelView, model=Relationship):
    column_list: ClassVar[list] = [
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


class PregnancyAdmin(AdminModelView, model=Pregnancy):
    column_list: ClassVar[list] = [
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


class TrainingAdmin(AdminModelView, model=Training):
    column_list: ClassVar[list] = [
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


class IncidentAdmin(AdminModelView, model=Incident):
    column_list: ClassVar[list] = [
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


class ExplorationAdmin(AdminModelView, model=Exploration):
    column_list: ClassVar[list] = [
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


class ChatMessageAdmin(AdminModelView, model=ChatMessage):
    column_list: ClassVar[list] = [
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
    column_searchable_list: ClassVar[list] = [ChatMessage.message_text, ChatMessage.happiness_reason]
    column_sortable_list: ClassVar[list] = [ChatMessage.created_at, ChatMessage.happiness_delta]
    column_default_sort: ClassVar[list] = [(ChatMessage.created_at, True)]

    column_formatters: ClassVar[dict] = {
        ChatMessage.message_text: lambda m, _attribute: _truncate(m.message_text),
        ChatMessage.happiness_reason: lambda m, _attribute: _truncate(m.happiness_reason),
    }

    name = "Chat Message"
    name_plural = "Chat Messages"
    icon = "fa-solid fa-message"

    can_create = False
    can_edit = False


class NotificationAdmin(AdminModelView, model=Notification):
    column_list: ClassVar[list] = [
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
    column_searchable_list: ClassVar[list] = [Notification.title, Notification.message]
    column_sortable_list: ClassVar[list] = [
        Notification.created_at,
        Notification.priority,
        Notification.notification_type,
    ]
    column_default_sort: ClassVar[list] = [(Notification.created_at, True)]

    column_formatters: ClassVar[dict] = {
        Notification.message: lambda m, _attribute: _truncate(m.message),
    }

    name = "Notification"
    name_plural = "Notifications"
    icon = "fa-solid fa-bell"

    can_create = False
    can_edit = True
