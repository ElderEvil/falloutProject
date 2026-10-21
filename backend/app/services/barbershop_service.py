"""Barbershop availability, appearance changes, and portrait/AI gates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app import crud
from app.core.game_config import game_config
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.options.races import RaceOption, race_of
from app.schemas.barbershop import BarbershopChangeRequest, BarbershopChangeResponse, BarbershopStatus
from app.schemas.dweller import DwellerUpdate
from app.services.vault_service import vault_service
from app.utils.dweller_assets import (
    HUMAN_PORTRAIT_HAIR_COLORS,
    HUMAN_PORTRAIT_SKIN_TONES,
    is_default_dweller_image,
)
from app.utils.exceptions import (
    AccessDeniedException,
    BarbershopRequiredException,
    ContentNoChangeException,
    ResourceNotFoundException,
    ValidationException,
)

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.room import Room

BARBERSHOP_ROOM_NAME = "Barbershop"


class BarbershopService:
    """Gate appearance work behind a built, staffed Barbershop."""

    @staticmethod
    def _is_barbershop(room: Room) -> bool:
        return room.name.casefold() == BARBERSHOP_ROOM_NAME.casefold()

    async def _barbershop_rooms(self, db_session: AsyncSession, vault_id: UUID4) -> list[Room]:
        rooms = await crud.room.get_all_by_vault(db_session, vault_id)
        return [room for room in rooms if self._is_barbershop(room)]

    async def _find_room(self, db_session: AsyncSession, vault_id: UUID4) -> Room | None:
        rooms = await self._barbershop_rooms(db_session, vault_id)
        return rooms[0] if rooms else None

    async def _is_staffed(self, db_session: AsyncSession, room: Room | None) -> bool:
        return room is not None and await crud.dweller.count_in_room(db_session, room.id) > 0

    async def get_status(
        self, db_session: AsyncSession, vault_id: UUID4, *, room: Room | None = None
    ) -> BarbershopStatus:
        """Return availability, fee, caps, and the preset swatches for a vault."""
        vault = await crud.vault.get(db_session, vault_id)
        if vault is None:
            raise ResourceNotFoundException(model=Vault, identifier=vault_id)

        rooms = await self._barbershop_rooms(db_session, vault_id)
        if room is None:
            staffed_room = None
            for candidate in rooms:
                if await self._is_staffed(db_session, candidate):
                    staffed_room = candidate
                    break
            room = staffed_room or (rooms[0] if rooms else None)
        if room is not None and (room.vault_id != vault_id or not self._is_barbershop(room)):
            raise ValidationException(detail="This room is not a Barbershop.")

        return BarbershopStatus(
            room_id=room.id if room is not None else None,
            built=room is not None,
            staffed=await self._is_staffed(db_session, room),
            fee=game_config.barbershop.change_cost,
            vault_caps=vault.bottle_caps,
            skin_tones=list(HUMAN_PORTRAIT_SKIN_TONES),
            hair_colors=[color.casefold() for color in HUMAN_PORTRAIT_HAIR_COLORS],
        )

    async def get_status_for_room(self, db_session: AsyncSession, room: Room) -> BarbershopStatus:
        """Return status for the room-scoped Barbershop endpoint."""
        if not self._is_barbershop(room):
            raise ValidationException(detail="This room is not a Barbershop.")
        return await self.get_status(db_session, room.vault_id, room=room)

    async def require_available(self, db_session: AsyncSession, vault_id: UUID4) -> Room:
        """Require at least one built and staffed Barbershop in the vault."""
        rooms = await self._barbershop_rooms(db_session, vault_id)
        if not rooms:
            raise BarbershopRequiredException(
                detail="Build a Barbershop before changing appearance or regenerating portraits."
            )
        for candidate in rooms:
            if await self._is_staffed(db_session, candidate):
                return candidate
        raise BarbershopRequiredException(detail="Assign at least one dweller to the Barbershop first.")

    async def require_available_for_dweller(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        """Require a staffed Barbershop in the dweller's vault."""
        dweller = await crud.dweller.get(db_session, dweller_id)
        if dweller is None or dweller.vault_id is None:
            raise ResourceNotFoundException(model=Dweller, identifier=dweller_id)
        await self.require_available(db_session, dweller.vault_id)
        return dweller

    @staticmethod
    def _canonical(value: str, choices: tuple[str, ...], label: str) -> str:
        folded = value.strip().casefold()
        for choice in choices:
            if choice.casefold() == folded:
                return choice
        raise ValidationException(detail=f"Choose a valid {label}: {', '.join(choices)}.")

    @staticmethod
    def _visual_attributes_changed(current: dict[str, Any], incoming: Any) -> bool:
        if hasattr(incoming, "model_dump"):
            incoming = incoming.model_dump(exclude_unset=True)
        if incoming is None:
            return bool(current)
        if not isinstance(incoming, dict):
            return True
        return any(current.get(key) != value for key, value in incoming.items())

    async def ensure_can_edit_appearance(
        self, db_session: AsyncSession, dweller_id: UUID4, data: dict[str, Any]
    ) -> None:
        """Gate a generic dweller update only when it changes appearance or portrait fields."""
        dweller = await crud.dweller.get(db_session, dweller_id)
        if dweller is None or dweller.vault_id is None:
            raise ResourceNotFoundException(model=Dweller, identifier=dweller_id)

        changed = False
        if "visual_attributes" in data:
            changed = self._visual_attributes_changed(dweller.visual_attributes or {}, data["visual_attributes"])
        if not changed and "image_url" in data and data["image_url"] != dweller.image_url:
            changed = True
        if not changed and "thumbnail_url" in data and data["thumbnail_url"] != dweller.thumbnail_url:
            changed = True
        if changed:
            await self.require_available(db_session, dweller.vault_id)

    async def change_appearance(
        self,
        db_session: AsyncSession,
        *,
        room: Room,
        dweller_id: UUID4,
        request: BarbershopChangeRequest,
    ) -> BarbershopChangeResponse:
        """Apply a preset skin/hair change, deducting the fee in one transaction."""
        if not self._is_barbershop(room):
            raise ValidationException(detail="This room is not a Barbershop.")

        dweller = await crud.dweller.get(db_session, dweller_id)
        if dweller is None:
            raise ResourceNotFoundException(model=Dweller, identifier=dweller_id)
        if dweller.vault_id != room.vault_id:
            raise AccessDeniedException(detail="Dweller does not belong to this vault.")
        if not dweller.is_mature:
            raise ValidationException(detail="Only adult or elder dwellers can use the Barbershop.")
        if dweller.is_dead or dweller.is_deleted:
            raise ValidationException(detail="This dweller cannot use the Barbershop right now.")
        if race_of(dweller) is not RaceOption.HUMAN:
            raise ValidationException(detail="Only human dwellers can use the Barbershop.")

        skin_tone = self._canonical(request.skin_tone, HUMAN_PORTRAIT_SKIN_TONES, "skin tone")
        hair_color = self._canonical(request.hair_color, HUMAN_PORTRAIT_HAIR_COLORS, "hair color").casefold()

        current = dweller.visual_attributes or {}
        current_skin = current.get("skin_tone")
        current_hair = current.get("hair_color")
        if (
            isinstance(current_skin, str)
            and isinstance(current_hair, str)
            and current_skin.casefold() == skin_tone.casefold()
            and current_hair.casefold() == hair_color.casefold()
        ):
            raise ContentNoChangeException(detail="The dweller already has that appearance.")

        if not await self._is_staffed(db_session, room):
            raise BarbershopRequiredException(detail="Assign at least one dweller to this Barbershop first.")

        vault_id = dweller.vault_id
        if vault_id is None:
            raise ResourceNotFoundException(model=Vault, identifier=dweller.id)
        vault = await vault_crud.get_for_update(db_session, vault_id)
        if vault is None:
            raise ResourceNotFoundException(model=Vault, identifier=vault_id)

        custom_art = (dweller.image_url and not is_default_dweller_image(dweller.image_url)) or (
            dweller.thumbnail_url and not is_default_dweller_image(dweller.thumbnail_url)
        )
        fee = game_config.barbershop.change_cost
        remaining_caps = vault.bottle_caps - fee

        try:
            await vault_service.withdraw_caps(
                db_session=db_session,
                vault_obj=vault,
                amount=fee,
                commit=False,
            )
            attributes = dict(current)
            attributes["skin_tone"] = skin_tone
            attributes["hair_color"] = hair_color
            await crud.dweller.update(
                db_session,
                dweller.id,
                DwellerUpdate(visual_attributes=attributes),
                commit=False,
            )
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

        updated = await crud.dweller.get_full_info(db_session, dweller.id)
        return BarbershopChangeResponse(
            dweller=updated,
            portrait_updated=not bool(custom_art),
            fee=fee,
            remaining_caps=remaining_caps,
        )


barbershop_service = BarbershopService()
