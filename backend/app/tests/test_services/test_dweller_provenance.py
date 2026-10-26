"""Tests for dweller content provenance classification."""

from __future__ import annotations

from uuid import UUID

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ContentProvenanceEnum, GenderEnum, RarityEnum
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride
from app.services.dweller_service import dweller_service
from app.services.family.breeding_service import BreedingService
from app.services.rewards import items, lunchbox
from app.services.rewards.settlement import _parse_objective_reward
from app.utils.static_data import game_data_store


def _create_payload(vault_id: UUID4, first_name: str, gender: GenderEnum) -> DwellerCreate:
    return DwellerCreate(
        first_name=first_name,
        last_name="Tester",
        gender=gender,
        rarity=RarityEnum.COMMON,
        vault_id=vault_id,
    )


async def test_random_dweller_is_generated(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await dweller_service.create_random_dweller(async_session, vault.id, seed=101)

    assert dweller.content_provenance == ContentProvenanceEnum.GENERATED


async def test_custom_name_override_is_player_edited(async_session: AsyncSession, vault: Vault) -> None:
    override = DwellerCreateCommonOverride(first_name="Custom", last_name="Name")

    dweller = await dweller_service.create_random_dweller(async_session, vault.id, obj_in=override, seed=102)

    assert dweller.content_provenance == ContentProvenanceEnum.PLAYER_EDITED


async def test_curated_template_is_curated(async_session: AsyncSession, vault: Vault) -> None:
    template = game_data_store.get_dwellers_by_rarity(RarityEnum.LEGENDARY.value)[0]

    dweller = await dweller_service.create_dweller_from_template(async_session, vault.id, template.template_id)

    assert dweller.content_provenance == ContentProvenanceEnum.CURATED


async def test_random_legendary_template_is_curated(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await dweller_service.create_random_dweller(
        async_session,
        vault.id,
        seed=105,
        rarity=RarityEnum.LEGENDARY,
    )

    assert dweller.content_provenance == ContentProvenanceEnum.CURATED


async def test_explicit_create_defaults_to_player_edited(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await dweller_service.create_dweller(
        async_session,
        _create_payload(vault.id, "Admin", GenderEnum.MALE),
    )

    assert dweller.content_provenance == ContentProvenanceEnum.PLAYER_EDITED


async def test_rename_marks_player_edited(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await dweller_service.create_random_dweller(async_session, vault.id, seed=103)

    updated = await dweller_service.update_dweller(async_session, dweller.id, {"first_name": "Renamed"})

    assert updated.content_provenance == ContentProvenanceEnum.PLAYER_EDITED


async def test_unchanged_name_update_keeps_provenance(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await dweller_service.create_random_dweller(async_session, vault.id, seed=104)

    updated = await dweller_service.update_dweller(
        async_session,
        dweller.id,
        {"first_name": dweller.first_name, "last_name": dweller.last_name},
    )

    assert updated.content_provenance == ContentProvenanceEnum.GENERATED


def test_lunchbox_common_dweller_is_generated() -> None:
    payload = lunchbox._lunchbox_common_dweller_data(1, RarityEnum.COMMON)

    assert payload["content_provenance"] == ContentProvenanceEnum.GENERATED


def test_starter_resident_reward_is_curated() -> None:
    reward_type, payload = _parse_objective_reward("dweller:Juno Pike")

    assert payload["content_provenance"] == ContentProvenanceEnum.CURATED


def test_non_starter_named_reward_is_curated() -> None:
    reward_type, payload = _parse_objective_reward("dweller:Riley Smith")

    assert payload["content_provenance"] == ContentProvenanceEnum.CURATED


async def test_named_item_dweller_is_curated(async_session: AsyncSession, vault: Vault) -> None:
    result = await items._grant_as_dweller(async_session, vault.id, "Riley Smith", "common", 1)

    dweller = await crud.dweller.get(async_session, UUID(result["dweller_id"]))
    assert dweller.content_provenance == ContentProvenanceEnum.CURATED


async def test_grant_dweller_uses_supplied_provenance(async_session: AsyncSession, vault: Vault) -> None:
    result = await items.grant_dweller(
        async_session,
        vault.id,
        {
            "first_name": "Curated",
            "last_name": "Resident",
            "rarity": "common",
            "content_provenance": ContentProvenanceEnum.CURATED,
        },
    )

    dweller = await crud.dweller.get(async_session, UUID(result["dweller_id"]))
    assert dweller.content_provenance == ContentProvenanceEnum.CURATED


async def test_newborn_is_generated(async_session: AsyncSession, vault: Vault) -> None:
    mother = await dweller_service.create_dweller(
        async_session,
        _create_payload(vault.id, "Mother", GenderEnum.FEMALE),
    )
    father = await dweller_service.create_dweller(
        async_session,
        _create_payload(vault.id, "Father", GenderEnum.MALE),
    )

    child = await BreedingService._create_newborn(async_session, mother, father, commit=True)

    assert child.content_provenance == ContentProvenanceEnum.GENERATED
