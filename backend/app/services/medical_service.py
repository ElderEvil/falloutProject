"""Business rules for dweller medical recommendations."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Storage
from app.schemas.chat import MedicalAidStatus, MedicalRecommendation
from app.schemas.dweller import DwellerReadFull


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
    max_health = max(dweller.max_health, 1)
    health_percent = dweller.health / max_health * 100
    radiation_percent = dweller.radiation / max_health * 100

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
