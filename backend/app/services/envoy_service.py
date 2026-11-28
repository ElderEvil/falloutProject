"""Envoy Terminal: the pair ledger, first-contact hails and the effective knobs."""

import logging
from datetime import datetime, timedelta
from math import hypot
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DiplomaticFilingKind, DiplomaticFilingStatus, VaultRelationStatus
from app.core.game_config import game_config
from app.crud import diplomatic_filing as filing_crud
from app.crud import vault_relation as relation_crud
from app.crud import world_location as world_location_crud
from app.crud.vault_slot import vault_slot as slot_crud
from app.models.diplomatic_filing import DiplomaticFiling
from app.schemas.envoy import EnvoyConfigRead, EnvoyFilingRead, EnvoySignalRead
from app.utils.exceptions import NotFoundException, ResourceConflictException, ValidationException
from app.utils.time import utcnow
from app.utils.vault_slots import slot_coords

logger = logging.getLogger(__name__)

#: Standing an answered first contact is worth; the ladder caps at +100.
HAIL_STANDING = 5
MAX_STANDING = 100


def _read(filing: DiplomaticFiling, *, vault_id: UUID) -> EnvoyFilingRead:
    return EnvoyFilingRead(
        filing_id=filing.id,
        kind=DiplomaticFilingKind(filing.kind),
        status=DiplomaticFilingStatus(filing.status),
        from_vault_id=filing.from_vault_id,
        to_vault_id=filing.to_vault_id,
        terms=filing.terms,
        incoming=filing.to_vault_id == vault_id,
        created_at=filing.created_at,
        expires_at=filing.expires_at,
        responded_at=filing.responded_at,
    )


