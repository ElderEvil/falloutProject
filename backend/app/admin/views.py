from collections.abc import Sequence
from typing import Any, ClassVar

from markupsafe import Markup
from sqladmin import ModelView, action, expose
from sqladmin.filters import AllUniqueStringValuesFilter, BooleanFilter, OperationColumnFilter, StaticValuesFilter
from sqlalchemy.ext.asyncio import async_object_session
from sqlalchemy.orm import InstrumentedAttribute
from sqlmodel import SQLModel, col
from starlette.requests import Request
from starlette.responses import Response

from app.admin.actions import confirm_action, render_incident_controls, submit_action, submit_incident_controls
from app.core.enums import AgeGroupEnum, DwellerStatusEnum
from app.models import Item, LLMInteraction, Objective, Storage
from app.models.chat_message import ChatMessage
from app.models.crafting_order import CraftingOrder
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.game_state import GameState
from app.models.incident import Incident
from app.models.junk import Junk
from app.models.notification import Notification
from app.models.oauth_account import OAuthAccount
from app.models.outfit import Outfit
from app.models.pet import Pet
from app.models.pregnancy import Pregnancy
from app.models.prompt import Prompt
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward
from app.models.relationship import Relationship
from app.models.room import Room
from app.models.team import Team, TeamMember
from app.models.training import Training
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.vault import Vault
from app.models.vault_quest import VaultQuestCompletionLink
from app.models.weapon import Weapon
from app.services.admin_service import FIRST_SUPERUSER_OPERATIONS, authorize_profile_edit
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException

type SortColumns = str | InstrumentedAttribute | tuple[str | InstrumentedAttribute, bool] | list

TRUNCATE_LENGTH = 50


def _truncate(value: str | None) -> str | None:
    return f"{value[:TRUNCATE_LENGTH]}..." if value and len(value) > TRUNCATE_LENGTH else value


def _progress(model: SQLModel, attribute: str) -> str:
    return f"{getattr(model, attribute):.1%}"


RELATED_VIEWS = {
    "vault_id": "vault",
    "room_id": "room",
    "user_id": "user",
    "dweller_id": "dweller",
    "mother_id": "dweller",
    "father_id": "dweller",
    "dweller_1_id": "dweller",
    "dweller_2_id": "dweller",
    "quest_id": "quest",
    "incident_id": "incident",
    "storage_id": "storage",
    "from_user_id": "user",
    "from_dweller_id": "dweller",
}


def _record_link(model: SQLModel, attribute: str, request: Request) -> str:
    value = getattr(model, attribute)
    if value is None:
        return "—"
    url = request.url_for("admin:details", identity=RELATED_VIEWS[attribute], pk=str(value))
    return Markup('<a href="{}" title="{}">{}</a>').format(url, value, str(value)[:8])


class AdminModelView(ModelView):
    """Read-only inspection by default; explicit support actions preserve game invariants."""

    column_formatters: ClassVar[dict] = {
        **dict.fromkeys(RELATED_VIEWS, _record_link),
        "progress": _progress,
        "reward_chance": _progress,
    }
    column_formatters_detail: ClassVar[dict] = {"progress": _progress, "reward_chance": _progress}
    support_operations: ClassVar[dict[str, str]] = {}
    page_size_options: ClassVar[Sequence[int]] = [25, 50, 100, 200]
    can_edit = False
    can_create = False

    can_delete = False
    page_size = 50

    def __init__(self) -> None:
        super().__init__()
        for name in self._prop_names:
            self._column_labels.setdefault(name, name.replace("_", " ").title().replace(" Id", " ID"))
        self._column_labels_value_by_key = {value: key for key, value in self._column_labels.items()}

    @expose("/support", methods=["POST"])
    async def support(self, request: Request) -> Response:
        return await submit_action(self, request)


