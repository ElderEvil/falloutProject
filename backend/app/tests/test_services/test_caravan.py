"""Caravan dispatch and resolution (issue #1493, wave 1).

The economy rule under test: a caravan is the safe faucet — no XP, common junk only, roughly half the
material volume of a comparable clear, and one trip per settlement cooldown.
"""

from datetime import timedelta

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerLocationRelationEnum, ExplorationPurpose, ExplorationStatus
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.vault import Vault
from app.models.world_location import VaultLocationState, WorldLocation
from app.schemas.dweller import DwellerCreate
from app.services.exploration.dispatch_resolution import resolve_dispatch_arrival
from app.services.exploration.rewards_calculator import rewards_calculator
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service
from app.utils.exceptions import ValidationException
from app.utils.place_groups import get_place_group, group_for_place_name, load_settlement_trade
from app.utils.place_loot import loot_table
from app.utils.static_data import game_data_store
from app.utils.time import utcnow

CARAVAN = game_config.exploration.caravan


def test_dispatch_request_defaults_to_clearing() -> None:
    """A client that does not know about caravans keeps sending clears, never an accidental trade."""
    from uuid import uuid4

    from app.schemas.exploration import ExpeditionDispatchRequest

    request = ExpeditionDispatchRequest(dweller_ids=[uuid4()], location_id=uuid4())
    assert request.purpose == ExplorationPurpose.CLEAR
    assert (
        ExpeditionDispatchRequest(dweller_ids=[uuid4()], location_id=uuid4(), purpose="trade").purpose
        == ExplorationPurpose.TRADE
    )


async def _register_place(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, name: str = "Megaton", *, unlock: bool = True
) -> tuple[WorldLocation, VaultLocationState]:
    """Register a map point for the vault, claiming an origin slot the first time (dispatch needs one)."""
    from app.crud.vault_slot import vault_slot

    if await vault_slot.get_by_vault(async_session, vault.id) is None:
        await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
        await async_session.commit()
    await map_service.register_bio_places(async_session, dweller, origin_place=name, visited_places=[])
    result = await async_session.execute(
        select(VaultLocationState)
        .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
        .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == name)
    )
    state = result.scalar_one()
    if unlock:
        await crud.world_location.link_dweller(
            async_session, dweller.id, state.location_id, DwellerLocationRelationEnum.VISITED, is_unlocked=True
        )
    location = await crud.world_location.get_registry(async_session, state.location_id)
    return location, state


async def _trade(async_session: AsyncSession, vault: Vault, dweller: Dweller, location: WorldLocation) -> Exploration:
    return await exploration_service.dispatch(
        async_session, vault.id, [dweller.id], location.id, purpose=ExplorationPurpose.TRADE
    )