class EnvoyService:
    """Signals, hails and filings for one vault's terminal."""

    async def list_signals(self, db_session: AsyncSession, vault_id: UUID) -> list[EnvoySignalRead]:
        """Every live vault on the atlas, with this vault's relation and radio range applied."""
        now = utcnow()
        await self._expire_overdue(db_session, vault_id, now)
        roster = await slot_crud.list_markers(db_session)
        origin = next((slot_coords(index) for index, other_id, *_ in roster if other_id == vault_id), None)
        relations = {
            (relation.vault_b_id if relation.vault_a_id == vault_id else relation.vault_a_id): relation
            for relation in await relation_crud.list_for_vault(db_session, vault_id=vault_id)
        }
        incoming = {filing.from_vault_id for filing in await filing_crud.list_inbox(db_session, vault_id=vault_id)}
        outgoing = {
            filing.to_vault_id for filing in await filing_crud.list_pending_outgoing(db_session, vault_id=vault_id)
        }
        visited = await world_location_crud.list_visited_coords(db_session, vault_id=vault_id)
        radius = game_config.diplomacy.hail_radius
        signals: list[EnvoySignalRead] = []
        for slot_index, other_id, number, _owner_id, username in roster:
            if other_id == vault_id:
                continue
            relation = relations.get(other_id)
            status = VaultRelationStatus(relation.status) if relation is not None else VaultRelationStatus.UNMET
            target = slot_coords(slot_index)
            near = any(hypot(coord_x - target[0], coord_y - target[1]) <= radius for coord_x, coord_y in visited)
            locked_until = relation.locked_until if relation is not None else None
            locked = locked_until is not None and locked_until > now
            signals.append(
                EnvoySignalRead(
                    vault_id=other_id,
                    number=number,
                    owner_username=username or "Unknown",
                    status=status,
                    standing=relation.standing if relation is not None else 0,
                    distance=round(hypot(target[0] - origin[0], target[1] - origin[1]), 1) if origin else None,
                    can_hail=(
                        status == VaultRelationStatus.UNMET
                        and (near or other_id in incoming)
                        and not locked
                        and other_id not in outgoing
                    ),
                    incoming_hail=other_id in incoming,
                    met_at=relation.met_at if relation is not None else None,
                    locked_until=locked_until,
                )
            )
        await db_session.commit()
        return signals

    async def hail(self, db_session: AsyncSession, vault_id: UUID, *, target_vault_id: UUID) -> EnvoyFilingRead:
        """File a hail; the answer opens contact. Treaties arrive in a later slice."""
        now = utcnow()
        await self._expire_overdue(db_session, vault_id, now)
        if target_vault_id == vault_id:
            raise ValidationException("A vault cannot hail itself.")
        if await slot_crud.get_by_vault(db_session, target_vault_id) is None:
            raise NotFoundException("Vault not found.")
        if not await self._in_hail_range(db_session, vault_id, target_vault_id):
            raise ValidationException("No dweller of yours has been near that vault.")
        # Lock (or create) the pair row before the pending check, so two hails cannot both pass it.
        relation = await relation_crud.get_or_create(
            db_session, vault_id=vault_id, other_vault_id=target_vault_id, for_update=True
        )
        if VaultRelationStatus(relation.status) != VaultRelationStatus.UNMET:
            raise ResourceConflictException("You are already in contact with that vault.")
        if relation.locked_until is not None and relation.locked_until > now:
            raise ResourceConflictException("That vault refused your last filing; the line is locked.")
        pending = await filing_crud.get_pending(
            db_session, from_vault_id=vault_id, to_vault_id=target_vault_id, kind=DiplomaticFilingKind.HAIL
        )
        if pending is not None:
            raise ResourceConflictException("A hail is already waiting for an answer.")
        filing = await filing_crud.create(
            db_session,
            from_vault_id=vault_id,
            to_vault_id=target_vault_id,
            kind=DiplomaticFilingKind.HAIL,
            terms={},
            expires_at=now + timedelta(hours=game_config.diplomacy.filing_ttl_hours),
        )
        await db_session.commit()
        return _read(filing, vault_id=vault_id)

    async def respond(
        self, db_session: AsyncSession, vault_id: UUID, filing_id: UUID, *, accept: bool
    ) -> EnvoyFilingRead:
        """Answer a filing: accepting opens contact (+5 standing), refusing locks the pair."""
        now = utcnow()
        filing = await filing_crud.get(db_session, filing_id, for_update=True)
        if filing is None or filing.to_vault_id != vault_id:
            raise NotFoundException("Filing not found.")
        if DiplomaticFilingStatus(filing.status) != DiplomaticFilingStatus.PENDING:
            raise ResourceConflictException("This filing is no longer waiting for an answer.")
        if filing.expires_at <= now:
            await filing_crud.resolve(db_session, filing, status=DiplomaticFilingStatus.EXPIRED, responded_at=now)
            await db_session.commit()
            raise ValidationException("This filing has expired.")
        relation = await relation_crud.get_or_create(
            db_session, vault_id=vault_id, other_vault_id=filing.from_vault_id, for_update=True
        )
        if accept:
            await filing_crud.resolve(db_session, filing, status=DiplomaticFilingStatus.ACCEPTED, responded_at=now)
            # Only the first answered contact pays: a crossed pair of hails pays once.
            if VaultRelationStatus(relation.status) == VaultRelationStatus.UNMET:
                relation.status = VaultRelationStatus.CONTACT
                relation.standing = min(MAX_STANDING, relation.standing + HAIL_STANDING)
                relation.met_at = now
                relation.locked_until = None
        else:
            await filing_crud.resolve(db_session, filing, status=DiplomaticFilingStatus.REFUSED, responded_at=now)
            relation.locked_until = now + timedelta(hours=game_config.diplomacy.refusal_lock_hours)
        db_session.add(relation)
        await db_session.commit()
        logger.info(
            "Vault %s %s filing %s from %s",
            vault_id,
            "accepted" if accept else "refused",
            filing.id,
            filing.from_vault_id,
        )
        return _read(filing, vault_id=vault_id)

    async def log(self, db_session: AsyncSession, vault_id: UUID) -> list[EnvoyFilingRead]:
        """Both directions of this vault's filing log, newest first."""
        await self._expire_overdue(db_session, vault_id, utcnow())
        filings = await filing_crud.list_for_vault(db_session, vault_id=vault_id)
        await db_session.commit()
        return [_read(filing, vault_id=vault_id) for filing in filings]

    def config(self) -> EnvoyConfigRead:
        """The effective knobs, so the terminal never claims a rule the server is not running."""
        diplomacy = game_config.diplomacy
        return EnvoyConfigRead(
            enabled=game_config.features.vault_diplomacy,
            trade_gate=diplomacy.trade_gate,
            hail_radius=diplomacy.hail_radius,
            filing_ttl_hours=diplomacy.filing_ttl_hours,
            refusal_lock_hours=diplomacy.refusal_lock_hours,
            repropose_hours=diplomacy.repropose_hours,
            ceasefire_days=diplomacy.ceasefire_days,
            war_upkeep_per_level=diplomacy.war_upkeep_per_level,
            footing_penalty_pct=diplomacy.footing_penalty_pct,
            fatigue_start_days=diplomacy.fatigue_start_days,
            fatigue_ramp_days=diplomacy.fatigue_ramp_days,
            arbitration_day=diplomacy.arbitration_day,
            accord_upkeep=diplomacy.accord_upkeep,
            compact_upkeep=diplomacy.compact_upkeep,
            unjust_war_multiplier=diplomacy.unjust_war_multiplier,
            stake_pct=diplomacy.stake_pct,
            stake_min=diplomacy.stake_min,
            stake_max=diplomacy.stake_max,
        )

    async def _in_hail_range(self, db_session: AsyncSession, vault_id: UUID, other_vault_id: UUID) -> bool:
        """True when a dweller has stood within hail radius of that slot, or they hailed first.

        The waiver is one-directional on purpose: reaching back at someone who already
        reached you is an answer, never a second gate.
        """
        answering = await filing_crud.get_pending(
            db_session, from_vault_id=other_vault_id, to_vault_id=vault_id, kind=DiplomaticFilingKind.HAIL
        )
        if answering is not None:
            return True
        # Only the target's slot matters: the radius is measured from our dwellers' feet.
        other_slot = await slot_crud.get_by_vault(db_session, other_vault_id)
        if other_slot is None:
            return False
        target = slot_coords(other_slot.slot_index)
        radius = game_config.diplomacy.hail_radius
        visited = await world_location_crud.list_visited_coords(db_session, vault_id=vault_id)
        return any(hypot(coord_x - target[0], coord_y - target[1]) <= radius for coord_x, coord_y in visited)

    async def _expire_overdue(self, db_session: AsyncSession, vault_id: UUID, now: datetime) -> None:
        """Lapse overdue filings before anything reads them; the entry point's commit lands it."""
        expired = await filing_crud.expire_overdue(db_session, vault_id=vault_id, now=now)
        if expired:
            logger.info("Expired %d diplomacy filings for vault %s", len(expired), vault_id)


envoy_service = EnvoyService()
