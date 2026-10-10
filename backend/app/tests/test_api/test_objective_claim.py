"""Player objective claims must validate progress, assignment and ownership."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api.deps import get_current_active_user
from app.models.objective import Objective
from app.models.user import User
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.user import UserCreate
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from main import app


@pytest.mark.parametrize("progress", [0, 2])
async def test_owner_claims_only_ready_rewards(
    async_client: AsyncClient, async_session: AsyncSession, user: User, vault: Vault, progress: int
) -> None:
    objective = Objective(
        challenge="Collect two caps",
        reward="50 caps",
        category="daily",
        target_amount=2,
        objective_type="collect",
        target_entity={"resource_type": "caps"},
    )
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, progress=progress, total=2)
    async_session.add_all([objective, link])
    await async_session.commit()
    initial_caps = vault.bottle_caps
    app.dependency_overrides[get_current_active_user] = lambda: user
    try:
        response = await async_client.post(f"/objectives/{vault.id}/{objective.id}/claim")
        assert response.status_code == (200 if progress == 2 else 400), response.text
        await async_session.refresh(vault)
        await async_session.refresh(link)
        assert vault.bottle_caps == initial_caps + (50 if progress == 2 else 0)
        assert link.is_completed == (progress == 2)
        if progress == 2:
            assert response.json()["is_completed"] is True
            repeat = await async_client.post(f"/objectives/{vault.id}/{objective.id}/claim")
            assert repeat.status_code == 409
            await async_session.refresh(vault)
            assert vault.bottle_caps == initial_caps + 50
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


async def test_objective_claim_rejects_foreign_vault_and_unassigned_objective(
    async_client: AsyncClient, async_session: AsyncSession, user: User, vault: Vault
) -> None:
    foreign_user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    app.dependency_overrides[get_current_active_user] = lambda: foreign_user
    try:
        response = await async_client.post(f"/objectives/{vault.id}/{uuid4()}/claim")
        assert response.status_code == 403
        app.dependency_overrides[get_current_active_user] = lambda: user
        response = await async_client.post(f"/objectives/{vault.id}/{uuid4()}/claim")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


async def test_current_guided_state_is_claimable_without_repeating_past_actions(
    async_client: AsyncClient, async_session: AsyncSession, user: User, vault: Vault, dweller
) -> None:
    """Already-met population milestones count, but future tutorial steps cannot be claimed early."""
    objectives = [
        Objective(
            challenge=f"Population step {sequence}",
            reward="50 caps",
            category="starter",
            sequence=sequence,
            objective_type="reach",
            target_entity={"reach_type": "dweller_count"},
            target_amount=1,
        )
        for sequence in range(2)
    ]
    links = [
        VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, total=1) for objective in objectives
    ]
    async_session.add_all([*objectives, *links])
    await async_session.commit()
    app.dependency_overrides[get_current_active_user] = lambda: user
    try:
        listed = await async_client.get(f"/objectives/{vault.id}/")
        current = next(item for item in listed.json() if item["id"] == str(objectives[0].id))
        assert current["progress"] == 1
        await async_session.refresh(links[0])
        assert links[0].progress == 0  # GET does not write.
        future = await async_client.post(f"/objectives/{vault.id}/{objectives[1].id}/claim")
        assert future.status_code == 400
        current_claim = await async_client.post(f"/objectives/{vault.id}/{objectives[0].id}/claim")
        assert current_claim.status_code == 200, current_claim.text
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


async def test_failed_claim_rolls_back_reward_and_keeps_objective_claimable(
    async_client: AsyncClient, async_session: AsyncSession, user: User, vault: Vault
) -> None:
    objective = Objective(challenge="Earn a cap", reward="50 caps", category="daily")
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, progress=1, total=1)
    async_session.add_all([objective, link])
    await async_session.commit()
    initial_caps = vault.bottle_caps
    vault_id, objective_id = vault.id, objective.id

    async def fail_after_credit(db_session, target_vault_id, _link):
        await reward_service.grant_caps(db_session, target_vault_id, 50)
        raise RuntimeError("reward delivery failed")

    app.dependency_overrides[get_current_active_user] = lambda: user
    try:
        with (
            patch.object(reward_service, "process_objective_reward", side_effect=fail_after_credit),
            pytest.raises(RuntimeError, match="reward delivery failed"),
        ):
            await async_client.post(f"/objectives/{vault_id}/{objective_id}/claim")
        await async_session.refresh(vault)
        await async_session.refresh(link)
        assert vault.bottle_caps == initial_caps
        assert link.is_completed is False
        assert link.progress == 1
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
