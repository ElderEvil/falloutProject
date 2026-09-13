"""Single reward contract shared by settlement, API responses, and presentation.

Every grant_* service method returns a plain dict that validates against
GrantedReward. The API boundary validates before serializing, so caps, items,
XP, dwellers, and lunchboxes agree exactly across backend settlement, API
responses, notifications, and frontend presentation.
"""

from typing import Annotated, Literal

from pydantic import UUID4, Field, TypeAdapter
from sqlmodel import SQLModel


class CapsGranted(SQLModel):
    reward_type: Literal["caps"] = "caps"
    amount: int


class ItemGranted(SQLModel):
    reward_type: Literal["item"] = "item"
    item_type: str
    name: str
    amount: int = 1
    item_id: str | None = None
    item_ids: list[str] = Field(default_factory=list)
    dweller_ids: list[str] = Field(default_factory=list)
    dweller_id: str | None = None


class DwellerGranted(SQLModel):
    reward_type: Literal["dweller"] = "dweller"
    dweller_id: str
    name: str


class ResourceGranted(SQLModel):
    reward_type: Literal["resource"] = "resource"
    resource_type: Literal["food", "water", "power"]
    amount: int


class ExperienceGranted(SQLModel):
    reward_type: Literal["experience"] = "experience"
    amount: int
    dweller_ids: list[str] = Field(default_factory=list)
    leveled_up: list[str] = Field(default_factory=list)
    name: str | None = None


class MedicationGranted(SQLModel):
    reward_type: Literal["stimpak", "radaway"] = "stimpak"
    amount: int
    dweller_id: str | None = None
    message: str | None = None


GrantedReward = Annotated[
    CapsGranted | ItemGranted | DwellerGranted | ResourceGranted | ExperienceGranted | MedicationGranted,
    Field(discriminator="reward_type"),
]

granted_reward_adapter = TypeAdapter(GrantedReward)

_MEDICATION_LABELS = {"stimpak": "Stimpak", "radaway": "RadAway"}


class LunchboxOpenedItem(SQLModel):
    name: str
    type: str
    rarity: str


class LunchboxOpened(SQLModel):
    """Payload returned when a player opens an unopened lunchbox Item."""

    reward_type: Literal["lunchbox"] = "lunchbox"
    items: list[LunchboxOpenedItem] = Field(default_factory=list)
    dweller: DwellerGranted


class LunchboxOpenRequest(SQLModel):
    item_id: UUID4


def format_reward_summary(granted: GrantedReward | list[GrantedReward]) -> str:
    """Render granted rewards the same way for logs, notifications, and toasts."""
    items = granted if isinstance(granted, list) else [granted]
    return ", ".join(_format_single(item) for item in items)


def _format_single(granted: GrantedReward) -> str:
    """Render one settled reward; see format_reward_summary for the shared contract."""
    if isinstance(granted, CapsGranted):
        return f"{granted.amount} caps"
    if isinstance(granted, ResourceGranted):
        return f"{granted.amount} {granted.resource_type}"
    if isinstance(granted, ExperienceGranted):
        return granted.name or f"{granted.amount} XP"
    if isinstance(granted, DwellerGranted):
        return granted.name
    if isinstance(granted, MedicationGranted):
        label = _MEDICATION_LABELS[granted.reward_type]
        return f"{granted.amount} {label}" if granted.amount else label
    quantity = f"{granted.amount}x " if granted.amount > 1 else ""
    return f"{quantity}{granted.name}"