class UserAdmin(AdminModelView, model=User):
    can_export = False
    category = "Accounts"
    column_filters: ClassVar[Sequence] = [
        BooleanFilter("email_verified"),
        BooleanFilter("is_active"),
        BooleanFilter("is_superuser"),
        BooleanFilter("is_deleted"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(User.created_at, True)]
    column_sortable_list: ClassVar[Sequence] = [
        User.username,
        User.email,
        User.email_verified,
        User.is_active,
        User.created_at,
    ]
    support_operations: ClassVar[dict[str, str]] = {
        "verify-email": "Verify email",
        "promote-superuser": "Promote to superuser",
        "demote-superuser": "Demote from superuser",
        "deactivate": "Deactivate user",
        "reactivate": "Reactivate user",
        "soft-delete": "Soft-delete user",
    }
    column_list: ClassVar[str | Sequence] = [
        User.username,
        User.email,
        User.email_verified,
        User.is_active,
        User.is_superuser,
        User.is_deleted,
        User.created_at,
    ]
    column_details_exclude_list: ClassVar[Sequence] = [
        User.hashed_password,
        User.email_verification_token,
        User.password_reset_token,
        User.password_reset_expires,
    ]
    column_searchable_list: ClassVar[Sequence] = [User.username, User.email]
    column_labels: ClassVar[dict] = {
        User.is_active: "Active",
        User.is_superuser: "Superuser",
        User.is_deleted: "Deleted",
    }

    icon = "fa-solid fa-user"

    def has_permission(self, request: Request, action: str, obj: Any = None) -> bool:
        if action in {f"action:{operation}" for operation in FIRST_SUPERUSER_OPERATIONS} and not getattr(
            request.state, "is_first_superuser", False
        ):
            return False
        return super().has_permission(request, action, obj)

    @action(name="verify-email", label=support_operations["verify-email"])
    async def verify_email(self, request: Request) -> Response:
        return await confirm_action(self, request, "verify-email")

    @action(name="promote-superuser", label=support_operations["promote-superuser"])
    async def promote_superuser(self, request: Request) -> Response:
        return await confirm_action(self, request, "promote-superuser")

    @action(name="demote-superuser", label=support_operations["demote-superuser"])
    async def demote_superuser(self, request: Request) -> Response:
        return await confirm_action(self, request, "demote-superuser")

    @action(name="deactivate", label=support_operations["deactivate"])
    async def deactivate_user(self, request: Request) -> Response:
        return await confirm_action(self, request, "deactivate")

    @action(name="reactivate", label=support_operations["reactivate"])
    async def reactivate_user(self, request: Request) -> Response:
        return await confirm_action(self, request, "reactivate")

    @action(name="soft-delete", label=support_operations["soft-delete"])
    async def soft_delete_user(self, request: Request) -> Response:
        return await confirm_action(self, request, "soft-delete")


class UserProfileAdmin(AdminModelView, model=UserProfile):
    async def check_can_edit(self, request: Request, model: Any) -> bool:
        if not await super().check_can_edit(request, model):
            return False
        if model is None:
            return True  # SQLAdmin's edit handler returns 404 for a missing record.
        try:
            async with self.session_maker() as session:
                await authorize_profile_edit(session, model.user_id, actor_id=str(request.session["user_id"]))
        except (AccessDeniedException, ResourceNotFoundException):
            return False
        return True

    async def on_model_change(self, data: dict, model: Any, is_created: bool, request: Request) -> None:
        session = async_object_session(model)
        if session is None:
            raise RuntimeError("Profile editing requires an attached async session")
        # Recheck in the write transaction and hold user locks through commit.
        await authorize_profile_edit(session, model.user_id, actor_id=str(request.session["user_id"]))

    can_edit = True
    form_columns: ClassVar[Sequence] = ["bio", "avatar_url"]
    category = "Accounts"
    column_list: ClassVar[str | Sequence] = [
        UserProfile.user,
        UserProfile.total_dwellers_created,
        UserProfile.total_caps_earned,
        UserProfile.total_explorations,
        UserProfile.total_rooms_built,
    ]

    name = "User Profile"
    name_plural = "User Profiles"

    icon = "fa-solid fa-id-card"


class VaultAdmin(AdminModelView, model=Vault):
    support_operations: ClassVar[dict[str, str]] = {"pause": "Pause vault", "resume": "Resume vault"}
    category = "Vault operations"
    column_list: ClassVar[str | Sequence] = [
        Vault.number,
        Vault.user,
        Vault.vault_mode,
        Vault.happiness,
        Vault.bottle_caps,
        Vault.population_max,
        Vault.incidents_disabled,
    ]
    column_searchable_list: ClassVar[Sequence] = [Vault.number]
    column_labels: ClassVar[dict] = {
        Vault.bottle_caps: "Caps",
        Vault.population_max: "Population limit",
        Vault.incidents_disabled: "Incidents disabled",
    }
    column_filters: ClassVar[Sequence] = [
        BooleanFilter("incidents_disabled"),
        OperationColumnFilter("number"),
        OperationColumnFilter("user_id", title="Owner ID"),
        BooleanFilter("is_deleted"),
    ]
    column_sortable_list: ClassVar[Sequence] = [
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
        Vault.created_at,
        Vault.updated_at,
    ]
    column_default_sort: ClassVar[SortColumns] = [(Vault.created_at, True)]

    icon = "fa-solid fa-house-lock"

    @expose("/incidents", methods=["GET"])
    async def incidents_page(self, request: Request) -> Response:
        return await render_incident_controls(self, request)

    @expose("/incidents", methods=["POST"])
    async def incidents(self, request: Request) -> Response:
        return await submit_incident_controls(self, request)

    @action(name="pause", label=support_operations["pause"])
    async def pause(self, request: Request) -> Response:
        return await confirm_action(self, request, "pause")

    @action(name="resume", label=support_operations["resume"])
    async def resume(self, request: Request) -> Response:
        return await confirm_action(self, request, "resume")


class StorageAdmin(AdminModelView, model=Storage):
    category = "Vault operations"
    column_list: ClassVar[str | Sequence] = [
        Storage.id,
        Storage.vault,
        Storage.used_space,
        Storage.max_space,
    ]

    icon = "fa-solid fa-box"


class ItemAdmin(AdminModelView, model=Item):
    category = "Catalog & inventory"
    column_default_sort: ClassVar[SortColumns] = [(Item.name, False)]
    column_filters: ClassVar[Sequence] = [AllUniqueStringValuesFilter("rarity")]
    column_sortable_list: ClassVar[Sequence] = [Item.name, Item.rarity, Item.value]
    column_list: ClassVar[str | Sequence] = [Item.id, Item.name, Item.item_type, Item.rarity, Item.value, Item.storage]
    column_searchable_list: ClassVar[Sequence] = [Item.name]

    icon = "fa-solid fa-boxes-stacked"


class DwellerAdmin(AdminModelView, model=Dweller):
    category = "Vault operations"
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        StaticValuesFilter("status", [(v.value, v.value.title()) for v in DwellerStatusEnum]),
        StaticValuesFilter("age_group", [(v.value, v.value.title()) for v in AgeGroupEnum]),
        BooleanFilter("is_dead"),
        BooleanFilter("is_deleted"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(Dweller.created_at, True)]
    column_sortable_list: ClassVar[Sequence] = [
        Dweller.first_name,
        Dweller.last_name,
        Dweller.level,
        Dweller.health,
        Dweller.happiness,
        Dweller.age_group,
        Dweller.status,
        Dweller.created_at,
    ]
    column_list: ClassVar[str | Sequence] = [
        Dweller.first_name,
        Dweller.last_name,
        Dweller.vault,
        Dweller.room,
        Dweller.age_group,
        Dweller.status,
        Dweller.level,
        Dweller.health,
        Dweller.happiness,
        Dweller.is_dead,
    ]
    column_searchable_list: ClassVar[Sequence] = [Dweller.first_name, Dweller.last_name]
    column_labels: ClassVar[dict] = {Dweller.max_health: "Max HP", Dweller.health: "HP"}

    icon = "fa-solid fa-person"


class JunkAdmin(AdminModelView, model=Junk):
    category = "Catalog & inventory"
    column_default_sort: ClassVar[SortColumns] = [(Junk.name, False)]
    column_filters: ClassVar[Sequence] = [AllUniqueStringValuesFilter("rarity")]
    column_sortable_list: ClassVar[Sequence] = [Junk.name, Junk.rarity, Junk.value]
    column_searchable_list: ClassVar[Sequence] = [Junk.name]
    column_list: ClassVar[str | Sequence] = [
        Junk.id,
        Junk.name,
        Junk.rarity,
        Junk.value,
        Junk.junk_type,
        Junk.description,
    ]

    name = "Junk item"
    name_plural = "Junk"

    icon = "fa-solid fa-trash"


class OutfitAdmin(AdminModelView, model=Outfit):
    category = "Catalog & inventory"
    column_default_sort: ClassVar[SortColumns] = [(Outfit.name, False)]
    column_filters: ClassVar[Sequence] = [AllUniqueStringValuesFilter("rarity")]
    column_sortable_list: ClassVar[Sequence] = [Outfit.name, Outfit.rarity, Outfit.value]
    column_searchable_list: ClassVar[Sequence] = [Outfit.name]
    column_list: ClassVar[str | Sequence] = [
        Outfit.id,
        Outfit.name,
        Outfit.rarity,
        Outfit.value,
        Outfit.outfit_type,
        Outfit.gender,
    ]

    icon = "fa-solid fa-tshirt"


class QuestAdmin(AdminModelView, model=Quest):
    category = "Progression & social"
    column_list: ClassVar[str | Sequence] = [
        Quest.title,
        Quest.quest_type,
        Quest.quest_category,
        Quest.chain_id,
        Quest.chain_order,
        Quest.duration_minutes,
    ]
    column_searchable_list: ClassVar[Sequence] = [Quest.title, Quest.short_description]
    column_sortable_list: ClassVar[Sequence] = [
        Quest.title,
        Quest.quest_type,
        Quest.quest_category,
        Quest.chain_order,
        Quest.duration_minutes,
        Quest.created_at,
    ]
    column_default_sort: ClassVar[SortColumns] = [(Quest.created_at, True)]

    icon = "fa-solid fa-book-open"

    can_export = True


class ObjectiveAdmin(AdminModelView, model=Objective):
    category = "Progression & social"
    column_list: ClassVar[str | Sequence] = [
        Objective.id,
        Objective.challenge,
        Objective.reward,
    ]
    column_searchable_list: ClassVar[Sequence] = [Objective.challenge, Objective.reward]
    column_sortable_list: ClassVar[Sequence] = [Objective.challenge]

    icon = "fa-solid fa-bullseye"

    can_export = True


class RoomAdmin(AdminModelView, model=Room):
    category = "Vault operations"
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        AllUniqueStringValuesFilter("category"),
    ]
    column_searchable_list: ClassVar[Sequence] = [Room.name]
    column_sortable_list: ClassVar[Sequence] = [Room.name, Room.tier, Room.size, Room.created_at]
    column_list: ClassVar[str | Sequence] = [Room.name, Room.vault, Room.category, Room.ability, Room.tier, Room.size]

    icon = "fa-solid fa-door-open"


