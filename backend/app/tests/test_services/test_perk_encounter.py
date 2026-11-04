"""Ordinary site choices enforce perks and settle the haul only once."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event

from app import crud
from app.core.enums import AgeGroupEnum, DwellerPerk, DwellerStatusEnum, ExpeditionRunStatus
from app.options.perks import PERKS
from app.schemas.expedition import ExpeditionResolveRequest
from app.services.catalog_service import get_expedition_site
from app.services.exploration.expedition import expedition_service
from app.services.exploration_service import exploration_service
from app.services.notification_service import manager, sse_manager
from app.utils.exceptions import ResourceConflictException, ValidationException


def test_pilot_perks_point_to_their_playable_site():
    site = get_expedition_site("research_checkpoint")
    assert site is not None
    assert all(site.name.lower() in perk.description.lower() for perk in PERKS.values())


async def _enter(session, dweller, vault, perk=None):
    dweller.level = 10
    dweller.health = dweller.max_health = 100
    dweller.radiation = dweller.stimpack = dweller.radaway = 0
    dweller.charisma = 10
    dweller.age_group = AgeGroupEnum.ADULT
    dweller.status = DwellerStatusEnum.IDLE
    dweller.is_dead = False
    dweller.selected_perk = perk
    session.add(dweller)
    await session.commit()
    exploration = await exploration_service.send_dweller(session, vault.id, dweller.id, duration=4)
    available = await expedition_service.list_available_sites(session, exploration.id)
    assert "research_checkpoint" in {site.id for site in available}
    view = await expedition_service.enter_run(session, exploration.id, "research_checkpoint")
    return exploration, view


@pytest.mark.parametrize(
    ("perk", "choice", "item_type"),
    [
        (DwellerPerk.HACKER, "hack_terminal", "junk"),
        (DwellerPerk.TERRIFYING_PRESENCE, "intimidate", "weapon"),
        (None, "salvage", "junk"),
        (None, "negotiate", "junk"),
    ],
)
async def test_perk_and_baseline_approaches_settle_once(async_session, dweller, vault, perk, choice, item_type):
    exploration, entered = await _enter(async_session, dweller, vault, perk)
    before_caps = exploration.total_caps_found
    request = ExpeditionResolveRequest(choice_id=choice, choice_context=entered.node.choice_context)
    cleared = await expedition_service.resolve_node(async_session, exploration.id, request)
    await async_session.refresh(exploration)
    assert cleared.status == ExpeditionRunStatus.CLEARED
    assert exploration.total_caps_found > before_caps
    assert exploration.loot_collected[-1]["item_type"] == item_type
    earned_caps = exploration.total_caps_found
    with pytest.raises(ValidationException, match="No open"):
        await expedition_service.resolve_node(async_session, exploration.id, request)
    await async_session.rollback()
    await async_session.refresh(exploration)
    assert exploration.total_caps_found == earned_caps


async def test_locked_choices_are_visible_but_rejected_server_side(async_session, dweller, vault):
    exploration, entered = await _enter(async_session, dweller, vault)
    locked = next(option for option in entered.node.options if option.id == "hack_terminal")
    assert locked.unavailable_reason == "Requires Hacker."
    before_caps = exploration.total_caps_found
    with pytest.raises(ValidationException, match="requires a perk"):
        await expedition_service.resolve_node(
            async_session,
            exploration.id,
            ExpeditionResolveRequest(
                choice_id="hack_terminal",
                choice_context=entered.node.choice_context,
            ),
        )
    await async_session.rollback()
    await async_session.refresh(exploration)
    assert exploration.total_caps_found == before_caps
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run is not None


@pytest.mark.parametrize("context", [None, "an-old-run:checkpoint_locker"])
async def test_stale_or_missing_choice_context_is_rejected(async_session, dweller, vault, context):
    exploration, _ = await _enter(async_session, dweller, vault)
    with pytest.raises(ResourceConflictException):
        await expedition_service.resolve_node(
            async_session,
            exploration.id,
            ExpeditionResolveRequest(
                choice_id="salvage",
                choice_context=context,
            ),
        )


async def test_late_run_write_failure_rolls_back_haul_and_choice(async_session, dweller, vault, monkeypatch):
    websocket, sse = AsyncMock(), AsyncMock()
    monkeypatch.setattr(manager, "send_personal_message", websocket)
    monkeypatch.setattr(sse_manager, "publish", sse)
    exploration, entered = await _enter(async_session, dweller, vault, DwellerPerk.HACKER)
    exploration_id = exploration.id
    before_caps, before_loot, before_events = (
        exploration.total_caps_found,
        list(exploration.loot_collected),
        list(exploration.events),
    )
    connection = (await async_session.connection()).sync_connection

    def fail_run_update(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("UPDATE expeditionrun"):
            raise RuntimeError("late run write failed")

    event.listen(connection, "before_cursor_execute", fail_run_update)
    try:
        with pytest.raises(RuntimeError, match="late run"):
            await expedition_service.resolve_node(
                async_session,
                exploration_id,
                ExpeditionResolveRequest(
                    choice_id="hack_terminal",
                    choice_context=entered.node.choice_context,
                ),
            )
    finally:
        event.remove(connection, "before_cursor_execute", fail_run_update)
    await async_session.rollback()
    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    assert exploration.total_caps_found == before_caps
    assert exploration.loot_collected == before_loot
    assert exploration.events == before_events
    assert dweller.health == 100
    assert await crud.expedition_run.get_open_for_exploration(async_session, exploration_id) is not None
    assert websocket.await_count == sse.await_count == 0
