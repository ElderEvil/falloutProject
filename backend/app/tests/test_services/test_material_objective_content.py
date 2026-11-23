from unittest.mock import patch

from app.core.enums import ObjectiveCategoryEnum
from app.crud.objective import objective_crud
from app.services.progression.objectives.assignment import ObjectiveAssignmentService
from app.utils.seed_objectives import seed_objectives_from_json

MATERIAL = {"weekly:salvage 6 adhesive", "weekly:recover 4 circuitry"}


async def test_material_weeklies_seed_idempotently_and_are_selectable(async_session, vault):
    for _ in range(2):
        await seed_objectives_from_json(async_session)
    pool = await objective_crud.get_by_category(async_session, ObjectiveCategoryEnum.WEEKLY)
    keys = [o.template_key for o in pool if o.template_key in MATERIAL]
    assert sorted(keys) == sorted(MATERIAL)

    material_ids = {o.id for o in pool if o.template_key in MATERIAL}
    assert len(material_ids) == 2

    def pick_material(population: list, _count: int) -> list:
        return [o for o in population if o.id in material_ids]

    with patch("app.services.progression.objectives.assignment.random.sample", side_effect=pick_material):
        assigned = await ObjectiveAssignmentService(async_session).refresh_weekly_objectives(vault.id)

    assert {o.template_key for o in assigned} == MATERIAL
