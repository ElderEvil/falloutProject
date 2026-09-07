"""Business rules for dweller medical recommendations and supply usage."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.dweller import dweller as dweller_crud
from app.models import Storage
from app.models.dweller import Dweller
from app.schemas.chat import MedicalAidStatus, MedicalRecommendation
from app.schemas.dweller import DwellerReadFull, DwellerUpdate
from app.services.radiation_service import radiation_removal_amount
from app.utils.exceptions import ContentNoChangeException, ResourceConflictException


async def get_available_medical_supplies(
    db_session: AsyncSession,
    dweller: DwellerReadFull,
    vault_id: UUID4,
) -> tuple[int, int]:
    """Return the dweller's carried and vault-stored medical supplies."""
    storage_result = await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    storage = storage_result.scalar_one_or_none()
    storage_stimpaks = (storage.stimpack or 0) if storage else 0
    storage_radaways = (storage.radaway or 0) if storage else 0
    return (dweller.stimpack or 0) + storage_stimpaks, (dweller.radaway or 0) + storage_radaways


async def get_dweller_medical_status(
    db_session: AsyncSession,
    dweller: DwellerReadFull,
    vault_id: UUID4,
) -> MedicalAidStatus:
    """Read live health, radiation, and supply state for a dweller."""
    available_stimpaks, available_radaways = await get_available_medical_supplies(db_session, dweller, vault_id)
    effective_max_health = dweller.effective_max_health
    health_percent = dweller.health / effective_max_health * 100
    radiation_percent = dweller.radiation / max(dweller.max_health, 1) * 100

    if health_percent < 50 and available_stimpaks > 0:
        recommended_action: MedicalRecommendation = "request_stimpak"
    elif radiation_percent >= 30 and available_radaways > 0:
        recommended_action = "request_radaway"
    else:
        recommended_action = "none"

    return MedicalAidStatus(
        health_percent=round(health_percent, 1),
        radiation_percent=round(radiation_percent, 1),
        available_stimpaks=available_stimpaks,
        available_radaways=available_radaways,
        recommended_action=recommended_action,
    )


async def use_stimpack(db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
    """Spend one carried stimpack and heal the dweller up to the radiation-reduced ceiling."""
    dweller_obj = await dweller_crud.get(db_session, dweller_id)

    if dweller_obj.stimpack <= 0:
        raise ResourceConflictException(detail="No stimpacks available to use.")

    if dweller_obj.health >= dweller_obj.effective_max_health:
        raise ContentNoChangeException(detail="Dweller is already at full health.")

    heal_amount = max(1, int(dweller_obj.max_health * game_config.health.stimpack_heal_percent))
    new_health = min(dweller_obj.health + heal_amount, dweller_obj.effective_max_health)

    return await dweller_crud.update(
        db_session, dweller_id, DwellerUpdate(health=new_health, stimpack=dweller_obj.stimpack - 1)
    )


async def use_radaway(db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
    """Spend one carried RadAway and remove a configured share of the dweller's radiation."""
    dweller_obj = await dweller_crud.get(db_session, dweller_id)

    if dweller_obj.radaway <= 0:
        raise ResourceConflictException(detail="No radaways available to use.")

    if dweller_obj.radiation <= 0:
        raise ContentNoChangeException(detail="Dweller has no radiation to remove.")

    new_radiation = dweller_obj.radiation - radiation_removal_amount(dweller_obj.radiation)

    return await dweller_crud.update(
        db_session, dweller_id, DwellerUpdate(radiation=new_radiation, radaway=dweller_obj.radaway - 1)
    )
