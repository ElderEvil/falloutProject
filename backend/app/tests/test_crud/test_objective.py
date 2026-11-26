from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import ObjectiveCategoryEnum
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.objective import ObjectiveCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.progression.objectives.assignment import ObjectiveAssignmentService
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


async def _user_vault(async_session: AsyncSession):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


def _obj(challenge: str, reward: str = "50 caps", **kw) -> ObjectiveCreate:
    base = {"challenge": challenge, "reward": reward, "category": ObjectiveCategoryEnum.ACHIEVEMENT}
    return ObjectiveCreate(**(base | kw))


async def _assign(async_session, vault, obj):
    return await crud.objective_crud.create_for_vault(db_session=async_session, vault_id=vault.id, obj_in=obj)


async def _progress(async_session, vault, objective, progress):
    return await reward_service.settle_objective_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=progress
    )


async def _complete(async_session, vault, objective):
    return await reward_service.settle_objective_completion(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id
    )


async def _assigned(async_session, vault):
    return await crud.objective_crud.get_multi_for_vault(db_session=async_session, vault_id=vault.id, skip=0, limit=100)


async def test_count_claimable_for_vault(async_session: AsyncSession) -> None:
    vault = await _user_vault(async_session)
    ready = await _assign(async_session, vault, _obj("Collect 10 weapons", target_amount=10))
    incomplete = await _assign(async_session, vault, _obj("Collect 20 weapons", target_amount=20))
    await _assign(async_session, vault, _obj("Collect 30 weapons", target_amount=30))
    await _progress(async_session, vault, ready, 10)
    await _progress(async_session, vault, incomplete, 2)

    assert await crud.objective_crud.count_claimable_for_vault(async_session, vault.id) == 1


# Progress is recorded but never paid; completion settles the reward. Both must work with a link
# created up front and with one created lazily by the first write.
@pytest.mark.parametrize("settle", ["progress", "complete"])
@pytest.mark.parametrize("linked", [True, False], ids=["with-link", "without-link"])
async def test_objective_settlement_creates_the_missing_link(
    async_session: AsyncSession, settle: str, linked: bool
) -> None:
    vault = await _user_vault(async_session)
    objective = await (
        _assign(async_session, vault, _obj("Collect 10 weapons", "500 caps"))
        if linked
        else crud.objective_crud.create(async_session, obj_in=_obj("Collect 10 weapons", "500 caps"))
    )
    initial_caps = vault.bottle_caps

    if settle == "progress":
        link = await _progress(async_session, vault, objective, 5)
        assert (link.vault_id, link.objective_id, link.progress) == (vault.id, objective.id, 5)
        assert link.is_completed is False
        await async_session.refresh(vault)
        assert vault.bottle_caps == initial_caps
    else:
        completed_objective = await _complete(async_session, vault, objective)
        assert completed_objective.id == objective.id
        await async_session.refresh(vault)
        assert vault.bottle_caps == initial_caps + 500
        objectives = await _assigned(async_session, vault)
        assert [(row.challenge, row.is_completed) for row in objectives] == [("Collect 10 weapons", True)]


async def test_assign_initial_objectives(async_session: AsyncSession) -> None:
    vault = await _user_vault(async_session)
    for category in (ObjectiveCategoryEnum.DAILY, ObjectiveCategoryEnum.WEEKLY, ObjectiveCategoryEnum.ACHIEVEMENT):
        await crud.objective_crud.create(
            async_session,
            obj_in=_obj(f"Starter {category.value}", "10 caps", category=category, objective_type="collect"),
        )

    assigned_count = await crud.objective_crud.assign_initial(async_session, vault.id, is_boosted=True)
    assigned = await _assigned(async_session, vault)

    assert assigned_count == 3
    assert {objective.category for objective in assigned} == {
        ObjectiveCategoryEnum.DAILY,
        ObjectiveCategoryEnum.WEEKLY,
        ObjectiveCategoryEnum.ACHIEVEMENT,
    }


async def test_vault_read_exposes_template_key(async_session: AsyncSession) -> None:
    vault = await _user_vault(async_session)
    await crud.objective_crud.create(
        async_session,
        obj_in=_obj(
            "Match a dweller to their room",
            category=ObjectiveCategoryEnum.STARTER,
            objective_type="assign_correct",
            target_entity={},
            target_amount=1,
            sequence=0,
            description="Match a dweller's best SPECIAL to the room.",
            template_key="starter:assign a dweller correctly",
        ),
    )

    await crud.objective_crud.assign_initial(async_session, vault.id, is_boosted=False)
    read = await _assigned(async_session, vault)

    assert {objective.template_key for objective in read} == {"starter:assign a dweller correctly"}


@pytest.mark.parametrize(("boosted", "expected_count"), [(False, 8), (True, 0)], ids=["standard", "boosted"])
async def test_assign_initial_starter_arc(async_session: AsyncSession, boosted: bool, expected_count: int) -> None:
    vault = await _user_vault(async_session)
    for sequence in range(8):
        await crud.objective_crud.create(
            async_session,
            obj_in=_obj(
                f"Starter step {sequence}",
                "10 caps",
                category=ObjectiveCategoryEnum.STARTER,
                objective_type="collect",
                target_entity={"resource_type": "caps"},
                target_amount=1,
                sequence=sequence,
                description=f"Step {sequence}",
            ),
        )

    assigned_count = await crud.objective_crud.assign_initial(async_session, vault.id, is_boosted=boosted)
    assigned = await _assigned(async_session, vault)
    starter = [o for o in assigned if o.category == ObjectiveCategoryEnum.STARTER]

    assert assigned_count == expected_count
    if boosted:
        assert all(o.category != ObjectiveCategoryEnum.STARTER for o in assigned)
        return
    assert len(starter) == 8
    assert sorted(o.sequence for o in starter) == list(range(8))
    assert all(o.description is not None for o in starter)


async def test_assign_initial_rolls_back_on_db_error() -> None:
    db_session = AsyncMock()
    db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB down"))

    assigned = await crud.objective_crud.assign_initial(db_session, uuid4(), is_boosted=False)

    assert assigned == 0
    db_session.rollback.assert_awaited_once()


async def test_completed_link_progress_not_mutated(async_session: AsyncSession) -> None:
    vault = await _user_vault(async_session)
    objective = await crud.objective_crud.create(async_session, obj_in=_obj("Collect 10 weapons", "500 caps"))

    link = await _progress(async_session, vault, objective, 5)
    await reward_service.claim_objective_reward(async_session, objective.id, vault.id)
    assert link.is_completed is True
    assert link.progress == 5
    relink = await _progress(async_session, vault, objective, 1)
    assert relink.progress == 5
    assert relink.is_completed is True


async def test_reset_reads_latest_progress_even_when_link_is_cached(async_session, vault):
    # A reset must re-read earned progress rather than delete a stale unfinished row.
    objective = Objective(challenge="Earn one", reward="50 caps", category="daily")
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, total=1)
    async_session.add_all([objective, link])
    await async_session.commit()
    await async_session.execute(
        update(VaultObjectiveProgressLink)
        .where(VaultObjectiveProgressLink.objective_id == objective.id)
        .values(progress=1)
        .execution_options(synchronize_session=False)
    )
    await async_session.commit()
    assert link.progress == 0  # Identity map is deliberately stale.
    assert await ObjectiveAssignmentService(async_session).clear_daily_objectives(vault.id) == 0
    await async_session.refresh(link)
    assert link.progress == 1
    assert not link.is_completed
