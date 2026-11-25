"""Award collectibles: the durable vault claim, the finder's permanent bonus, magazines, and sets.

Every write is staged; the caller's transaction owner commits. Dispatch awards run inside the
existing vault claim and are published from ``start_return``, never from here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
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
    magazine_boon_amount,
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
        claims like every other collectible and writes the finder's permanent ``magazine_boon``; a
        bobblehead or comic writes the permanent per-stat ``collectible_bonus`` instead. Either way
        the bonus is written only after the claim lands, so a lost race leaves the finder untouched.
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
            await self._apply_magazine_boon(db_session, vault_id=vault_id, dweller=dweller, entry=entry)
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
        # Magazine amounts come from the finder, not the catalog: the completed shelf pays an extra
        # point, and recycling clears the boon while the vault's claim stays behind. A cleared boon
        # reads as 0 so the list never promises a bonus the dweller no longer holds.
        finder = await crud.dweller.get(db_session, dweller_id)
        boons = (finder.magazine_boon if finder else None) or {}
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
            amount = entry["amount"]
            if entry["kind"] == MAGAZINE:
                held = boons.get(entry["key"])
                held_amount = held.get("amount") if isinstance(held, dict) else None
                is_counted = isinstance(held_amount, int) and not isinstance(held_amount, bool)
                amount = held_amount if is_counted else 0
            reads.append(
                DwellerCollectibleRead(
                    key=entry["key"],
                    name=entry["name"],
                    stat=entry["stat"],
                    amount=amount,
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
        notification is parked until that commit. Every salvage site is a one-time find, so a return
        here always means the claim was new; None means the feature is off, the site holds nothing,
        or the vault already holds this collectible.
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
        if not claimed:
            return None
        # A magazine's boon is not always its catalog amount: the completed shelf pays an extra
        # point, and the boon just written is the single source of truth for what the finder got.
        amount = entry["amount"]
        if entry["kind"] == MAGAZINE:
            held = (finder.magazine_boon or {}).get(entry["key"])
            if isinstance(held, dict):
                amount = int(held.get("amount", entry["amount"]))

        vault = await crud.vault.get(db_session, exploration.vault_id)
        if vault is not None:
            title = f"{entry['name']} found"
            message = (
                f"{finder.display_name} found the {entry['name']} at {location.name}: "
                f"permanent +{amount} {entry['stat']}."
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
            amount=amount,
            dweller_id=finder.id,
            location_name=location.name,
        )

    async def _apply_magazine_boon(
        self, db_session: AsyncSession, *, vault_id: UUID, dweller: Dweller, entry: dict[str, Any]
    ) -> int:
        """Stage the finder's permanent magazine boon and return its amount.

        Called after the claim is flushed, so the read that completes the shelf already counts and
        pays the larger boon. No clock and no expiry: a one-time find is kept for good.
        """
        amount = magazine_boon_amount(entry, await collectible_crud.list_keys(db_session, vault_id))
        # Keyed by magazine, not replaced: a dweller who finds a second one keeps the first.
        boons = dict(dweller.magazine_boon or {})
        boons[entry["key"]] = {"stat": entry["stat"], "amount": amount}
        dweller.magazine_boon = boons
        db_session.add(dweller)
        await db_session.flush()
        if amount > entry["amount"]:
            # This read completed the shelf. Boons are written at claim time, so finders who came
            # before the shelf closed are still holding the smaller amount; raise them now, once.
            await self._upgrade_shelf_boons(db_session, vault_id=vault_id, amount=amount)
        return amount

    async def _upgrade_shelf_boons(self, db_session: AsyncSession, *, vault_id: UUID, amount: int) -> None:
        """Raise every already-claimed magazine boon in the vault to the completed-shelf amount.

        A set completes once per vault, so this sweep runs at most once and never has to unwind:
        claims are permanent, so the shelf cannot come undone.
        """
        raised = 0
        for holder in await crud.dweller.get_all_in_vault(db_session, vault_id):
            boons = holder.magazine_boon
            if not boons:
                continue
            upgraded = {
                key: {**held, "amount": amount}
                for key, held in boons.items()
                if isinstance(held, dict) and int(held.get("amount", 0)) < amount
            }
            if not upgraded:
                continue
            holder.magazine_boon = {**boons, **upgraded}
            db_session.add(holder)
            raised += 1
        if raised:
            await db_session.flush()


collectible_service = CollectibleService()
