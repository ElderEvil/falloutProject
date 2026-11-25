"""Pack capacity behaviour while an exploration is running."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ExplorationStatus
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.vault import Vault
from app.schemas.exploration_event import ExplorationEventType
from app.services.exploration.event_service import apply_loot_find
from app.services.exploration_service import exploration_service


async def _active_run(async_session: AsyncSession, vault: Vault, dweller: Dweller, strength: int = 1) -> Exploration:
    """Send a dweller out, then pin the run's snapshot strength so capacity is deterministic."""
    run = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    run.dweller_strength = strength
    async_session.add(run)
    await async_session.commit()
    await async_session.refresh(run)
    return run


def _fill_pack(run: Exploration, slots: int) -> None:
    for index in range(slots):
        assert run.add_loot(item_name=f"Junk {index}", rarity="Common", item_type="junk") is True


def _pack_full_events(run: Exploration) -> list[dict]:
    return [event for event in run.events if event["type"] == ExplorationEventType.PACK_FULL]


async def test_a_find_that_fits_is_appended(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    run = await _active_run(async_session, vault, dweller, strength=5)

    assert apply_loot_find(run, item_name="Desk Fan", rarity="Common", item_type="junk", caps=12) is True

    assert [entry["item_name"] for entry in run.loot_collected] == ["Desk Fan"]
    assert run.pack_slots_used == 1
    assert _pack_full_events(run) == []
    assert run.status == ExplorationStatus.ACTIVE
    assert run.total_caps_found == 12


async def test_the_find_that_fills_the_pack_exactly_still_fits(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    run = await _active_run(async_session, vault, dweller, strength=1)
    assert run.carry_capacity == 17
    _fill_pack(run, 16)

    assert apply_loot_find(run, item_name="Desk Fan", rarity="Common", item_type="junk", caps=0) is True

    assert run.pack_slots_used == run.carry_capacity == 17
    assert len(run.loot_collected) == 17
    assert run.status == ExplorationStatus.ACTIVE
    assert _pack_full_events(run) == []


async def test_the_next_find_is_refused_logs_one_event_and_starts_the_return(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    run = await _active_run(async_session, vault, dweller, strength=1)
    _fill_pack(run, 17)

    assert apply_loot_find(run, item_name="Wonderglue", rarity="Common", item_type="junk", caps=9) is False

    async_session.add(run)
    await async_session.commit()
    await async_session.refresh(run)

    assert run.pack_slots_used == 17
    assert all(entry["item_name"] != "Wonderglue" for entry in run.loot_collected)
    events = _pack_full_events(run)
    assert len(events) == 1
    assert events[0]["description"] == "Pack full — the Wonderglue stays behind."
    # Caps are found even when the item is left behind.
    assert run.total_caps_found == 9
    assert run.status == ExplorationStatus.RETURNING
    assert run.return_started_at is not None
    assert run.return_completes_at is not None


async def test_a_second_refusal_logs_but_does_not_restart_the_trip_home(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    run = await _active_run(async_session, vault, dweller, strength=1)
    _fill_pack(run, 17)
    apply_loot_find(run, item_name="Wonderglue", rarity="Common", item_type="junk", caps=0)
    started_at = run.return_started_at
    completes_at = run.return_completes_at

    assert apply_loot_find(run, item_name="Duct tape", rarity="Common", item_type="junk", caps=0) is False

    assert len(_pack_full_events(run)) == 2
    assert run.status == ExplorationStatus.RETURNING
    assert run.return_started_at == started_at
    assert run.return_completes_at == completes_at


async def test_a_full_pack_does_not_send_home_a_run_already_returning(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    run = await _active_run(async_session, vault, dweller, strength=1)
    run.start_return()
    started_at = run.return_started_at
    completes_at = run.return_completes_at
    _fill_pack(run, 17)

    assert apply_loot_find(run, item_name="Wonderglue", rarity="Common", item_type="junk", caps=0) is False

    assert len(_pack_full_events(run)) == 1
    assert run.status == ExplorationStatus.RETURNING
    assert run.recalled_early is False
    assert run.return_started_at == started_at
    assert run.return_completes_at == completes_at