class WeaponAdmin(AdminModelView, model=Weapon):
    category = "Catalog & inventory"
    column_default_sort: ClassVar[SortColumns] = [(Weapon.name, False)]
    column_filters: ClassVar[Sequence] = [AllUniqueStringValuesFilter("rarity")]
    column_sortable_list: ClassVar[Sequence] = [Weapon.name, Weapon.rarity, Weapon.value]
    column_searchable_list: ClassVar[Sequence] = [Weapon.name]
    column_list: ClassVar[str | Sequence] = [
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
    can_export = False
    category = "AI & diagnostics"
    column_list: ClassVar[str | Sequence] = [
        Prompt.id,
        Prompt.prompt_name,
        Prompt.version,
        Prompt.is_active,
        Prompt.description,
        Prompt.entity_id,
    ]
    # Templates are a constrained interface: details previews the raw template;
    # edits go through the deferred copy-as-new-version flow, never in place.
    column_details_exclude_list: ClassVar[Sequence] = [Prompt.llm_interactions]
    column_searchable_list: ClassVar[Sequence] = [Prompt.prompt_name, Prompt.description]
    column_filters: ClassVar[Sequence] = [
        BooleanFilter(col(Prompt.is_active)),  # ty: ignore[invalid-argument-type]
        AllUniqueStringValuesFilter(col(Prompt.version)),  # ty: ignore[invalid-argument-type]
    ]
    column_default_sort: ClassVar[SortColumns] = [
        (Prompt.is_active, True),
        (Prompt.version, True),
    ]

    icon = "fa-solid fa-comment-dots"


class GameStateAdmin(AdminModelView, model=GameState):
    category = "Vault operations"
    column_default_sort: ClassVar[SortColumns] = [(GameState.last_tick_time, False)]
    column_filters: ClassVar[Sequence] = [
        BooleanFilter("is_paused"),
        BooleanFilter("is_active"),
        OperationColumnFilter("vault_id", title="Vault ID"),
    ]
    column_sortable_list: ClassVar[Sequence] = [
        GameState.last_tick_time,
        GameState.last_activity_time,
        GameState.total_game_time,
    ]
    column_list: ClassVar[str | Sequence] = [
        GameState.vault_id,
        GameState.is_active,
        GameState.is_paused,
        GameState.last_tick_time,
        GameState.last_activity_time,
        GameState.total_game_time,
    ]

    name = "Game State"
    name_plural = "Game States"
    icon = "fa-solid fa-clock"


class LLInteractionAdmin(AdminModelView, model=LLMInteraction):
    can_export = False
    category = "AI & diagnostics"
    name = "LLM Interaction"
    name_plural = "LLM Interactions"
    column_list: ClassVar[str | Sequence] = [
        LLMInteraction.usage,
        LLMInteraction.user,
        LLMInteraction.provider,
        LLMInteraction.model,
        LLMInteraction.total_tokens,
        LLMInteraction.created_at,
    ]
    column_searchable_list: ClassVar[Sequence] = [LLMInteraction.usage]
    column_filters: ClassVar[Sequence] = [
        AllUniqueStringValuesFilter(col(LLMInteraction.usage)),  # ty: ignore[invalid-argument-type]
        AllUniqueStringValuesFilter(col(LLMInteraction.provider)),  # ty: ignore[invalid-argument-type]
        AllUniqueStringValuesFilter(col(LLMInteraction.model)),  # ty: ignore[invalid-argument-type]
    ]
    column_sortable_list: ClassVar[Sequence] = [
        LLMInteraction.usage,
        LLMInteraction.created_at,
        LLMInteraction.total_tokens,
    ]
    column_default_sort: ClassVar[SortColumns] = [(LLMInteraction.created_at, True)]

    icon = "fa-solid fa-comment-dots"


class RelationshipAdmin(AdminModelView, model=Relationship):
    category = "Progression & social"
    column_sortable_list: ClassVar[Sequence] = [Relationship.updated_at]
    column_default_sort: ClassVar[SortColumns] = [(Relationship.updated_at, True)]
    column_filters: ClassVar[Sequence] = [AllUniqueStringValuesFilter("relationship_type")]
    column_list: ClassVar[str | Sequence] = [
        Relationship.dweller_1_id,
        Relationship.dweller_2_id,
        Relationship.relationship_type,
        Relationship.affinity,
        Relationship.updated_at,
    ]

    name = "Relationship"
    name_plural = "Relationships"
    icon = "fa-solid fa-heart"


class PregnancyAdmin(AdminModelView, model=Pregnancy):
    category = "Progression & social"
    column_sortable_list: ClassVar[Sequence] = [Pregnancy.due_at]
    column_default_sort: ClassVar[SortColumns] = [(Pregnancy.due_at, True)]
    column_filters: ClassVar[Sequence] = [AllUniqueStringValuesFilter("status")]
    column_list: ClassVar[str | Sequence] = [
        Pregnancy.mother_id,
        Pregnancy.father_id,
        Pregnancy.status,
        Pregnancy.due_at,
    ]

    name = "Pregnancy"
    name_plural = "Pregnancies"
    icon = "fa-solid fa-baby"


class TrainingAdmin(AdminModelView, model=Training):
    support_operations: ClassVar[dict[str, str]] = {"cancel-training": "Cancel training"}
    category = "Vault operations"
    column_default_sort: ClassVar[SortColumns] = [(Training.started_at, True)]
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        AllUniqueStringValuesFilter("status"),
        AllUniqueStringValuesFilter("stat_being_trained"),
    ]
    column_sortable_list: ClassVar[Sequence] = [
        Training.progress,
        Training.estimated_completion_at,
        Training.started_at,
    ]
    column_list: ClassVar[str | Sequence] = [
        Training.dweller,
        Training.vault,
        Training.room,
        Training.stat_being_trained,
        Training.goal_stat_value,
        Training.progress,
        Training.status,
        Training.estimated_completion_at,
    ]

    name = "Training"
    name_plural = "Training Sessions"
    icon = "fa-solid fa-dumbbell"

    @action(name="cancel-training", label=support_operations["cancel-training"])
    async def cancel_training(self, request: Request) -> Response:
        return await confirm_action(self, request, "cancel-training")


