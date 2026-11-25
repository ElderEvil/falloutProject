"""Magazines: a one-time find that claims the site and leaves a permanent boon on the finder.

A magazine is not a rhythm: the first arrival claims it for the vault, stamps ``searched_at`` exactly
like a bobblehead or comic, and the finder keeps +1 to the magazine's stat for good — +2 once the
shelf is complete. These tests drive the real dispatch arrival, so the site marker, the claim, the
boon and the closed map action are exercised together; the failure modes are the places they can
disagree.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DeathCauseEnum, DwellerLocationRelationEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.models.collectible import VaultCollectible
from app.models.dweller import Dweller
from app.models.exploration import Exploration
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
KEY = "guns_and_bullets"
BOON = {KEY: {"stat": "perception", "amount": 1}}


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


async def _depart(async_session: AsyncSession, vault: Vault, dweller: Dweller, location: WorldLocation) -> Exploration:
    """Send one dweller out and age the run to arrival, without resolving it."""
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    return exploration


async def _arrive(async_session: AsyncSession, vault: Vault, dweller: Dweller, location: WorldLocation) -> None:
    exploration = await _depart(async_session, vault, dweller, location)
    await resolve_dispatch_arrival(async_session, exploration.id)


async def _claims(async_session: AsyncSession, vault: Vault, key: str) -> int:
    return (
        await async_session.execute(
            select(func.count())
            .select_from(VaultCollectible)
            .where(VaultCollectible.vault_id == vault.id, VaultCollectible.collectible_key == key)
        )
    ).scalar_one()


@pytest.fixture
def collectible_events() -> Iterator[list[dict]]:
    """Record every COLLECTIBLE_FOUND the bus actually delivers during one test.

    A real subscriber, not a mock: the assertion is that evaluators never see the event, which is
    what a rollback has to guarantee.
    """
    delivered: list[dict] = []

    async def record(_event_type: str, _vault_id: UUID, data: dict) -> None:
        delivered.append(data)

    event_bus.subscribe(GameEvent.COLLECTIBLE_FOUND, record)
    try:
        yield delivered
    finally:
        event_bus.unsubscribe(GameEvent.COLLECTIBLE_FOUND, record)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_first_read_claims_once_leaves_a_permanent_boon_and_closes_the_site(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim is set progress, the boon is the finder's for good, and the site is spent."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, state = await _site(async_session, vault, dweller)

    await _arrive(async_session, vault, dweller, location)
    await async_session.refresh(dweller)
    await async_session.refresh(state)

    assert await _claims(async_session, vault, KEY) == 1
    # A magazine must never leak into the bobblehead/comic column...
    assert dweller.collectible_bonus is None
    # ...and its own column is the whole boon: no clock, no expiry.
    assert dweller.magazine_boon == BOON
    # The site closes exactly like a bobblehead or comic site: one find, then nothing.
    assert state.searched_at is not None


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_claimed_site_awards_nothing_to_a_second_arrival(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once read, the site is not a destination and the award path refuses it outright."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, _state = await _site(async_session, vault, dweller)
    await _arrive(async_session, vault, dweller, location)
    latecomer = await _dweller(async_session, vault, luck=9)

    with pytest.raises(ValidationException, match="cannot be cleared"):
        await exploration_service.dispatch(async_session, vault.id, [latecomer.id], location.id)

    awarded = await collectible_service.award_site_collectible(
        async_session,
        exploration=SimpleNamespace(vault_id=vault.id),
        location=location,
        members=[latecomer],
        action="salvage",
    )

    assert awarded is None
    assert latecomer.magazine_boon is None
    assert await _claims(async_session, vault, KEY) == 1


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_late_failure_after_the_claim_and_boon_are_staged_leaves_the_site_unread_and_unclaimed(
    async_session: AsyncSession,
    db_connection: AsyncConnection,
    vault: Vault,
    dweller: Dweller,
    monkeypatch: pytest.MonkeyPatch,
    collectible_events: list[dict],
) -> None:
    """A failure in the return leg must unwind the site marker, the claim and the boon together.

    The run's transaction owner is ``start_return``; everything before it only stages. The injected
    fault lands on that owner's own write (the transition to RETURNING), so the site marker, the
    claim and the boon have already reached the database inside the transaction when it fails.
    """
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, state = await _site(async_session, vault, dweller)
    exploration = await _depart(async_session, vault, dweller, location)

    statements: list[str] = []

    def reject_return_leg(_connection, _cursor, statement, _parameters, _context, _executemany) -> None:
        statements.append(statement)
        if statement.startswith("UPDATE exploration SET") and "return_started_at" in statement:
            raise RuntimeError("injected return-leg write failure")

    event.listen(db_connection.sync_connection, "before_cursor_execute", reject_return_leg)
    try:
        with pytest.raises(RuntimeError, match="injected return-leg write failure"):
            await resolve_dispatch_arrival(async_session, exploration.id)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", reject_return_leg)

    # The failing statement is last, and the site marker, the claim insert and the boon update had
    # already run: this is the ordering the test is about, read off the real SQL, not off the hook.
    assert any(
        statement.startswith("UPDATE vaultlocationstate SET") and "searched_at" in statement for statement in statements
    )
    assert any(statement.startswith("INSERT INTO vaultcollectible") for statement in statements)
    assert any(statement.startswith("UPDATE dweller SET") and "magazine_boon" in statement for statement in statements)

    await async_session.rollback()
    # Reload from the session: the failed call mutated these objects in memory before it raised.
    await async_session.refresh(dweller)
    await async_session.refresh(state)
    await async_session.refresh(exploration)
    await async_session.refresh(vault)

    assert dweller.magazine_boon is None
    assert state.searched_at is None
    assert await _claims(async_session, vault, KEY) == 0
    assert exploration.total_caps_found == 0
    assert exploration.is_active()
    assert collectible_events == []


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_run_landing_on_an_already_searched_site_stages_nothing_and_returns_home(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    monkeypatch: pytest.MonkeyPatch,
    collectible_events: list[dict],
) -> None:
    """A closed site is an ordinary rejection: no claim, no boon change, no event, run comes home.

    ``uq_exploration_active_target`` allows one active run per point, so the site closing under an
    in-flight run is the only way the marker can already be set on arrival; the marker is modelled
    directly rather than raced.
    """
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, state = await _site(async_session, vault, dweller)
    live_boon = {"key": "tesla_science", "stat": "intelligence", "amount": 1}
    dweller.magazine_boon = live_boon
    async_session.add(dweller)
    await async_session.commit()
    exploration = await _depart(async_session, vault, dweller, location)
    stamp = utcnow() - timedelta(minutes=5)
    state.searched_at = stamp
    async_session.add(state)
    await async_session.commit()

    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(dweller)
    await async_session.refresh(state)
    await async_session.refresh(exploration)

    assert dweller.magazine_boon == live_boon
    assert state.searched_at == stamp
    assert await _claims(async_session, vault, KEY) == 0
    assert collectible_events == []
    # The refusal still sends the run home: nothing is staged, but the run is not left hanging.
    assert not exploration.is_active()


@pytest.mark.parametrize(
    ("held", "amount"),
    [((), 1), (("tesla_science", "wasteland_survival_guide"), 2)],
    ids=["single", "complete-shelf"],
)
async def test_the_completed_shelf_upgrades_the_same_boon_from_one_point_to_two(
    async_session: AsyncSession,
    vault: Vault,
    monkeypatch: pytest.MonkeyPatch,
    held: tuple[str, ...],
    amount: int,
) -> None:
    """The shelf pays on the read that completes it, and it upgrades the boon rather than stacking one."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    reader = await _dweller(async_session, vault)
    for key in held:
        assert await collectible_service.award(async_session, vault_id=vault.id, dweller=reader, collectible_key=key)
    base = effective_stat(reader, "perception")

    payload = await collectible_service.award_site_collectible(
        async_session,
        exploration=SimpleNamespace(vault_id=vault.id),
        location=SimpleNamespace(id=uuid4(), name=SITE),
        members=[reader],
        action="salvage",
    )

    assert payload is not None
    assert payload.amount == amount
    assert (reader.magazine_boon or {})[KEY] == {"stat": "perception", "amount": amount}
    assert effective_stat(reader, "perception") == base + amount


