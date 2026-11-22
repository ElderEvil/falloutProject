"""Award bobbleheads: the durable vault claim plus the finder's permanent bonus.

Every write is staged; the caller's transaction owner commits. Dispatch awards run inside the
existing vault claim and are published from ``start_return``, never from here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import NotificationPriority, NotificationType
from app.core.game_config import game_config
from app.crud.collectible import collectible_crud
from app.models.collectible import VaultCollectible
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.world_location import WorldLocation
from app.schemas.collectible import DwellerCollectibleRead
from app.services.notification_service import notification_service
from app.utils.collectibles import bobblehead_for_key, bobblehead_for_location
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectibleAward:
    """One bobblehead awarded to a finder; the boundary builds its event payload."""

    collectible_key: str
    name: str
    stat: str
    amount: int
    dweller_id: UUID
    location_name: str


class CollectibleService:
    async def award(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID,
        dweller: Dweller,
        collectible_key: str,
        location_id: UUID | None = None,
    ) -> bool:
        """Claim a bobblehead for the vault and add its bonus to the finder.

        Returns False when the vault already holds the claim; nothing is written then.
        """
        entry = bobblehead_for_key(collectible_key)
        if await collectible_crud.get_by_vault_and_key(db_session, vault_id, collectible_key) is not None:
            return False

        bonus = dict(dweller.collectible_bonus or {})
        bonus[entry["stat"]] = bonus.get(entry["stat"], 0) + entry["amount"]
        dweller.collectible_bonus = bonus
        db_session.add(dweller)
        db_session.add(
            VaultCollectible(
                vault_id=vault_id,
                collectible_key=entry["key"],
                finder_dweller_id=dweller.id,
                location_id=location_id,
                found_at=utcnow(),
            )
        )
        await db_session.flush()
        return True

    async def list_for_dweller(
        self, db_session: AsyncSession, *, vault_id: UUID, dweller_id: UUID
    ) -> list[DwellerCollectibleRead]:
        """The dweller's found bobbleheads in its current vault, catalog-joined for the API."""
        claims = await collectible_crud.list_for_dweller(db_session, vault_id, dweller_id)
        reads: list[DwellerCollectibleRead] = []
        for claim in claims:
            try:
                entry = bobblehead_for_key(claim.collectible_key)
            except ValueError:
                logger.warning(
                    "Collectible claim %s for vault %s has no catalog entry; omitting it",
                    claim.collectible_key,
                    vault_id,
                )
                continue
            reads.append(
                DwellerCollectibleRead(
                    key=entry["key"],
                    name=entry["name"],
                    stat=entry["stat"],
                    amount=entry["amount"],
                    image=entry["image"],
                    location=entry["location"],
                    found_at=claim.found_at,
                )
            )
        return reads

    async def award_site_collectible(
        self,
        db_session: AsyncSession,
        *,
        exploration: Exploration,
        location: WorldLocation,
        members: Sequence[Dweller],
        action: str = "clear",
    ) -> CollectibleAward | None:
        """Award a cleared site's bobblehead to its luckiest survivor.

        Staged only: the dispatch transaction owner commits the claim and the bonus, and the
        notification is parked until that commit. Returns the event payload, or None when the
        feature is off, the site holds nothing, or the vault already has the claim.
        """
        if not game_config.features.collectibles:
            return None
        entry = bobblehead_for_location(location.name)
        if entry is None or entry["action"] != action:
            return None
        living = [member for member in members if not member.is_dead]
        if not living:
            return None
        finder = min(living, key=lambda member: (-member.luck, str(member.id)))
        if not await self.award(
            db_session,
            vault_id=exploration.vault_id,
            dweller=finder,
            collectible_key=entry["key"],
            location_id=location.id,
        ):
            return None

        vault = await crud.vault.get(db_session, exploration.vault_id)
        if vault is not None:
            await notification_service.create_and_send(
                db_session,
                user_id=vault.user_id,
                vault_id=vault.id,
                notification_type=NotificationType.COLLECTIBLE_FOUND,
                priority=NotificationPriority.NORMAL,
                title=f"{entry['name']} found",
                message=(
                    f"{finder.display_name} found the {entry['name']} at {location.name}: "
                    f"permanent +{entry['amount']} {entry['stat']}."
                ),
                meta_data={"collectible_key": entry["key"], "dweller_id": str(finder.id)},
                commit=False,
            )
        return CollectibleAward(
            collectible_key=entry["key"],
            name=entry["name"],
            stat=entry["stat"],
            amount=entry["amount"],
            dweller_id=finder.id,
            location_name=location.name,
        )


collectible_service = CollectibleService()