class IncidentAdmin(AdminModelView, model=Incident):
    category = "Vault operations"
    column_sortable_list: ClassVar[Sequence] = [Incident.start_time]
    column_default_sort: ClassVar[SortColumns] = [(Incident.start_time, True)]
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        AllUniqueStringValuesFilter("status"),
    ]
    column_list: ClassVar[str | Sequence] = [
        Incident.vault_id,
        Incident.room_id,
        Incident.type,
        Incident.status,
        Incident.difficulty,
        Incident.start_time,
    ]

    name = "Incident"
    name_plural = "Incidents"
    icon = "fa-solid fa-exclamation-triangle"


class ExplorationAdmin(AdminModelView, model=Exploration):
    support_operations: ClassVar[dict[str, str]] = {"recall": "Recall explorer"}
    category = "Vault operations"
    column_sortable_list: ClassVar[Sequence] = [Exploration.start_time]
    column_default_sort: ClassVar[SortColumns] = [(Exploration.start_time, True)]
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        AllUniqueStringValuesFilter("status"),
    ]
    column_list: ClassVar[str | Sequence] = [
        Exploration.vault_id,
        Exploration.dweller_id,
        Exploration.status,
        Exploration.start_time,
        Exploration.return_completes_at,
        Exploration.total_distance,
        Exploration.total_caps_found,
    ]

    name = "Exploration"
    name_plural = "Explorations"
    icon = "fa-solid fa-map-marked-alt"

    @action(name="recall", label=support_operations["recall"])
    async def recall(self, request: Request) -> Response:
        return await confirm_action(self, request, "recall")


