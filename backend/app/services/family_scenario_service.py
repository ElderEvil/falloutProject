"""Service for building deterministic family/breeding test scenarios.

Dev/QA tooling for manually testing the family feature: pair couples at a
controlled relationship stage and affinity, co-locate them in a living
quarters room (so the game-loop affinity ticks drive real progression), and
create pregnancies, postpartum deliveries, and children with controlled
timestamps so timing-driven behaviour (due dates, the 6h postpartum cooldown,
3h child growth) can be observed on a real timeline.

The API exposes no way to set affinity directly — the romance/partner/marry
endpoints only enforce thresholds — so scenario construction works at the
service/DB layer, like the pregen-service dev/QA commands. CLI commands in
``app/cli/app/family_scenario.py`` are thin wrappers over this service
(AGENTS.md: business logic lives in services, not CLI scripts).

Usage (from backend/):
    uv run fo-cli family-scenario setup --vault-id <UUID>
    uv run fo-cli family-scenario status --vault-id <UUID>
    uv run fo-cli family-scenario reset --vault-id <UUID>
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]
from sqlmodel import select

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.models.relationship import Relationship  # ruff: ignore[typing-only-first-party-import]
from app.models.room import Room
from app.schemas.common import (
    AgeGroupEnum,
    GenderEnum,
    PregnancyStatusEnum,
    RelationshipTypeEnum,
    RoomTypeEnum,
)
from app.services.breeding_service import breeding_service
from app.utils.datetime import utc_now
from app.utils.exceptions import ResourceNotFoundException

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

# Sensible default affinity per stage when the user omits one.
DEFAULT_AFFINITY: dict[RelationshipTypeEnum, int] = {
    RelationshipTypeEnum.ACQUAINTANCE: 20,
    RelationshipTypeEnum.FRIEND: 60,
    RelationshipTypeEnum.ROMANTIC: 70,
    RelationshipTypeEnum.PARTNER: 80,
    RelationshipTypeEnum.MARRIED: 95,
    RelationshipTypeEnum.EX: 30,
}

# Relationship milestones used by the timeline report (affinity targets).
ROMANCE_TARGET = game_config.relationship.romance_threshold
MARRIAGE_TARGET = game_config.relationship.marriage_threshold


@dataclass
class Couple:
    """A paired couple plus the relationship row that backs it."""

    index: int
    dweller_1: Dweller
    dweller_2: Dweller
    relationship: Relationship

    @property
    def label(self) -> str:
        return f"{self.dweller_1.first_name} + {self.dweller_2.first_name}"


@dataclass
class TimelineRow:
    """One status-report line with a computed countdown."""

    kind: str  # 'relationship' | 'pregnancy' | 'postpartum' | 'child'
    label: str
    detail: str
    countdown: str = ""


@dataclass
class ScenarioResult:
    """Summary of a setup run (for CLI reporting)."""

    couples: list[Couple] = field(default_factory=list)
    pregnancies: list[Pregnancy] = field(default_factory=list)
    postpartum: list[Pregnancy] = field(default_factory=list)
    children: list[Dweller] = field(default_factory=list)


def _fmt_delta(delta: timedelta) -> str:
    """Format a timedelta as a compact human string (``2h 05m``, ``-4m``)."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return f"-{_fmt_delta(-delta)}"
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


