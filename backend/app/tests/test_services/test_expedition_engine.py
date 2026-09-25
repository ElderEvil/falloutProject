"""Tests for the expedition site resolution engine (SQLite, seeded RNG)."""

import random

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExpeditionRunStatus
from app.schemas.dweller import DwellerCreate
from app.schemas.expedition import EnemySpec, ExpeditionResolveRequest
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.exploration import data_loader
from app.services.exploration.expedition import (
    expedition_service,
    resolve_enemy_spec,
    roll_gear,
    success_odds,
    validate_site_content,
)
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ValidationException


async def _make_exploration(async_session: AsyncSession, level: int = 10):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller_data = create_fake_adult_dweller() | {"level": level, "health": 100, "max_health": 100}
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)),
    )
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    return vault, dweller, exploration


def test_success_odds_boundaries():
    assert success_odds(10, 1) == 0.95
    assert success_odds(1, 5) == pytest.approx(0.15)
    assert 0.05 < success_odds(5, 3) < 0.95


def test_resolve_enemy_spec_inline_boss():
    boss = resolve_enemy_spec(EnemySpec(name="Raider Boss", difficulty=4, min_damage=25, max_damage=45))
    assert boss.name == "Raider Boss"
    assert boss.min_damage == 25


def test_resolve_enemy_spec_table_lookup():
    enemy = resolve_enemy_spec(EnemySpec(name="Mole Rat pack"))
    assert enemy.difficulty == 2


def test_resolve_enemy_spec_unknown_raises():
    with pytest.raises(ValidationException, match="Unknown expedition enemy"):
        resolve_enemy_spec(EnemySpec(name="No Such Thing"))


def test_site_content_validates():
    for site in data_loader.load_expedition_sites():
        validate_site_content(site)


def test_roll_gear_respects_floor():
    random.seed(7)
    item = roll_gear(1, "weapon", "rare", attempts=5)
    assert item.rarity.lower() in ("rare", "legendary")


@pytest.mark.asyncio
async def test_enter_unknown_site_rejected(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    with pytest.raises(ValidationException, match="Unknown expedition site"):
        await expedition_service.enter_run(async_session, exploration.id, "no_such_site")


@pytest.mark.asyncio
async def test_enter_level_gate(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session, level=1)
    with pytest.raises(ValidationException, match="needs dweller level"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_enter_twice_conflicts(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    with pytest.raises(ResourceConflictException, match="already has an open expedition run"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_enter_after_recent_clear_conflicts(async_session: AsyncSession):
    from datetime import datetime

    vault, dweller, exploration = await _make_exploration(async_session)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
    )
    run.status = ExpeditionRunStatus.CLEARED
    run.cleared_at = datetime.utcnow()
    async_session.add(run)
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="quiet"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_full_red_rocket_clear(async_session: AsyncSession):
    random.seed(42)
    _, _, exploration = await _make_exploration(async_session)
    view = await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    assert view.site_id == "red_rocket"
    assert view.room_total == 3
    assert view.node.kind == "trap"
    assert view.can_retreat is True

    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm")
    )
    assert view.room_index == 1
    assert view.node.kind == "combat"
    assert view.outcome is not None

    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.room_index == 2
    assert view.node.kind == "finale"

    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.status == "cleared"
    assert view.finale_paid is True
    assert view.outcome is not None
    assert view.outcome.caps_gained > 0
    assert view.can_retreat is False

    refreshed = await crud.exploration.get(async_session, exploration.id)
    assert refreshed.total_caps_found > 0
    assert refreshed.loot_collected


@pytest.mark.asyncio
async def test_resolve_requires_choice_id(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    with pytest.raises(ValidationException, match="needs a choice"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    with pytest.raises(ValidationException, match="Unknown choice"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest(choice_id="nope"))


@pytest.mark.asyncio
async def test_retreat_keeps_run_closed(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    view = await expedition_service.retreat_run(async_session, exploration.id)
    assert view.status == "retreated"
    with pytest.raises(ValidationException, match="No open expedition run"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())


@pytest.mark.asyncio
async def test_combat_death_ends_run(async_session: AsyncSession):
    random.seed(1)
    _, dweller, exploration = await _make_exploration(async_session)
    await crud.dweller.update(async_session, dweller.id, {"health": 1}, commit=True)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="tank")
    )
    assert view.status == "died"
    assert view.outcome is not None
    assert "died" in view.outcome.text


@pytest.mark.asyncio
async def test_current_view_none_without_run(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    assert await expedition_service.current_view(async_session, exploration.id) is None


@pytest.mark.asyncio
async def test_mart_trade_without_caps_falls_back(async_session: AsyncSession):
    random.seed(3)
    _, _, exploration = await _make_exploration(async_session, level=10)
    await expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="call_out")
    )
    assert view.room_index == 2
    assert view.outcome is not None
