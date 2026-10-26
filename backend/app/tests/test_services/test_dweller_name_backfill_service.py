"""Tests for the opt-in legacy dweller-name backfill."""

from __future__ import annotations

import re

import pytest
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import AvailabilityEnum, ContentProvenanceEnum, GenderEnum, RarityEnum
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.options.dweller_names import SUPER_MUTANT_NAMES, SYNTH_DESIGNATION_PREFIXES
from app.options.races import RaceOption
from app.schemas.dweller import DwellerCreate
from app.services.dweller_name_backfill_service import (
    dweller_name_backfill_service,
    generate_backfill_name,
)

DESIGNATION = re.compile(rf"^[{''.join(SYNTH_DESIGNATION_PREFIXES)}]\d-\d{{2}}$")
ALL_MUTANT_NAMES = {name for pool in SUPER_MUTANT_NAMES.values() for name in pool}


async def _make_dweller(
    async_session: AsyncSession,
    vault: Vault,
    *,
    first_name: str,
    last_name: str | None = "Smith",
    race: str = "super_mutant",
    state: str | None = "average",
    provenance: ContentProvenanceEnum | None = None,
    **overrides: object,
) -> Dweller:
    visual_attributes = {"race": race}
    if state is not None:
        visual_attributes["state_of_being"] = state
    availability = overrides.pop("availability", None)
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name=first_name,
            last_name=last_name,
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault.id,
            visual_attributes=visual_attributes,
            **overrides,
        ),
    )
    if provenance is not None or availability is not None:
        if provenance is not None:
            dweller.content_provenance = provenance
        if availability is not None:
            dweller.availability = availability
        await async_session.commit()
        await async_session.refresh(dweller)
    return dweller


async def test_dry_run_reports_without_writing(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _make_dweller(async_session, vault, first_name="Michael", last_name="Smith")

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id)

    await async_session.refresh(dweller)
    assert summary["scanned"] == 1
    assert summary["renamed"] == 1
    assert len(summary["samples"]) == 1
    assert "Michael Smith" in summary["samples"][0]
    assert dweller.display_name == "Michael Smith"


