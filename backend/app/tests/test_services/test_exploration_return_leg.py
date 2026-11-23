from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, ExplorationStatus
from app.crud.team import team_crud
from app.models.dweller import Dweller
from app.models.team import Team, TeamMember
from app.models.vault import Vault
from app.services.dweller_service import dweller_service
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.utils.exceptions import ValidationException
from app.utils.time import utcnow


async def _expired_exploration(async_session: AsyncSession, vault: Vault, dweller: Dweller, duration: int = 4):
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=duration)
    exploration.start_time = utcnow() - timedelta(hours=duration)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


async def _home(async_session: AsyncSession, exploration) -> None:
    """The return leg has already elapsed."""
    exploration.return_completes_at = utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()


async def test_return_leg_lasts_half_the_exploring_time_and_locks_the_run(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await _expired_exploration(async_session, vault, dweller, duration=4)
    exploration.add_loot(item_name="Desk Fan", quantity=1, rarity="Common", item_type="junk")
    async_session.add(exploration)
    await async_session.commit()
    returned = await exploration_coordinator.start_return(async_session, exploration.id)
    assert returned.status == ExplorationStatus.RETURNING
    assert returned.return_started_at is not None
    assert returned.return_completes_at is not None
    assert returned.recalled_early is False
    return_seconds = (returned.return_completes_at - returned.return_started_at).total_seconds()
    assert return_seconds == 2 * 3600
    # Loot is not collectable until arrival.
    assert await rewards_service.get_pending_overflow(async_session, vault.id) == []
    with pytest.raises(ValidationException, match="still in progress"):
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)
    # A racing recall must not overwrite the natural finish's timestamps or flag.
    with pytest.raises(ValueError, match="not active"):
        await exploration_coordinator.start_return(async_session, exploration.id, recalled=True)
    await async_session.refresh(exploration)
    assert exploration.recalled_early is False
    assert exploration.return_completes_at == returned.return_completes_at
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.EXPLORING
    with pytest.raises(ValueError, match="already on an exploration"):
        await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=2)


async def test_recall_return_leg_is_half_the_elapsed_time(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=10)
    exploration.start_time = utcnow() - timedelta(hours=2)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    returned = await exploration_coordinator.start_return(async_session, exploration.id, recalled=True)
    assert returned.status == ExplorationStatus.RETURNING
    assert returned.recalled_early is True
    return_seconds = (returned.return_completes_at - returned.return_started_at).total_seconds()
    assert return_seconds == 1 * 3600


def _spy_lock_order(monkeypatch) -> list[str]:
    """Record the order of vault-claim and exploration-lock acquisitions."""
    order: list[str] = []
    real_vault = crud.vault.get_for_update
    real_exploration = crud.exploration.get_for_update

    async def spy_vault(*args, **kwargs):
        order.append("vault")
        return await real_vault(*args, **kwargs)

    async def spy_exploration(*args, **kwargs):
        order.append("exploration")
        return await real_exploration(*args, **kwargs)

    monkeypatch.setattr(crud.vault, "get_for_update", spy_vault)
    monkeypatch.setattr(crud.exploration, "get_for_update", spy_exploration)
    return order


async def test_finalize_return_restores_dweller_and_claims_vault_first(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch
) -> None:
    # Reward settlement takes the vault claim before the exploration lock, matching site actions.
    exploration = await _expired_exploration(async_session, vault, dweller)
    await exploration_coordinator.start_return(async_session, exploration.id)
    await _home(async_session, exploration)
    order = _spy_lock_order(monkeypatch)
    await exploration_coordinator.finalize_return(async_session, exploration.id)
    assert order[0] == "vault"
    assert order[1] == "exploration"
    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert exploration.end_time is not None
    assert dweller.status == DwellerStatusEnum.IDLE


async def test_tick_claims_vault_before_reading_the_run_then_finalizes(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch
) -> None:
    # The tick re-reads under the shared claim before its open-run check, then sends the dweller home.
    exploration = await _expired_exploration(async_session, vault, dweller, duration=1)
    order = _spy_lock_order(monkeypatch)
    first = await process_explorations(async_session, vault.id)
    assert order[0] == "vault"
    assert order[1] == "exploration"
    assert first["returning"] == 1
    assert first["completed"] == 0
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.RETURNING
    await _home(async_session, exploration)
    second = await process_explorations(async_session, vault.id)
    assert second["completed"] == 1
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.COMPLETED


async def test_finalize_return_rolls_back_terminal_transition_when_rewards_fail(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # A reward failure must leave the run RETURNING so the next tick retries it.
    exploration = await _expired_exploration(async_session, vault, dweller)
    await exploration_coordinator.start_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    exploration.total_caps_found = 250
    vault.bottle_caps = 0
    async_session.add_all([exploration, vault])
    await async_session.commit()
    await _home(async_session, exploration)
    with (
        patch.object(
            rewards_service,
            "apply_rewards",
            new_callable=AsyncMock,
            side_effect=RuntimeError("reward settlement exploded"),
        ),
        pytest.raises(RuntimeError, match="reward settlement exploded"),
    ):
        await exploration_coordinator.finalize_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.RETURNING
    assert dweller.status == DwellerStatusEnum.EXPLORING
    await exploration_coordinator.finalize_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(vault)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert vault.bottle_caps == 250


async def test_party_finalize_grants_xp_when_caps_are_deposited(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # Depositing party caps flushes the session, so the roster must survive until XP is granted.
    partner = await dweller_service.create_random_dweller(async_session, vault.id, register_bio_places=False)
    exploration = await _expired_exploration(async_session, vault, dweller)
    team = Team(vault_id=vault.id, exploration_id=exploration.id)
    async_session.add(team)
    await async_session.flush()
    async_session.add_all(
        [
            TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"),
            TeamMember(team_id=team.id, dweller_id=partner.id, slot_number=2, status="assigned"),
        ]
    )
    exploration.team_id = team.id
    exploration.total_caps_found = 250
    exploration.total_distance = 10
    vault.bottle_caps = 0
    async_session.add_all([exploration, vault])
    await async_session.commit()
    await exploration_coordinator.start_return(async_session, exploration.id)
    await _home(async_session, exploration)
    before = {dweller.id: dweller.experience, partner.id: partner.experience}
    await exploration_coordinator.finalize_return(async_session, exploration.id)
    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    await async_session.refresh(vault)
    assert dweller.experience > before[dweller.id]
    assert partner.experience > before[partner.id]
    assert vault.bottle_caps == 250
    assert await team_crud.get_exploration_team(async_session, exploration.id) is None
