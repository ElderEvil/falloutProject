"""Magazines: a once-per-vault claim, plus a timed buff renewed on a fixed 24h site clock.

The claim is permanent set progress; the buff is the repeating rhythm and expires on read in
``effective_stat``. These tests drive the real dispatch arrival so the site marker, the claim, the
buff and the cooldown are exercised together — the failure modes are the places they can disagree.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DeathCauseEnum, DwellerLocationRelationEnum
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.models.collectible import VaultCollectible
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.world_location import VaultLocationState, WorldLocation
from app.options.identity_modifiers import effective_stat
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.collectible_service import collectible_service
from app.services.dweller_recycling_service import dweller_recycling_service
from app.services.exploration.dispatch_resolution import resolve_dispatch_arrival
from app.services.exploration_service import exploration_service
from app.services.family.death_service import death_service
from app.services.map_service import map_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ValidationException
from app.utils.time import utcnow

SITE = "National Archives"
NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


async def _dweller(async_session: AsyncSession, vault: Vault, *, luck: int = 5) -> Dweller:
    data = create_fake_adult_dweller()
    data.update({"first_name": "Reader", "last_name": "Dweller", "health": 100, "max_health": 100, "luck": luck})
    return await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))


async def _site(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> tuple[WorldLocation, VaultLocationState]:
    """Register the magazine place as a known, inert map point."""
    await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()
    await map_service.register_bio_places(async_session, dweller, origin_place=SITE, visited_places=[])
    state = (
        await async_session.execute(
            select(VaultLocationState)
            .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
            .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == SITE)
        )
    ).scalar_one()
    await crud.world_location.link_dweller(
        async_session, dweller.id, state.location_id, DwellerLocationRelationEnum.VISITED, is_unlocked=True
    )
    return await crud.world_location.get_registry(async_session, state.location_id), state


async def _arrive(async_session: AsyncSession, vault: Vault, dweller: Dweller, location: WorldLocation) -> None:
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    await resolve_dispatch_arrival(async_session, exploration.id)


async def _claims(async_session: AsyncSession, vault: Vault, key: str) -> int:
    return (
        await async_session.execute(
            select(func.count())
            .select_from(VaultCollectible)
            .where(VaultCollectible.vault_id == vault.id, VaultCollectible.collectible_key == key)
        )
    ).scalar_one()


def _buff(stat: str, amount: int, expires_at: datetime) -> dict:
    return {"key": "guns_and_bullets", "stat": stat, "amount": amount, "expires_at": expires_at.isoformat()}


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_first_read_claims_once_and_writes_no_permanent_bonus(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim is set progress only: a magazine must never leak into ``collectible_bonus``."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, state = await _site(async_session, vault, dweller)

    await _arrive(async_session, vault, dweller, location)
    await async_session.refresh(dweller)
    await async_session.refresh(state)

    assert await _claims(async_session, vault, "guns_and_bullets") == 1
    assert dweller.collectible_bonus is None
    assert dweller.magazine_buff is not None
    assert (dweller.magazine_buff["key"], dweller.magazine_buff["stat"], dweller.magazine_buff["amount"]) == (
        "guns_and_bullets",
        "perception",
        2,
    )
    # The site stays open for a reread: the read clock, never the one-shot salvage marker.
    assert state.last_read_at is not None
    assert state.searched_at is None


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_reread_inside_the_cooldown_is_refused(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, _state = await _site(async_session, vault, dweller)
    await _arrive(async_session, vault, dweller, location)
    other = await _dweller(async_session, vault)

    with pytest.raises(ValidationException, match="cannot be cleared"):
        await exploration_service.dispatch(async_session, vault.id, [other.id], location.id)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_reread_after_the_cooldown_refreshes_the_buff_with_no_second_claim(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, state = await _site(async_session, vault, dweller)
    await _arrive(async_session, vault, dweller, location)
    state.last_read_at = utcnow() - timedelta(hours=25)
    async_session.add(state)
    await async_session.commit()
    other = await _dweller(async_session, vault, luck=9)

    await _arrive(async_session, vault, other, location)
    await async_session.refresh(other)

    assert await _claims(async_session, vault, "guns_and_bullets") == 1
    assert other.magazine_buff is not None
    assert other.magazine_buff["key"] == "guns_and_bullets"


@pytest.mark.parametrize(
    ("held", "hours"),
    [((), 6), (("tesla_science", "wasteland_survival_guide"), 12)],
    ids=["single", "complete-set"],
)
async def test_the_buff_is_six_hours_and_the_completed_shelf_overrides_it_to_twelve(
    async_session: AsyncSession,
    vault: Vault,
    monkeypatch: pytest.MonkeyPatch,
    held: tuple[str, ...],
    hours: int,
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    monkeypatch.setattr("app.services.collectible_service.utcnow", lambda: NOW)
    reader = await _dweller(async_session, vault)
    for key in held:
        assert await collectible_service.award(async_session, vault_id=vault.id, dweller=reader, collectible_key=key)

    payload = await collectible_service.award_site_collectible(
        async_session,
        exploration=SimpleNamespace(vault_id=vault.id),
        location=SimpleNamespace(id=uuid4(), name=SITE),
        members=[reader],
        action="salvage",
    )

    assert payload is not None
    assert reader.magazine_buff["expires_at"] == (NOW + timedelta(hours=hours)).isoformat()


def test_a_live_buff_raises_only_its_own_stat(dweller: Dweller, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.options.identity_modifiers.utcnow", lambda: NOW)
    perception, intelligence = effective_stat(dweller, "perception"), effective_stat(dweller, "intelligence")
    dweller.magazine_buff = _buff("perception", 2, NOW + timedelta(hours=6))

    assert effective_stat(dweller, "perception") == perception + 2
    assert effective_stat(dweller, "intelligence") == intelligence


def test_an_expired_buff_adds_nothing(dweller: Dweller, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.options.identity_modifiers.utcnow", lambda: NOW)
    base = effective_stat(dweller, "endurance")
    dweller.magazine_buff = _buff("endurance", 2, NOW)

    assert effective_stat(dweller, "endurance") == base


@pytest.mark.parametrize(
    "buff",
    [None, {}, {"stat": "perception"}, {"stat": "perception", "amount": 2, "expires_at": "not-a-date"}],
    ids=["absent", "empty", "no-expiry", "unreadable-expiry"],
)
def test_a_missing_or_unreadable_buff_is_neutral(
    dweller: Dweller, monkeypatch: pytest.MonkeyPatch, buff: dict | None
) -> None:
    """A JSONB column can hold a hand-edited row; reading a stat must not start raising."""
    monkeypatch.setattr("app.options.identity_modifiers.utcnow", lambda: NOW)
    base = effective_stat(dweller, "perception")
    dweller.magazine_buff = buff

    assert effective_stat(dweller, "perception") == base


async def test_death_clears_the_buff_and_revival_leaves_it_clear(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _dweller(async_session, vault)
    dweller.magazine_buff = _buff("perception", 2, utcnow() + timedelta(hours=6))
    async_session.add(dweller)
    await async_session.commit()

    await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.HEALTH)
    await async_session.refresh(dweller)
    assert dweller.magazine_buff is None

    vault.bottle_caps = 999_999
    async_session.add(vault)
    await async_session.commit()
    user = await crud.user.get(async_session, vault.user_id)
    await death_service.revive_dweller(async_session, dweller.id, user)
    revived = await crud.dweller.get(async_session, dweller.id)
    assert revived.magazine_buff is None


async def test_cross_vault_recycling_clears_the_buff(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _dweller(async_session, vault)
    dweller.magazine_buff = _buff("perception", 2, utcnow() + timedelta(hours=6))
    async_session.add(dweller)
    await async_session.commit()
    await crud.dweller.soft_delete(async_session, dweller.id)
    other_vault = await crud.vault.create(
        db_session=async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=vault.user_id)
    )

    recycled = await dweller_recycling_service.recycle_dweller_for_vault(
        async_session, dweller.id, other_vault.id, reset_stats=False
    )

    assert recycled.magazine_buff is None