async def test_completing_the_shelf_raises_the_boons_claimed_before_it_closed(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shelf pays every holder, not just the finder who happened to complete it."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    early = await _dweller(async_session, vault)
    late = await _dweller(async_session, vault)
    base = effective_stat(early, "perception")

    assert await collectible_service.award(
        async_session, vault_id=vault.id, dweller=early, collectible_key="guns_and_bullets"
    )
    assert (early.magazine_boon or {})["guns_and_bullets"]["amount"] == 1
    assert effective_stat(early, "perception") == base + 1

    for key in ("tesla_science", "wasteland_survival_guide"):
        assert await collectible_service.award(async_session, vault_id=vault.id, dweller=late, collectible_key=key)

    assert (early.magazine_boon or {})["guns_and_bullets"]["amount"] == 2
    assert effective_stat(early, "perception") == base + 2


async def test_a_second_magazine_adds_to_the_first_instead_of_replacing_it(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Permanent means permanent: a finder who reads another magazine keeps the first boon too."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    reader = await _dweller(async_session, vault)
    perception, intelligence = effective_stat(reader, "perception"), effective_stat(reader, "intelligence")

    for key in ("guns_and_bullets", "tesla_science"):
        await collectible_service.award(async_session, vault_id=vault.id, dweller=reader, collectible_key=key)

    assert set(reader.magazine_boon) == {"guns_and_bullets", "tesla_science"}
    assert effective_stat(reader, "perception") == perception + 1
    assert effective_stat(reader, "intelligence") == intelligence + 1


async def test_the_boon_raises_only_the_finders_own_stat(async_session: AsyncSession, vault: Vault) -> None:
    finder = await _dweller(async_session, vault)
    bystander = await _dweller(async_session, vault, luck=1)
    perception, intelligence = effective_stat(finder, "perception"), effective_stat(finder, "intelligence")
    untouched = effective_stat(bystander, "perception")

    finder.magazine_boon = dict(BOON)

    assert effective_stat(finder, "perception") == perception + 1
    assert effective_stat(finder, "intelligence") == intelligence
    # A dweller who never found the magazine is unaffected by another's boon.
    assert effective_stat(bystander, "perception") == untouched


@pytest.mark.parametrize(
    "boon",
    [None, {}, {"stat": "perception"}, {"stat": "perception", "amount": "2"}, {"stat": "perception", "amount": True}],
    ids=["absent", "empty", "no-amount", "unreadable-amount", "boolean-amount"],
)
def test_a_missing_or_unreadable_boon_is_neutral(dweller: Dweller, boon: dict | None) -> None:
    """A JSONB column can hold a hand-edited row; reading a stat must not start raising."""
    base = effective_stat(dweller, "perception")
    dweller.magazine_boon = boon

    assert effective_stat(dweller, "perception") == base


async def test_death_clears_the_boon_and_revival_leaves_it_clear(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _dweller(async_session, vault)
    dweller.magazine_boon = dict(BOON)
    async_session.add(dweller)
    await async_session.commit()

    await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.HEALTH)
    await async_session.refresh(dweller)
    assert dweller.magazine_boon is None

    vault.bottle_caps = 999_999
    async_session.add(vault)
    await async_session.commit()
    user = await crud.user.get(async_session, vault.user_id)
    await death_service.revive_dweller(async_session, dweller.id, user)
    revived = await crud.dweller.get(async_session, dweller.id)
    assert revived.magazine_boon is None


async def test_cross_vault_recycling_clears_the_boon(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _dweller(async_session, vault)
    dweller.magazine_boon = dict(BOON)
    async_session.add(dweller)
    await async_session.commit()
    await crud.dweller.soft_delete(async_session, dweller.id)
    other_vault = await crud.vault.create(
        db_session=async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=vault.user_id)
    )

    recycled = await dweller_recycling_service.recycle_dweller_for_vault(
        async_session, dweller.id, other_vault.id, reset_stats=False
    )

    assert recycled.magazine_boon is None