class FamilyScenarioService:
    """Deterministic family/breeding test-scenario builder."""

    # ------------------------------------------------------------------
    # lookups
    # ------------------------------------------------------------------

    @staticmethod
    async def list_adults(db_session: AsyncSession, vault_id: UUID4) -> list[Dweller]:
        """List alive adult dwellers in a vault (excluding the dead)."""
        adults = await crud.dweller.get_multi_by_vault(
            db_session, vault_id=vault_id, age_group=AgeGroupEnum.ADULT, limit=1000
        )
        return [d for d in adults if not d.is_dead and not d.is_deleted]

    @staticmethod
    async def find_living_quarters(db_session: AsyncSession, vault_id: UUID4) -> Room | None:
        """Return the first living-quarters (capacity) room in the vault, if any."""
        query = select(Room).where(Room.vault_id == vault_id, Room.category == RoomTypeEnum.CAPACITY)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def _get_dweller(db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        try:
            return await crud.dweller.get(db_session, dweller_id)
        except ResourceNotFoundException as exc:
            raise ValueError(f"Dweller not found (id={dweller_id})") from exc

    @staticmethod
    async def _get_room(db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> Room:
        try:
            room = await crud.room.get(db_session, room_id)
        except ResourceNotFoundException as exc:
            raise ValueError(f"Room not found (id={room_id})") from exc
        if vault_id is not None and room.vault_id != vault_id:
            raise ValueError(f"Room {room_id} does not belong to vault {vault_id}")
        return room

    # ------------------------------------------------------------------
    # couple pairing
    # ------------------------------------------------------------------

    @classmethod
    async def auto_pair(
        cls,
        db_session: AsyncSession,
        vault_id: UUID4,
        count: int,
        seed: int | None,
    ) -> list[tuple[Dweller, Dweller]]:
        """Auto-pick ``count`` couples from the vault's adults.

        Pairs are built male+female first (breeding requires opposite
        genders), then leftover dwellers are paired in list order. Throws a
        clear ValueError if there are not enough adults.
        """
        adults = await cls.list_adults(db_session, vault_id)
        rng = random.Random(seed)
        rng.shuffle(adults)

        if len(adults) < count * 2:
            raise ValueError(
                f"Vault {vault_id} has {len(adults)} adult dwellers but {count * 2} are needed "
                f"for {count} couples. Use --pairs or pregen more dwellers "
                f"(uv run fo-cli pregen-dwellers --vault-id {vault_id})."
            )

        males = [d for d in adults if d.gender == GenderEnum.MALE]
        females = [d for d in adults if d.gender == GenderEnum.FEMALE]

        pairs: list[tuple[Dweller, Dweller]] = []
        used: set[UUID4] = set()
        for _ in range(count):
            male = next((m for m in males if m.id not in used), None)
            female = next((f for f in females if f.id not in used), None)
            if male and female:
                pairs.append((male, female))
                used.update({male.id, female.id})
                continue
            remaining = [d for d in adults if d.id not in used]
            if len(remaining) >= 2:
                pairs.append((remaining[0], remaining[1]))
                used.update({remaining[0].id, remaining[1].id})
        return pairs

    @classmethod
    async def pair(
        cls,
        db_session: AsyncSession,
        vault_id: UUID4,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
        stage: str,
        affinity: int | None,
        room_id: UUID4 | None = None,
    ) -> Couple:
        """Create a relationship between two dwellers at a fixed stage/affinity.

        For partner/MARRIED stages the reciprocal ``partner_id`` is set on both
        dwellers (mirroring RelationshipService._set_partner_ids). If ``room_id``
        is given, both dwellers are moved there so the game loop's affinity tick
        and conception check can operate on the couple.
        """
        dweller_1 = await cls._get_dweller(db_session, dweller_1_id)
        dweller_2 = await cls._get_dweller(db_session, dweller_2_id)
        for d in (dweller_1, dweller_2):
            if d.vault_id != vault_id:
                raise ValueError(f"Dweller {d.id} does not belong to vault {vault_id}")

        rel_type = RelationshipTypeEnum(stage)
        rel = await crud.relationship.create_with_defaults(
            db_session,
            dweller_1_id,
            dweller_2_id,
            relationship_type=rel_type,
            affinity=min(100, max(0, affinity if affinity is not None else DEFAULT_AFFINITY[rel_type])),
        )

        # Partner-linked stages must also set reciprocal partner_id on the dwellers.
        if rel_type in {RelationshipTypeEnum.PARTNER, RelationshipTypeEnum.MARRIED}:
            dweller_1.partner_id = dweller_2.id
            dweller_2.partner_id = dweller_1.id

        if room_id:
            for d in (dweller_1, dweller_2):
                d.room_id = room_id

        db_session.add_all([dweller_1, dweller_2])
        await db_session.commit()
        await db_session.refresh(rel)

        return Couple(index=-1, dweller_1=dweller_1, dweller_2=dweller_2, relationship=rel)

    @staticmethod
    async def _co_locate(db_session: AsyncSession, couple: Couple, room: Room | None) -> None:
        """Move both dwellers of a couple into a room (no-op if room is None)."""
        if room is None:
            return
        for d in (couple.dweller_1, couple.dweller_2):
            d.room_id = room.id
        db_session.add_all([couple.dweller_1, couple.dweller_2])
        await db_session.commit()

    # ------------------------------------------------------------------
    # pregnancy / postpartum / children
    # ------------------------------------------------------------------

    @classmethod
    async def create_pregnancy(
        cls,
        db_session: AsyncSession,
        couple: Couple,
        due_in_minutes: int,
    ) -> Pregnancy:
        """Create a PREGNANT pregnancy, due in ``due_in_minutes`` (negative = already overdue).

        The mother is the female member of the couple; raises ValueError if the
        couple has no female member.
        """
        mother = next((d for d in (couple.dweller_1, couple.dweller_2) if d.gender == GenderEnum.FEMALE), None)
        father = next((d for d in (couple.dweller_1, couple.dweller_2) if d is not mother), None)
        if mother is None or father is None:
            raise ValueError(f"Couple '{couple.label}' has no female member — cannot create a pregnancy")

        pregnancy = await breeding_service.create_pregnancy(db_session, mother.id, father.id)
        pregnancy.due_at = utc_now() + timedelta(minutes=due_in_minutes)
        db_session.add(pregnancy)
        await db_session.commit()
        await db_session.refresh(pregnancy)
        return pregnancy

    @classmethod
    async def create_postpartum(
        cls,
        db_session: AsyncSession,
        couple: Couple,
        delivered_hours_ago: float,
    ) -> Pregnancy:
        """Create a DELIVERED pregnancy whose ``updated_at`` is ``delivered_hours_ago`` in the past.

        The postpartum-cooldown check (``_get_postpartum_mother_ids``) reads
        ``Pregnancy.updated_at`` and excludes mothers whose delivery falls
        within ``birth_cooldown_hours`` (default 6h). Backdating ``updated_at``
        is what makes the cooldown testable without waiting: e.g. 2h ago = still
        cooling down (excluded from conception), 7h ago = cooldown expired.
        """
        mother = next((d for d in (couple.dweller_1, couple.dweller_2) if d.gender == GenderEnum.FEMALE), None)
        father = next((d for d in (couple.dweller_1, couple.dweller_2) if d is not mother), None)
        if mother is None or father is None:
            raise ValueError(f"Couple '{couple.label}' has no female member — cannot create a delivery")

        now = utc_now()
        pregnancy = Pregnancy(
            mother_id=mother.id,
            father_id=father.id,
            conceived_at=now - timedelta(hours=game_config.breeding.pregnancy_duration_hours + delivered_hours_ago),
            due_at=now - timedelta(hours=delivered_hours_ago),
            status=PregnancyStatusEnum.DELIVERED,
        )
        pregnancy.updated_at = now - timedelta(hours=delivered_hours_ago)
        db_session.add(pregnancy)
        await db_session.commit()
        await db_session.refresh(pregnancy)
        return pregnancy

    @classmethod
    async def create_child(
        cls,
        db_session: AsyncSession,
        vault_id: UUID4,
        couple: Couple,
        age_hours: float,
        seed: int | None,
    ) -> Dweller:
        """Create a child of the couple whose ``birth_date`` is ``age_hours`` ago.

        The growth check (``age_children``) ages children whose ``birth_date``
        is older than ``child_growth_duration_hours`` (default 3h). Backdating
        the birth date makes growth testable immediately: e.g. 1h old = still a
        child, 4h old = will age to adult on the next tick.
        """
        child = await crud.dweller.create_random(
            db_session,
            vault_id,
            seed=seed,
            register_bio_places=False,
        )
        child.age_group = AgeGroupEnum.CHILD
        child.is_adult = False
        child.birth_date = utc_now() - timedelta(hours=age_hours)
        child.parent_1_id = couple.dweller_1.id
        child.parent_2_id = couple.dweller_2.id
        db_session.add(child)
        await db_session.commit()
        await db_session.refresh(child)
        return child

    # ------------------------------------------------------------------
    # status / reset
    # ------------------------------------------------------------------

    @staticmethod
    async def get_status(db_session: AsyncSession, vault_id: UUID4) -> list[TimelineRow]:
        """Build a timeline report of every relationship/pregnancy/child in the vault."""
        rows: list[TimelineRow] = []
        dwellers_by_id: dict[UUID4, Dweller] = {}

        async def _name(dweller_id: UUID4) -> str:
            if dweller_id not in dwellers_by_id:
                try:
                    dwellers_by_id[dweller_id] = await crud.dweller.get(db_session, dweller_id)
                except ResourceNotFoundException:
                    return "?"
            return f"{dwellers_by_id[dweller_id].first_name} {dwellers_by_id[dweller_id].last_name or ''}".strip()

        # Relationships with next-milestone countdowns.
        relationships = await crud.relationship.get_by_vault(db_session, vault_id)
        for rel in relationships:
            name_1 = await _name(rel.dweller_1_id)
            name_2 = await _name(rel.dweller_2_id)
            rel_type = RelationshipTypeEnum(rel.relationship_type)
            if rel_type == RelationshipTypeEnum.MARRIED:
                detail = "married"
                countdown = ""
            elif rel_type in {RelationshipTypeEnum.PARTNER, RelationshipTypeEnum.ROMANTIC}:
                if rel.affinity < MARRIAGE_TARGET:
                    ticks = (
                        MARRIAGE_TARGET - rel.affinity + game_config.relationship.affinity_increase_per_tick - 1
                    ) // (game_config.relationship.affinity_increase_per_tick)
                    countdown = f"marriage in ~{ticks} ticks ({_fmt_delta(timedelta(seconds=ticks * game_config.game_loop.tick_interval))})"
                else:
                    countdown = "can marry now"
                detail = f"affinity {rel.affinity}/100"
            else:
                if rel.affinity < ROMANCE_TARGET:
                    ticks = (
                        ROMANCE_TARGET - rel.affinity + game_config.relationship.affinity_increase_per_tick - 1
                    ) // (game_config.relationship.affinity_increase_per_tick)
                    countdown = f"romance in ~{ticks} ticks ({_fmt_delta(timedelta(seconds=ticks * game_config.game_loop.tick_interval))})"
                else:
                    countdown = "can romance now"
                detail = f"affinity {rel.affinity}/100"
            rows.append(
                TimelineRow(
                    kind="relationship",
                    label=f"{name_1} + {name_2} [{rel_type.value}]",
                    detail=detail,
                    countdown=countdown,
                )
            )

        # Pregnancies: due countdown for PREGNANT, cooldown countdown for DELIVERED.
        pregnancy_query = (
            select(Pregnancy).join(Dweller, Pregnancy.mother_id == Dweller.id).where(Dweller.vault_id == vault_id)
        )
        pregnancies = list((await db_session.execute(pregnancy_query)).scalars().all())
        for preg in pregnancies:
            mother = await _name(preg.mother_id)
            father = await _name(preg.father_id)
            if preg.status == PregnancyStatusEnum.PREGNANT:
                due_in = preg.due_at - utc_now()
                countdown = f"due in {_fmt_delta(due_in)}"
                rows.append(
                    TimelineRow(kind="pregnancy", label=f"{mother} ⚧ {father}", detail="pregnant", countdown=countdown)
                )
            else:
                cooldown_ends = preg.updated_at + timedelta(hours=game_config.breeding.birth_cooldown_hours)
                remaining = cooldown_ends - utc_now()
                if remaining > timedelta(0):
                    countdown = f"cooldown ends in {_fmt_delta(remaining)}"
                else:
                    countdown = "cooldown expired — can conceive again"
                rows.append(
                    TimelineRow(
                        kind="postpartum", label=f"{mother} ⚧ {father}", detail="delivered", countdown=countdown
                    )
                )

        # Children: growth countdown.
        children = await crud.dweller.get_multi_by_vault(db_session, vault_id, age_group=AgeGroupEnum.CHILD, limit=1000)
        for child in children:
            if child.birth_date is None:
                continue
            grows_at = child.birth_date + timedelta(hours=game_config.breeding.child_growth_duration_hours)
            remaining = grows_at - utc_now()
            if remaining > timedelta(0):
                countdown = f"grows up in {_fmt_delta(remaining)}"
            else:
                countdown = "ready to grow up (next tick)"
            rows.append(
                TimelineRow(
                    kind="child",
                    label=f"{child.first_name} {child.last_name or ''}".strip(),
                    detail="child",
                    countdown=countdown,
                )
            )

        return rows

    @staticmethod
    async def reset(
        db_session: AsyncSession,
        vault_id: UUID4,
        *,
        include_children: bool = False,
    ) -> dict[str, int]:
        """Remove relationships and pregnancies for the vault; optionally children too.

        Relationships are hard-deleted (they are pure join rows), children are
        soft-deleted to keep the dweller history intact.
        """
        counts: dict[str, int] = {"relationships": 0, "pregnancies": 0, "children": 0}

        relationships = await crud.relationship.get_by_vault(db_session, vault_id)
        for rel in relationships:
            for dweller_id in (rel.dweller_1_id, rel.dweller_2_id):
                dweller = await crud.dweller.get(db_session, dweller_id)
                if dweller and dweller.partner_id in (rel.dweller_1_id, rel.dweller_2_id):
                    dweller.partner_id = None
                    db_session.add(dweller)
            await crud.relationship.delete(db_session, rel.id, soft=False)
            counts["relationships"] += 1

        pregnancy_query = (
            select(Pregnancy).join(Dweller, Pregnancy.mother_id == Dweller.id).where(Dweller.vault_id == vault_id)
        )
        for preg in (await db_session.execute(pregnancy_query)).scalars().all():
            await db_session.delete(preg)
            counts["pregnancies"] += 1
        await db_session.commit()

        if include_children:
            children = await crud.dweller.get_multi_by_vault(
                db_session, vault_id, age_group=AgeGroupEnum.CHILD, limit=1000
            )
            for child in children:
                await crud.dweller.delete(db_session, child.id, soft=True)
                counts["children"] += 1

        return counts

    # ------------------------------------------------------------------
    # setup orchestration
    # ------------------------------------------------------------------

    @classmethod
    async def setup(
        cls,
        db_session: AsyncSession,
        vault_id: UUID4,
        *,
        count: int = 1,
        pairs: list[tuple[UUID4, UUID4]] | None = None,
        stage: str = "partner",
        affinity: int | None = None,
        room_id: UUID4 | None = None,
        pregnancy_due_minutes: list[int] | None = None,
        postpartum_hours: list[float] | None = None,
        child_ages_hours: list[float] | None = None,
        seed: int | None = None,
        co_locate: bool = True,
    ) -> ScenarioResult:
        """Create couples (auto-paired or explicit) plus optional pregnancies/children.

        - ``pairs``: explicit ``(dweller_1_id, dweller_2_id)`` list; takes
          precedence over ``count``.
        - ``stage``/``affinity``: relationship stage (and affinity override) for
          every created couple.
        - ``pregnancy_due_minutes``: per-couple due offsets, e.g. ``[15, 60]``
          makes the 1st couple pregnant due in 15m and the 2nd due in 60m.
        - ``postpartum_hours``: per-couple delivered timestamps (hours ago),
          e.g. ``[2, 7]`` → 1st mother still cooling down, 2nd cooldown expired.
        - ``child_ages_hours``: per-couple child ages (hours), e.g. ``[1, 4]``.
        - ``co_locate``: move every couple into a living-quarters room so the
          game loop can tick affinity/conception on them (default True).
        """
        if pairs:
            raw_pairs = pairs
        else:
            raw_pairs = await cls.auto_pair(db_session, vault_id, count, seed)

        # Resolve and validate the co-location room before creating any couples,
        # so an invalid or cross-vault room is rejected up front.
        room = None
        if co_locate:
            if room_id is not None:
                room = await cls._get_room(db_session, room_id, vault_id)
            else:
                room = await cls.find_living_quarters(db_session, vault_id)

        couples: list[Couple] = []
        for i, (d1_id, d2_id) in enumerate(raw_pairs):
            couple = await cls.pair(db_session, vault_id, d1_id, d2_id, stage, affinity, room_id if co_locate else None)
            couple.index = i
            couples.append(couple)

        for couple in couples:
            await cls._co_locate(db_session, couple, room)

        result = ScenarioResult(couples=couples)

        # Timing lists map to couples by index (cycling for couples[0]).
        def _targets(values: list[float] | None) -> list[tuple[Couple, float]]:
            if not values:
                return []
            return [(couples[i % len(couples)], value) for i, value in enumerate(values)]

        for couple, due_minutes in _targets(pregnancy_due_minutes):
            result.pregnancies.append(await cls.create_pregnancy(db_session, couple, int(due_minutes)))
        for couple, hours in _targets(postpartum_hours):
            result.postpartum.append(await cls.create_postpartum(db_session, couple, hours))
        for couple, hours in _targets(child_ages_hours):
            result.children.append(await cls.create_child(db_session, vault_id, couple, hours, seed))

        return result


family_scenario_service = FamilyScenarioService()
