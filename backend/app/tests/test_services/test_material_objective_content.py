"""Material objectives: seeding idempotency and weekly-pool eligibility."""

from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.crud.objective import objective_crud
from app.models.vault import Vault
from app.services.progression.objectives.assignment import ObjectiveAssignmentService
from app.utils.seed_objectives import seed_objectives_from_json

MATERIAL_TEMPLATES = {"weekly:salvage 6 adhesive", "weekly:recover 4 circuitry"}


@pytest.mark.asyncio
async def test_seeding_material_weeklies_twice_creates_no_duplicates(async_session: AsyncSession) -> None:
    """Re-running the seed upserts by template_key instead of adding a second row."""
    await seed_objectives_from_json(async_session)
    await seed_objectives_from_json(async_session)

    weekly = await objective_crud.get_by_category(async_session, ObjectiveCategoryEnum.WEEKLY)
    keys = [objective.template_key for objective in weekly if objective.template_key in MATERIAL_TEMPLATES]

    assert sorted(keys) == sorted(MATERIAL_TEMPLATES)


@pytest.mark.asyncio
async def test_material_weeklies_are_selectable_on_the_next_reset(async_session: AsyncSession, vault: Vault) -> None:
    """Both templates are in the weekly pool the reset samples from, and assignment accepts them."""
    await seed_objectives_from_json(async_session)
    pool = await objective_crud.get_by_category(async_session, ObjectiveCategoryEnum.WEEKLY)
    material_ids = {objective.id for objective in pool if objective.template_key in MATERIAL_TEMPLATES}
    assert len(material_ids) == 2

    def pick_material(population: list, _count: int) -> list:
        return [objective for objective in population if objective.id in material_ids]

    service = ObjectiveAssignmentService(async_session)
    with patch("app.services.progression.objectives.assignment.random.sample", side_effect=pick_material):
        assigned = await service.refresh_weekly_objectives(vault.id)

    assert {objective.template_key for objective in assigned} == MATERIAL_TEMPLATES