class ChatMessageAdmin(AdminModelView, model=ChatMessage):
    category = "AI & diagnostics"
    column_filters: ClassVar[Sequence] = [OperationColumnFilter("vault_id", title="Vault ID")]
    column_list: ClassVar[str | Sequence] = [
        ChatMessage.vault_id,
        ChatMessage.from_user_id,
        ChatMessage.from_dweller_id,
        ChatMessage.message_text,
        ChatMessage.happiness_delta,
        ChatMessage.created_at,
    ]
    column_searchable_list: ClassVar[Sequence] = [ChatMessage.message_text, ChatMessage.happiness_reason]
    column_sortable_list: ClassVar[Sequence] = [ChatMessage.created_at, ChatMessage.happiness_delta]
    column_default_sort: ClassVar[SortColumns] = [(ChatMessage.created_at, True)]

    column_formatters: ClassVar[dict] = {
        **AdminModelView.column_formatters,
        ChatMessage.message_text: lambda m, _attribute: _truncate(m.message_text),
    }

    name = "Chat Message"
    name_plural = "Chat Messages"
    icon = "fa-solid fa-message"


class NotificationAdmin(AdminModelView, model=Notification):
    category = "AI & diagnostics"
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        BooleanFilter("is_read"),
        BooleanFilter("is_dismissed"),
        AllUniqueStringValuesFilter("notification_type"),
    ]
    column_list: ClassVar[str | Sequence] = [
        Notification.user_id,
        Notification.vault_id,
        Notification.notification_type,
        Notification.priority,
        Notification.title,
        Notification.is_read,
        Notification.created_at,
    ]
    column_searchable_list: ClassVar[Sequence] = [Notification.title, Notification.message]
    column_sortable_list: ClassVar[Sequence] = [
        Notification.created_at,
        Notification.priority,
        Notification.notification_type,
    ]
    column_default_sort: ClassVar[SortColumns] = [(Notification.created_at, True)]

    name = "Notification"
    name_plural = "Notifications"
    icon = "fa-solid fa-bell"


