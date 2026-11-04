"""Own elective perk selection and its atomic progression notification."""

from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerPerk, NotificationType
from app.models.dweller import Dweller
from app.options.perks import PERKS
from app.schemas.perk import DwellerPerksRead, PerkDefinition, PerkOption
from app.services.notification_service import notification_service
from app.utils.exceptions import (
    AccessDeniedException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)


def _unavailable_reason(dweller: Dweller, perk: PerkDefinition) -> str | None:
    if dweller.selected_perk:
        return "This dweller has already chosen their perk."
    if dweller.is_dead or dweller.is_deleted or not dweller.is_mature:
        return "Only living adult dwellers can choose a perk."
    if not dweller.is_in_vault:
        return "Choose a perk after returning to the vault."
    if dweller.level < perk.minimum_level:
        return f"Requires level {perk.minimum_level}."
    if getattr(dweller, perk.stat) < perk.minimum_stat:
        return f"Requires trained {perk.stat} {perk.minimum_stat}; equipment bonuses do not count."
    return None


def perk_view(dweller: Dweller) -> DwellerPerksRead:
    return DwellerPerksRead(
        dweller_id=dweller.id,
        selected_perk=DwellerPerk(dweller.selected_perk) if dweller.selected_perk else None,
        options=[
            PerkOption(
                **perk.model_dump(),
                eligible=(reason := _unavailable_reason(dweller, perk)) is None,
                unavailable_reason=reason,
            )
            for perk in PERKS.values()
        ],
    )


class PerkService:
    async def get_perks(self, db: AsyncSession, dweller_id: UUID) -> DwellerPerksRead:
        return perk_view(await crud.dweller.get(db, dweller_id))

    async def select(self, db: AsyncSession, dweller_id: UUID, perk: DwellerPerk, user_id: UUID) -> DwellerPerksRead:
        """The row lock, perk and notification persist under this one commit."""
        notification_service.discard_deferred_notifications(db)
        try:
            dweller = await crud.dweller.get_for_update(db, dweller_id)
            if dweller is None or dweller.vault_id is None:
                raise ResourceNotFoundException(Dweller, identifier=dweller_id)
            vault = await crud.vault.get(db, dweller.vault_id)
            if vault.user_id != user_id:
                raise AccessDeniedException("This dweller no longer belongs to your vault.")
            if dweller.selected_perk:
                raise ResourceConflictException("This dweller has already chosen their perk.")
            if reason := _unavailable_reason(dweller, PERKS[perk]):
                raise ValidationException(reason)
            dweller.selected_perk = perk.value
            db.add(dweller)
            await db.flush()
            await notification_service.create_and_send(
                db,
                user_id=user_id,
                vault_id=dweller.vault_id,
                from_dweller_id=dweller.id,
                notification_type=NotificationType.PERK_UNLOCKED,
                title="Explorer perk learned",
                message=f"{dweller.display_name} learned {PERKS[perk].name}.",
                meta_data={"perk": perk.value},
                commit=False,
            )
            view = perk_view(dweller)
            await db.commit()
            await notification_service.deliver_deferred_notifications(db)
            return view
        finally:
            notification_service.discard_deferred_notifications(db)


perk_service = PerkService()
