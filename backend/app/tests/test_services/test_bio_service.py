"""Living biographies — structured entries compiled into Dweller.bio.

Covers entry composition (legacy wrapping, ordering, caps, origin rewrites),
the dedupe/normalization rules on append, and the rendered-bio size guard.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.dweller import BIO_MAX_CHARS, Dweller
from app.schemas.common import GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.bio_service import (
    BIO_ENTRY_CAP,
    bio_service,
    cap_entries,
    compile_bio,
    make_entry,
    truncate_bio,
)
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ContentNoChangeException, ValidationException

TEMPLATE = "Born in Megaton. Before the vault, I wandered the wastes alone."


async def _make_dweller(async_session: AsyncSession, bio: str | None):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller_in = DwellerCreate(
        first_name="Bio",
        last_name="Test",
        gender=GenderEnum.FEMALE,
        rarity=RarityEnum.COMMON,
        level=1,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        bio=bio,
        vault_id=vault.id,
    )
    return await crud.dweller.create(async_session, obj_in=dweller_in)


def test_compile_orders_template_first() -> None:
    entries = [
        make_entry("exploration", "Visited Rivet City."),
        make_entry("template", TEMPLATE),
        make_entry("family", "Married Jane."),
    ]

    assert compile_bio(entries) == f"{TEMPLATE} Visited Rivet City. Married Jane."


def test_compile_caps_entries_dropping_oldest_non_template() -> None:
    entries = [make_entry("template", TEMPLATE)]
    entries += [make_entry("exploration", f"Visited Place {n}.") for n in range(BIO_ENTRY_CAP)]

    compiled = cap_entries(entries)

    assert len(compiled) == BIO_ENTRY_CAP
    assert compiled[0]["source"] == "template"
    assert compiled[-1]["text"] == f"Visited Place {BIO_ENTRY_CAP - 1}."


def test_compile_caps_rendered_length() -> None:
    entries = [make_entry("template", TEMPLATE)]
    entries += [make_entry("exploration", f"Visited {'Very Long Place Name ' * 10}{n}.") for n in range(5)]

    assert len(compile_bio(entries)) <= BIO_MAX_CHARS


def test_make_entry_shape() -> None:
    entry = make_entry("family", "Married Jane.", ref={"partner_id": "abc"})

    assert entry["source"] == "family"
    assert entry["text"] == "Married Jane."
    assert entry["ref"] == {"partner_id": "abc"}
    assert entry["created_at"]


def test_truncate_bio_marks_the_cut() -> None:
    assert truncate_bio("short", 10) == "short"
    assert truncate_bio("x" * 20, 10) == "x" * 7 + "..."


def test_with_entry_wraps_legacy_bio_once() -> None:
    """The composer wraps pre-entries bio text as one legacy entry, then appends."""
    dweller = Dweller(
        first_name="Test",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        bio="Old text.",
    )

    entries = bio_service.with_entry(dweller, "family", "Married Jane.")

    assert [entry["source"] for entry in entries] == ["legacy", "family"]


def test_with_origin_preserves_life_entries() -> None:
    """Rewriting the origin must not discard marriage, birth, or visit entries."""
    dweller = Dweller(
        first_name="Test",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        bio="Old origin.",
        bio_entries=[
            make_entry("template", "Old origin."),
            make_entry("family", "Married Jane.", ref={"partner_id": "p1"}),
            make_entry("exploration", "Visited Rivet City.", ref={"place": "Rivet City"}),
        ],
    )

    entries = bio_service.with_origin(dweller, "New origin.")

    assert [entry["source"] for entry in entries] == ["template", "family", "exploration"]
    assert entries[0]["text"] == "New origin."
    assert entries[1]["ref"] == {"partner_id": "p1"}
    assert entries[2]["ref"] == {"place": "Rivet City"}


def test_origin_text_prefers_the_origin_entry() -> None:
    dweller = Dweller(
        first_name="Test",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        bio="Compiled text.",
        bio_entries=[make_entry("template", "Origin."), make_entry("family", "Married Jane.")],
    )

    assert bio_service.origin_text(dweller) == "Origin."


def test_origin_text_falls_back_to_bio() -> None:
    dweller = Dweller(
        first_name="Test",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        bio="Legacy text.",
    )

    assert bio_service.origin_text(dweller) == "Legacy text."


@pytest.mark.asyncio
async def test_append_wraps_legacy_bio(async_session: AsyncSession) -> None:
    dweller = await _make_dweller(async_session, "Ancient AI words.")

    updated = await bio_service.append_entry(async_session, dweller.id, "family", "Married Jane.")

    sources = [entry["source"] for entry in updated.bio_entries]
    assert sources == ["legacy", "family"]
    assert updated.bio == "Ancient AI words. Married Jane."


@pytest.mark.asyncio
async def test_record_visit_dedupes_place(async_session: AsyncSession) -> None:
    dweller = await _make_dweller(async_session, TEMPLATE)

    await bio_service.record_visit(async_session, dweller.id, "Rivet City")
    updated = await bio_service.record_visit(async_session, dweller.id, "Rivet City")

    visits = [entry for entry in updated.bio_entries if entry["source"] == "exploration"]
    assert len(visits) == 1
    assert "Rivet City" in updated.bio


@pytest.mark.asyncio
async def test_template_entry_seeded_at_creation(async_session: AsyncSession) -> None:
    """Dwellers persisted through the service carry their creation bio as a template entry."""
    from app.services.dweller_service import dweller_service

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller = await dweller_service.create_random_dweller(async_session, vault.id)

    assert dweller.bio_entries
    assert dweller.bio_entries[0]["source"] == "template"
    assert dweller.bio_entries[0]["text"] == dweller.bio


@pytest.mark.asyncio
async def test_append_entry_rejects_blank_text(async_session: AsyncSession) -> None:
    """Whitespace passes a raw length check but records nothing."""
    dweller = await _make_dweller(async_session, TEMPLATE)

    with pytest.raises(ValidationException):
        await bio_service.append_entry(async_session, dweller.id, "dialogue", "          ")


@pytest.mark.asyncio
async def test_append_entry_strips_and_rejects_duplicate_dialogue(async_session: AsyncSession) -> None:
    """Repeated dialogue requests must not stack identical entries."""
    dweller = await _make_dweller(async_session, TEMPLATE)

    updated = await bio_service.append_entry(async_session, dweller.id, "dialogue", "  I keep a wrench.  ")
    assert updated.bio_entries[-1]["text"] == "I keep a wrench."

    with pytest.raises(ContentNoChangeException):
        await bio_service.append_entry(async_session, dweller.id, "dialogue", "I keep a wrench.")