class TeamAdmin(AdminModelView, model=Team):
    category = "Progression & social"
    column_list: ClassVar[str | Sequence] = [
        Team.id,
        Team.vault,
        Team.hazard_team,
        Team.quest_id,
        Team.incident_id,
        Team.name,
        Team.created_at,
        Team.updated_at,
    ]
    column_sortable_list: ClassVar[Sequence] = [Team.created_at, Team.hazard_team]
    column_default_sort: ClassVar[SortColumns] = [(Team.created_at, True)]
    column_labels: ClassVar[dict] = {
        Team.hazard_team: "Hazard team",
        Team.quest_id: "Quest",
        Team.incident_id: "Incident",
    }

    name = "Team"
    name_plural = "Teams"
    icon = "fa-solid fa-people-group"


class TeamMemberAdmin(AdminModelView, model=TeamMember):
    category = "Progression & social"
    column_list: ClassVar[str | Sequence] = [
        TeamMember.id,
        TeamMember.team,
        TeamMember.dweller,
        TeamMember.slot_number,
        TeamMember.status,
        TeamMember.created_at,
    ]
    column_sortable_list: ClassVar[Sequence] = [TeamMember.created_at, TeamMember.status]
    column_default_sort: ClassVar[SortColumns] = [(TeamMember.created_at, True)]
    column_labels: ClassVar[dict] = {TeamMember.slot_number: "Slot", TeamMember.team: "Team"}

    name = "Team member"
    name_plural = "Team members"
    icon = "fa-solid fa-user-group"


