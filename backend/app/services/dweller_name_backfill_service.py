"""Opt-in, deterministic backfill for legacy super-mutant and visible-synth names.

PR #1182 changed name generation only for new dwellers. Existing rows keep the
Faker names they were created with, and renames are irreversible and
player-visible, so this is an operator-run CLI (dry run by default) rather than
an automatic migration.
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from faker import Faker

from app.core.enums import ContentProvenanceEnum, SynthTypeEnum
from app.crud.dweller import dweller as dweller_crud
from app.crud.vault import vault as vault_crud
from app.options.dweller_names import SUPER_MUTANT_NAMES, SYNTH_DESIGNATION_PREFIXES
from app.options.races import RaceOption, race_of, state_of_being_of
from app.services.rewards.starter_residents import starter_residents
from app.utils.dwellers import get_race_based_name
from app.utils.static_data import game_data_store

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller

logger = logging.getLogger(__name__)

_RENAMEABLE_SYNTH_STATES = frozenset({SynthTypeEnum.GEN_1.value, SynthTypeEnum.GEN_2.value})
_SUPER_MUTANT_BASE_NAMES = frozenset(name for pool in SUPER_MUTANT_NAMES.values() for name in pool)
_SYNTH_DESIGNATION = re.compile(rf"^[{''.join(SYNTH_DESIGNATION_PREFIXES)}]\d-\d{{2}}$")


def _curated_full_names() -> frozenset[str]:
    """Every curated identity currently shipped, so backfills never rewrite one."""
    names = {
        f"{template.first_name} {template.last_name or ''}".strip().casefold() for template in game_data_store.dwellers
    }
    names.update(starter_residents())
    return frozenset(names)


def _already_uses_race_name(dweller: Dweller, race: RaceOption, state: str | None) -> bool:
    """Whether the row already carries a valid name for its race and generation."""
    if race == RaceOption.SUPER_MUTANT:
        base_name = dweller.first_name.partition(" the ")[0]
        return dweller.last_name is None and base_name in _SUPER_MUTANT_BASE_NAMES
    if race == RaceOption.SYNTH and state in _RENAMEABLE_SYNTH_STATES:
        return dweller.last_name is None and _SYNTH_DESIGNATION.fullmatch(dweller.first_name) is not None
    return False


@dataclass(frozen=True)
class ActiveVaultBackfillResult:
    """Per-vault summaries plus the number of active vaults a cap left unprocessed."""

    summaries: dict[UUID4, dict[str, Any]]
    omitted: int


def generate_backfill_name(dweller: Dweller, race: RaceOption, state: str | None) -> tuple[str, str | None]:
    """Return the deterministic replacement name for a legacy row.

    Seeding from the dweller id keeps a re-run after a manual rollback stable and
    prevents every row from receiving the same name.
    """
    seed = dweller.id.int
    rng = random.Random(seed)
    faker = Faker()
    faker.seed_instance(seed)
    return get_race_based_name(race, state, dweller.gender, faker, rng)


class DwellerNameBackfillService:
    """Rename legacy non-human dwellers; dry run unless explicitly applied."""

    async def backfill_names_for_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        *,
        dry_run: bool = True,
        sample_limit: int = 10,
    ) -> dict[str, Any]:
        """Plan or apply names for one vault and return a summary."""
        candidates = await dweller_crud.get_name_backfill_candidates(
            db_session,
            vault_id,
            for_update=not dry_run,
        )
        curated_names = _curated_full_names()
        summary: dict[str, Any] = {
            "scanned": len(candidates),
            "renamed": 0,
            "skipped_curated": 0,
            "skipped_already_shaped": 0,
            "skipped_other_synth": 0,
            "samples": [],
        }
        for dweller in candidates:
            race = race_of(dweller)
            state = state_of_being_of(dweller)
            if race == RaceOption.SYNTH and state not in _RENAMEABLE_SYNTH_STATES:
                summary["skipped_other_synth"] += 1
                continue
            if race not in (RaceOption.SUPER_MUTANT, RaceOption.SYNTH):
                continue
            if dweller.display_name.casefold() in curated_names:
                summary["skipped_curated"] += 1
                continue
            if _already_uses_race_name(dweller, race, state):
                summary["skipped_already_shaped"] += 1
                continue

            first_name, last_name = generate_backfill_name(dweller, race, state)
            if len(summary["samples"]) < sample_limit:
                summary["samples"].append(f"{dweller.display_name} -> {(first_name + ' ' + (last_name or '')).strip()}")
            if not dry_run:
                dweller.first_name = first_name
                dweller.last_name = last_name
                dweller.content_provenance = ContentProvenanceEnum.GENERATED
            summary["renamed"] += 1

        if not dry_run:
            await db_session.commit()
        return summary

    async def backfill_names_for_active_vaults(
        self,
        db_session: AsyncSession,
        *,
        dry_run: bool = True,
        max_vaults: int | None = None,
        sample_limit: int = 10,
    ) -> ActiveVaultBackfillResult:
        """Plan or apply names across non-deleted vaults, ordered by creation date.

        ``max_vaults=None`` processes every active vault. An explicit cap is
        reported through ``omitted`` so the operator can see what was not touched.
        """
        if max_vaults is not None and max_vaults < 1:
            raise ValueError("max_vaults must be at least 1 when provided")
        vaults = list(await vault_crud.get_active_ordered(db_session, None))
        selected = vaults if max_vaults is None else vaults[:max_vaults]
        summaries = {
            vault.id: await self.backfill_names_for_vault(
                db_session,
                vault.id,
                dry_run=dry_run,
                sample_limit=sample_limit,
            )
            for vault in selected
        }
        return ActiveVaultBackfillResult(summaries=summaries, omitted=len(vaults) - len(selected))


dweller_name_backfill_service = DwellerNameBackfillService()
