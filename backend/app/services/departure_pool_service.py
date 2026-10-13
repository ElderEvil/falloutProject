"""Shared recruitment pool: claim a living departure into a new vault.

A departure is a living person with no active vault (canonical ``wasteland``/``departure``).
Once past the eligibility delay and with reusable content, they appear in the shared pool and
any vault may recruit them for caps. A claim preserves the person — same id, age, appearance,
stats and authored history — and transfers ownership atomically under a row lock, so a
concurrent double claim cannot create two owners. Equipment is left with the source vault.
"""

import logging
from datetime import UTC, datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AvailabilityEnum, ContentProvenanceEnum, DwellerStatusEnum, LifecycleEnum
from app.crud.dweller import dweller as dweller_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.trading_post_service import trade_value
from app.services.vault_service import vault_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException

logger = logging.getLogger(__name__)

POOL_SIZE = 20

_REUSABLE_PROVENANCES = frozenset({ContentProvenanceEnum.CURATED, ContentProvenanceEnum.GENERATED})


def _consent_ok(dweller: Dweller) -> bool:
    """System/curated content is always reusable; player-authored content needs consent."""
    if dweller.content_provenance in _REUSABLE_PROVENANCES:
        return True
    if dweller.content_provenance is None:
        return False
    return dweller.sharing_consent is True


class DeparturePoolService:
    """List and atomically claim living departures from the shared pool."""

    async def list_pool(self, db_session: AsyncSession, vault: Vault) -> list[Dweller]:
        """Departures eligible for a vault to recruit, excluding its own departures."""
        return list(await dweller_crud.get_pool_eligible(db_session, exclude_vault_id=vault.id, limit=POOL_SIZE))

    async def claim(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> Dweller:
        """Recruit a departure into ``vault``, preserving identity and stats.

        Atomic: the row is locked FOR UPDATE, so two concurrent claims — or a claim
        racing a relisting — resolve to exactly one winner.
        """
        dweller = await dweller_crud.get_for_update(db_session, dweller_id, include_deleted=True)
        if dweller is None:
            raise ResourceNotFoundException(Dweller, identifier=dweller_id)
        if dweller.availability is not AvailabilityEnum.DEPARTURE:
            raise ResourceConflictException(detail="Dweller is no longer available in the pool")
        if dweller.previous_vault_id == vault.id:
            raise VaultOperationException(detail="You cannot recruit your own departure")

        now = datetime.now(UTC).replace(tzinfo=None)
        if dweller.departure_eligible_at is None or dweller.departure_eligible_at > now:
            raise ResourceConflictException(detail="Dweller is not yet eligible for recruitment")
        if not _consent_ok(dweller):
            raise ResourceConflictException(detail="Dweller's content is not shared for recruitment")

        price = trade_value(dweller)
        await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price, commit=False)
        await self._return_equipment_to_source(db_session, dweller)

        dweller.lifecycle = LifecycleEnum.ALIVE
        dweller.availability = AvailabilityEnum.VAULT
        dweller.vault_id = vault.id
        dweller.previous_vault_id = None
        dweller.room_id = None
        dweller.status = DwellerStatusEnum.IDLE
        dweller.departed_at = None
        dweller.departure_eligible_at = None
        db_session.add(dweller)
        await db_session.commit()
        await db_session.refresh(dweller)

        logger.info("Vault %s recruited departure %s for %d caps", vault.id, dweller_id, price)
        return dweller

    async def _return_equipment_to_source(self, db_session: AsyncSession, dweller: Dweller) -> None:
        """Hand the person's equipped items back to their previous vault's storage.

        The person moves empty-handed; the gear stays behind. When the source vault has no
        storage the items are left as-is rather than orphaned.
        """
        if dweller.previous_vault_id is None:
            return
        await db_session.refresh(dweller, attribute_names=["weapon", "outfit", "pet"])
        source = await vault_crud.get_or_none(db_session, dweller.previous_vault_id)
        if source is None:
            return
        await db_session.refresh(source, attribute_names=["storage"])
        storage = source.storage
        if storage is None:
            return
        for item in (dweller.weapon, dweller.outfit, dweller.pet):
            if item is not None:
                item.dweller_id = None
                item.storage_id = storage.id
                db_session.add(item)


departure_pool_service = DeparturePoolService()