class CraftingOrderAdmin(AdminModelView, model=CraftingOrder):
    category = "Vault operations"
    name = "Crafting order"
    name_plural = "Crafting orders"
    icon = "fa-solid fa-hammer"
    column_list: ClassVar[str | Sequence] = [
        CraftingOrder.vault,
        CraftingOrder.room,
        CraftingOrder.item_name,
        CraftingOrder.status,
        CraftingOrder.progress,
        CraftingOrder.estimated_completion_at,
    ]
    column_searchable_list: ClassVar[Sequence] = [CraftingOrder.item_name]
    column_sortable_list: ClassVar[Sequence] = [
        CraftingOrder.item_name,
        CraftingOrder.progress,
        CraftingOrder.estimated_completion_at,
        CraftingOrder.started_at,
    ]
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        AllUniqueStringValuesFilter("status"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(CraftingOrder.started_at, True)]


class VaultQuestAdmin(AdminModelView, model=VaultQuestCompletionLink):
    category = "Progression & social"
    name = "Vault quest"
    name_plural = "Vault quest progress"
    icon = "fa-solid fa-route"
    column_list: ClassVar[str | Sequence] = [
        VaultQuestCompletionLink.vault_id,
        VaultQuestCompletionLink.quest_id,
        VaultQuestCompletionLink.started_at,
        VaultQuestCompletionLink.return_completes_at,
        VaultQuestCompletionLink.is_reward_ready,
        VaultQuestCompletionLink.is_completed,
    ]
    column_sortable_list: ClassVar[Sequence] = [
        VaultQuestCompletionLink.started_at,
        VaultQuestCompletionLink.return_completes_at,
    ]
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("vault_id", title="Vault ID"),
        BooleanFilter("is_reward_ready"),
        BooleanFilter("is_completed"),
        BooleanFilter("is_visible"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(VaultQuestCompletionLink.started_at, True)]