def test_shipment_stays_under_half_of_the_comparable_clear() -> None:
    """The guardrail, as arithmetic: expected units per trip <= 55% of one comparable clear's haul."""
    for entry in load_settlement_trade().values():
        group = get_place_group(group_for_place_name(entry["comparable"]))
        haul = loot_table(group["loot_table"])["items"]
        junk_units = sum(1 for item in haul if item["type"] == "junk")
        expected = sum(entry["band"]) / 2
        assert expected <= 0.55 * junk_units, f"{entry['place']} ships {expected} vs a {junk_units}-unit clear"


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_trade_charges_one_flat_fee_and_marks_the_run(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    location, _state = await _register_place(async_session, vault, dweller)
    before = vault.bottle_caps

    exploration = await _trade(async_session, vault, dweller, location)

    await async_session.refresh(vault)
    assert exploration.purpose == ExplorationPurpose.TRADE
    assert exploration.clear_tier is None
    assert exploration.target_location_id == location.id
    assert vault.bottle_caps == before - CARAVAN.caps_cost_settlement


@pytest.mark.usefixtures("default_world_snapshot")
async def test_trade_refuses_places_and_states_it_cannot_serve(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    rocket, _rocket_state = await _register_place(async_session, vault, dweller, "Red Rocket")
    with pytest.raises(ValidationException, match="Nothing to trade here"):
        await _trade(async_session, vault, dweller, rocket)

    memorial, _memorial_state = await _register_place(async_session, vault, dweller, "Jefferson Memorial")
    with pytest.raises(ValidationException, match="Nothing to trade here"):
        await _trade(async_session, vault, dweller, memorial)

    hidden, _hidden_state = await _register_place(async_session, vault, dweller, "Arefu", unlock=False)
    with pytest.raises(ValidationException, match="not known to the vault"):
        await _trade(async_session, vault, dweller, hidden)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_trade_refuses_a_settlement_that_is_busy_or_cooling(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, state = await _register_place(async_session, vault, dweller)
    other = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    first = await _trade(async_session, vault, dweller, location)
    with pytest.raises(ValidationException, match="already on its way"):
        await _trade(async_session, vault, other, location)

    # A returning party still holds the destination: the unique index covers ACTIVE only.
    first.status = ExplorationStatus.RETURNING
    async_session.add(first)
    await async_session.commit()
    with pytest.raises(ValidationException, match="already on its way"):
        await _trade(async_session, vault, other, location)

    first.status = ExplorationStatus.COMPLETED
    async_session.add(first)
    await async_session.commit()
    state.caravan_available_at = utcnow() + timedelta(hours=1)
    async_session.add(state)
    await async_session.commit()
    with pytest.raises(ValidationException, match="no caravan ready yet"):
        await _trade(async_session, vault, other, location)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_trade_refuses_an_unaffordable_fee_without_touching_the_vault(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    location, _state = await _register_place(async_session, vault, dweller)
    vault.bottle_caps = CARAVAN.caps_cost_settlement - 1
    async_session.add(vault)
    await async_session.commit()

    with pytest.raises(ValidationException, match="costs 150 caps"):
        await _trade(async_session, vault, dweller, location)

    await async_session.refresh(vault)
    assert vault.bottle_caps == CARAVAN.caps_cost_settlement - 1
    rows = await async_session.execute(select(Exploration).where(Exploration.vault_id == vault.id))
    assert rows.first() is None


@pytest.mark.usefixtures("default_world_snapshot")
async def test_map_offers_trade_exactly_when_dispatch_accepts(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Read/write parity: whatever the map advertises, the service must accept."""
    location, state = await _register_place(async_session, vault, dweller)

    detail = await map_service.get_location_detail(async_session, vault, location.id)
    assert detail.action == "trade"
    assert detail.caravan is not None
    assert detail.caravan.refusal_reason is None
    assert detail.caravan.caps_cost == CARAVAN.caps_cost_settlement
    await _trade(async_session, vault, dweller, location)

    detail = await map_service.get_location_detail(async_session, vault, location.id)
    assert detail.action == "none"
    assert detail.caravan is not None
    assert detail.caravan.refusal_reason is not None
    with pytest.raises(ValidationException):
        await _trade(async_session, vault, dweller, location)

    state.caravan_available_at = utcnow() + timedelta(hours=6)
    async_session.add(state)
    await async_session.commit()
    detail = await map_service.get_location_detail(async_session, vault, location.id)
    assert detail.action == "none"
    assert detail.caravan.cooldown_remaining_seconds > 0


@pytest.mark.usefixtures("default_world_snapshot")
async def test_resolution_pays_a_common_shipment_and_starts_the_cooldown(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    location, state = await _register_place(async_session, vault, dweller)
    exploration = await _trade(async_session, vault, dweller, location)

    await resolve_dispatch_arrival(async_session, exploration.id, arrived=True)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    shipped = exploration.loot_collected
    assert 1 <= len(shipped) <= 2
    entry = load_settlement_trade()["megaton"]
    common_steel = [
        item
        for item in game_data_store.junk_items
        if str(item.junk_type).lower() == entry["material"] and str(item.rarity).lower() == "common"
    ]
    assert shipped[0]["item_name"] == common_steel[0].name
    assert all(item["rarity"].lower() == "common" for item in shipped)
    released = state.caravan_available_at - utcnow()
    assert timedelta(hours=23) < released <= timedelta(hours=CARAVAN.revisit_hours_settlement)
    # A caravan never touches the clear clock.
    assert state.reclear_available_at is None


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_cooldown_stamped_between_the_pre_check_and_the_fee_still_blocks(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eligibility is re-checked under the vault lock: the pre-check window is not authoritative."""
    from app.services.world_snapshot_service import world_snapshot_service

    location, state = await _register_place(async_session, vault, dweller)
    before = vault.bottle_caps
    generate = world_snapshot_service.get_or_generate

    async def _stamp_cooldown(*args, **kwargs):
        snapshot = await generate(*args, **kwargs)
        state.caravan_available_at = utcnow() + timedelta(hours=1)
        async_session.add(state)
        await async_session.commit()
        return snapshot

    monkeypatch.setattr(world_snapshot_service, "get_or_generate", _stamp_cooldown)
    with pytest.raises(ValidationException, match="no caravan ready yet"):
        await _trade(async_session, vault, dweller, location)

    await async_session.refresh(vault)
    assert vault.bottle_caps == before


@pytest.mark.usefixtures("default_world_snapshot")
async def test_a_departure_that_fails_after_the_debit_leaves_no_trace(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fee is charged in the departure transaction: a later failure must roll back the whole trip."""
    location, _state = await _register_place(async_session, vault, dweller)
    before = vault.bottle_caps

    async def _explode(*_args, **_kwargs):
        raise RuntimeError("departure failed after the debit")

    monkeypatch.setattr(exploration_service, "_persist_departure_transaction", _explode)
    with pytest.raises(RuntimeError):
        await _trade(async_session, vault, dweller, location)
    await async_session.rollback()

    await async_session.refresh(vault)
    await async_session.refresh(dweller)
    assert vault.bottle_caps == before
    assert dweller.status.value != "exploring"
    rows = await async_session.execute(select(Exploration).where(Exploration.vault_id == vault.id))
    assert rows.first() is None


@pytest.mark.usefixtures("default_world_snapshot")
async def test_trade_run_grants_no_xp(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    location, _state = await _register_place(async_session, vault, dweller)
    exploration = await _trade(async_session, vault, dweller, location)
    await resolve_dispatch_arrival(async_session, exploration.id, arrived=True)
    await async_session.refresh(exploration)
    exploration.total_distance = 12  # distance XP accrues on the move; the grant point must ignore it

    assert rewards_calculator.calculate_exploration_xp(exploration, dweller) > 0
    assert await rewards_service._grant_member_xp(async_session, exploration, dweller) == 0