async def test_apply_renames_mutant_and_marks_it_generated(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _make_dweller(async_session, vault, first_name="Michael", last_name="Smith")

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    renamed = await crud.dweller.get(async_session, dweller.id)
    assert summary["renamed"] == 1
    assert renamed.display_name != "Michael Smith"
    assert renamed.last_name is None
    assert renamed.first_name.partition(" the ")[0] in ALL_MUTANT_NAMES
    assert renamed.content_provenance == ContentProvenanceEnum.GENERATED


async def test_apply_is_idempotent(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _make_dweller(async_session, vault, first_name="Michael", last_name="Smith")

    await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)
    first_run = await crud.dweller.get(async_session, dweller.id)
    first_name, first_last_name = first_run.first_name, first_run.last_name

    second = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    after_second = await crud.dweller.get(async_session, dweller.id)
    assert second["scanned"] == 0
    assert second["renamed"] == 0
    assert (after_second.first_name, after_second.last_name) == (first_name, first_last_name)


async def test_generated_name_is_deterministic_from_the_id(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _make_dweller(async_session, vault, first_name="Michael", last_name="Smith")

    first = generate_backfill_name(dweller, RaceOption.SUPER_MUTANT, "average")
    second = generate_backfill_name(dweller, RaceOption.SUPER_MUTANT, "average")

    assert first == second


async def test_curated_template_and_starter_names_are_skipped(async_session: AsyncSession, vault: Vault) -> None:
    await _make_dweller(async_session, vault, first_name="Sarah", last_name="Lyons")
    await _make_dweller(async_session, vault, first_name="Juno", last_name="Pike")

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    assert summary["renamed"] == 0
    assert summary["skipped_curated"] == 2
    sarah = await _find_by_name(async_session, vault.id, "Sarah")
    juno = await _find_by_name(async_session, vault.id, "Juno")
    assert sarah.display_name == "Sarah Lyons"
    assert juno.display_name == "Juno Pike"


async def _find_by_name(async_session: AsyncSession, vault_id: UUID4, first_name: str) -> Dweller:
    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id, limit=100)
    return next(dweller for dweller in dwellers if dweller.first_name == first_name)


async def test_classified_provenance_is_never_touched(async_session: AsyncSession, vault: Vault) -> None:
    curated = await _make_dweller(
        async_session,
        vault,
        first_name="Michael",
        provenance=ContentProvenanceEnum.CURATED,
    )
    player_edited = await _make_dweller(
        async_session,
        vault,
        first_name="Ralph",
        provenance=ContentProvenanceEnum.PLAYER_EDITED,
    )

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    assert summary["scanned"] == 0
    assert (await crud.dweller.get(async_session, curated.id)).display_name == "Michael Smith"
    assert (await crud.dweller.get(async_session, player_edited.id)).display_name == "Ralph Smith"


async def test_post_feature_generated_rows_are_never_touched(async_session: AsyncSession, vault: Vault) -> None:
    """A gen-2 cover name is intentional and must survive later backfill runs."""
    dweller = await _make_dweller(
        async_session,
        vault,
        first_name="Alice",
        last_name="Smith",
        race="synth",
        state="gen_2",
        provenance=ContentProvenanceEnum.GENERATED,
    )

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    unchanged = await crud.dweller.get(async_session, dweller.id)
    assert summary["scanned"] == 0
    assert unchanged.display_name == "Alice Smith"


async def test_gen_three_synths_are_skipped(async_session: AsyncSession, vault: Vault) -> None:
    await _make_dweller(async_session, vault, first_name="Alice", last_name="Smith", race="synth", state="gen_3")

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    assert summary["scanned"] == 1
    assert summary["renamed"] == 0
    assert summary["skipped_other_synth"] == 1


async def test_visible_synths_get_designations(async_session: AsyncSession, vault: Vault) -> None:
    gen_one = await _make_dweller(
        async_session, vault, first_name="Alice", last_name="Smith", race="synth", state="gen_1"
    )
    gen_two = await _make_dweller(
        async_session, vault, first_name="Bob", last_name="Jones", race="synth", state="gen_2"
    )

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    renamed_one = await crud.dweller.get(async_session, gen_one.id)
    renamed_two = await crud.dweller.get(async_session, gen_two.id)
    assert summary["renamed"] == 2
    assert DESIGNATION.fullmatch(renamed_one.first_name)
    assert renamed_one.last_name is None
    assert renamed_two.display_name != "Bob Jones"
    assert renamed_two.content_provenance == ContentProvenanceEnum.GENERATED


async def test_already_shaped_names_are_skipped(async_session: AsyncSession, vault: Vault) -> None:
    await _make_dweller(async_session, vault, first_name="Grog", last_name=None)
    await _make_dweller(async_session, vault, first_name="S2-14", last_name=None, race="synth", state="gen_1")

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    assert summary["renamed"] == 0
    assert summary["skipped_already_shaped"] == 2


async def test_inactive_rows_are_not_candidates(async_session: AsyncSession, vault: Vault) -> None:
    await _make_dweller(async_session, vault, first_name="Dead", is_dead=True)
    await _make_dweller(async_session, vault, first_name="Permanent", is_permanently_dead=True)
    await _make_dweller(async_session, vault, first_name="Departed", availability=AvailabilityEnum.DEPARTURE)

    summary = await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id)

    assert summary["scanned"] == 0
    assert summary["renamed"] == 0


@pytest.mark.parametrize(
    ("state", "expected_pool"),
    [
        ("mild", SUPER_MUTANT_NAMES["mild"]),
        ("average", SUPER_MUTANT_NAMES["average"]),
        ("behemoth", SUPER_MUTANT_NAMES["behemoth"]),
    ],
)
async def test_mutant_names_follow_the_state_pool(
    async_session: AsyncSession, vault: Vault, state: str, expected_pool: tuple[str, ...]
) -> None:
    dweller = await _make_dweller(async_session, vault, first_name="Michael", state=state)

    await dweller_name_backfill_service.backfill_names_for_vault(async_session, vault.id, dry_run=False)

    renamed = await crud.dweller.get(async_session, dweller.id)
    assert renamed.first_name.partition(" the ")[0] in expected_pool