class PetAdmin(AdminModelView, model=Pet):
    category = "Catalog & inventory"
    icon = "fa-solid fa-paw"
    column_list: ClassVar[str | Sequence] = [Pet.name, Pet.rarity, Pet.dweller, Pet.storage_id]
    column_searchable_list: ClassVar[Sequence] = [Pet.name]
    column_sortable_list: ClassVar[Sequence] = [Pet.name, Pet.rarity, Pet.created_at]
    column_filters: ClassVar[Sequence] = [
        AllUniqueStringValuesFilter("rarity"),
        OperationColumnFilter("storage_id", title="Storage ID"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(Pet.created_at, True)]


class OAuthAccountAdmin(AdminModelView, model=OAuthAccount):
    can_export = False
    category = "Accounts"
    name = "Linked provider"
    name_plural = "Linked sign-in providers"
    icon = "fa-solid fa-key"
    column_list: ClassVar[str | Sequence] = [OAuthAccount.user_id, OAuthAccount.provider, OAuthAccount.created_at]
    column_sortable_list: ClassVar[Sequence] = [OAuthAccount.provider, OAuthAccount.created_at]
    column_filters: ClassVar[Sequence] = [
        StaticValuesFilter("provider", [("google", "Google"), ("github", "GitHub")]),
        OperationColumnFilter("user_id", title="User ID"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(OAuthAccount.created_at, True)]


class QuestRequirementAdmin(AdminModelView, model=QuestRequirement):
    category = "Progression & social"
    name = "Quest requirement"
    name_plural = "Quest requirements"
    icon = "fa-solid fa-list-check"
    column_list: ClassVar[str | Sequence] = [
        QuestRequirement.quest,
        QuestRequirement.requirement_type,
        QuestRequirement.requirement_data,
        QuestRequirement.is_mandatory,
    ]
    column_sortable_list: ClassVar[Sequence] = [QuestRequirement.requirement_type, QuestRequirement.is_mandatory]
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("quest_id", title="Quest ID"),
        AllUniqueStringValuesFilter("requirement_type"),
        BooleanFilter("is_mandatory"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(QuestRequirement.quest_id, False)]


class QuestRewardAdmin(AdminModelView, model=QuestReward):
    category = "Progression & social"
    name = "Quest reward"
    name_plural = "Quest rewards"
    icon = "fa-solid fa-gift"
    column_list: ClassVar[str | Sequence] = [
        QuestReward.quest,
        QuestReward.reward_type,
        QuestReward.reward_data,
        QuestReward.reward_chance,
    ]
    column_sortable_list: ClassVar[Sequence] = [QuestReward.reward_type, QuestReward.reward_chance]
    column_filters: ClassVar[Sequence] = [
        OperationColumnFilter("quest_id", title="Quest ID"),
        AllUniqueStringValuesFilter("reward_type"),
    ]
    column_default_sort: ClassVar[SortColumns] = [(QuestReward.quest_id, False)]
