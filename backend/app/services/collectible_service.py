"""Award collectibles: the durable vault claim, the finder's permanent bonus, magazines, and sets.

Every write is staged; the caller's transaction owner commits. Dispatch awards run inside the
existing vault claim and are published from ``start_return``, never from here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import NotificationPriority, NotificationType
from app.core.game_config import game_config
from app.crud.collectible import collectible_crud
from app.models.collectible import VaultCollectible
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.world_location import WorldLocation
from app.schemas.collectible import CollectibleSetProgressRead, DwellerCollectibleRead
from app.services.notification_service import notification_service
from app.utils.collectibles import (
    MAGAZINE,
    collectible_for_key,
    collectible_for_location,
    magazine_buff_hours,
    set_progress,
)
from app.utils.collectibles import set_bonus_multiplier as completed_set_multiplier
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectibleAward:
    """One collectible awarded to a finder; the boundary builds its event payload."""

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
        """Claim a collectible for the vault and add its bonus to the finder.

        Returns False when the vault already holds the claim; nothing is written then. A magazine
        writes no permanent bonus — its claim is set progress and its effect is the timed buff that
        ``award_site_collectible`` applies — so the finder's ``collectible_bonus`` stays untouched.
        """
        entry = collectible_for_key(collectible_key)
        if await collectible_crud.get_by_vault_and_key(db_session, vault_id, collectible_key) is not None:
            return False

        # The pre-check is a courtesy, not the rule: UNIQUE(vault_id, collectible_key) is what
        # makes a claim once-per-vault. Insert inside a savepoint so a concurrent award landing
        # between check and insert costs a lost race, never a rolled-back dispatch.
        try:
            async with db_session.begin_nested():
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
        except IntegrityError:
            logger.info("Vault %s already claimed %r; another award won the race", vault_id, entry["key"])
            return False

        if entry["kind"] == MAGAZINE:
            return True

        # Mutated only after the claim lands, so a lost race leaves the finder's bonus untouched.
        bonus = dict(dweller.collectible_bonus or {})
        bonus[entry["stat"]] = bonus.get(entry["stat"], 0) + entry["amount"]
        dweller.collectible_bonus = bonus
        db_session.add(dweller)
        await db_session.flush()
        return True

    async def list_for_dweller(
        self, db_session: AsyncSession, *, vault_id: UUID, dweller_id: UUID
    ) -> list[DwellerCollectibleRead]:
        """The dweller's found collectibles in its current vault, catalog-joined for the API."""
        claims = await collectible_crud.list_for_dweller(db_session, vault_id, dweller_id)
        reads: list[DwellerCollectibleRead] = []
        for claim in claims:
            try:
                entry = collectible_for_key(claim.collectible_key)
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

    async def bonus_multiplier(self, db_session: AsyncSession, *, vault_id: UUID, bonus_type: str) -> float:
        """The vault's multiplier from its completed sets of one bonus type.

        Derived per read — nothing is written when a set completes — and gated on the feature
        flag here so callers never branch on it. Returns 1.0 while the flag is off.
        """
        if not game_config.features.collectibles:
            return 1.0
        return completed_set_multiplier(bonus_type, await collectible_crud.list_keys(db_session, vault_id))

    async def set_progress(self, db_session: AsyncSession, *, vault_id: UUID) -> list[CollectibleSetProgressRead]:
        """Every defined set with this vault's counts and whether its bonus is being paid."""
        keys = await collectible_crud.list_keys(db_session, vault_id)
        return [
            CollectibleSetProgressRead(**row) for row in set_progress(keys, enabled=game_config.features.collectibles)
        ]

    async def award_site_collectible(
        self,
        db_session: AsyncSession,
        *,
        exploration: Exploration,
        location: WorldLocation,
        members: Sequence[Dweller],
        action: str = "clear",
    ) -> CollectibleAward | None:
        """Award the collectible bound to a site to its luckiest survivor.

        Staged only: the dispatch transaction owner commits the claim and the bonus, and the
        notification is parked until that commit. A magazine is the recurring case — its claim is
        written once per vault and a later read only refreshes the finder's buff — so a return here
        means "this read counted", for a first read and a renewal alike. Returns None when the
        feature is off, the site holds nothing, or a one-shot collectible is already claimed.
        """
        if not game_config.features.collectibles:
            return None
        entry = collectible_for_location(location.name, action=action)
        if entry is None:
            return None
        living = [member for member in members if not member.is_dead]
        if not living:
            return None
        finder = min(living, key=lambda member: (-member.luck, str(member.id)))
        claimed = await self.award(
            db_session,
            vault_id=exploration.vault_id,
            dweller=finder,
            collectible_key=entry["key"],
            location_id=location.id,
        )
        magazine = entry["kind"] == MAGAZINE
        hours = 0
        if magazine:
            hours = await self._read_magazine(db_session, vault_id=exploration.vault_id, dweller=finder, entry=entry)
        elif not claimed:
            return None

        vault = await crud.vault.get(db_session, exploration.vault_id)
        if vault is not None:
            if magazine:
                title = f"{entry['name']} {'read' if claimed else 'reread'}"
                message = (
                    f"{finder.display_name} {'read' if claimed else 'reread'} the {entry['name']} at "
                    f"{location.name}: +{entry['amount']} {entry['stat']} for {hours} hours."
                )
            else:
                title = f"{entry['name']} found"
                message = (
                    f"{finder.display_name} found the {entry['name']} at {location.name}: "
                    f"permanent +{entry['amount']} {entry['stat']}."
                )
            await notification_service.create_and_send(
                db_session,
                user_id=vault.user_id,
                vault_id=vault.id,
                notification_type=NotificationType.COLLECTIBLE_FOUND,
                priority=NotificationPriority.NORMAL,
                title=title,
                message=message,
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

    async def _read_magazine(
        self, db_session: AsyncSession, *, vault_id: UUID, dweller: Dweller, entry: dict[str, Any]
    ) -> int:
        """Put the finder's one magazine buff in place and return its length in hours.

        Called after the claim is staged, so a first read already counts towards the set and gets
        the set's longer buff. One buff at a time: a newer read replaces the old one outright.
        """
        hours = magazine_buff_hours(entry, await collectible_crud.list_keys(db_session, vault_id))
        dweller.magazine_buff = {
            "key": entry["key"],
            "stat": entry["stat"],
            "amount": entry["amount"],
            "expires_at": (utcnow() + timedelta(hours=hours)).isoformat(),
        }
        db_session.add(dweller)
        await db_session.flush()
        return hours


collectible_service = CollectibleService()
