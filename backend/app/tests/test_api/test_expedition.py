"""API tests for expedition site endpoints."""

import random
from datetime import datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExpeditionRunStatus, Exploration
from app.models.vault import Vault
from app.schemas.expedition import TriviaQuestion
from app.services import catalog_service as data_loader
from app.services.exploration_service import exploration_service


async def _enter_raider_tollbooth(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> tuple[Exploration, TriviaQuestion, Response]:
    """Enter the trivia site and return the run's pinned question, not the served answer key."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    entered = await async_client.post(
        f"/explorations/{exploration.id}/site/enter",
        json={"site_id": "raider_tollbooth"},
        headers=superuser_token_headers,
    )
    assert entered.status_code == 200
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    question_id = next(iter(run.flags["trivia_questions"].values()))
    site = data_loader.get_expedition_site("raider_tollbooth")
    question = next(q for q in site.encounter.node.trivia_questions if q.id == question_id)
    return exploration, question, entered


@pytest.mark.asyncio
async def test_site_enter_and_current(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Enter Red Rocket, then fetch the open run via the reconnect endpoint."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    enter = await async_client.post(
        f"/explorations/{exploration.id}/site/enter",
        json={"site_id": "red_rocket"},
        headers=superuser_token_headers,
    )
    assert enter.status_code == 200
    body = enter.json()
    assert body["site_id"] == "red_rocket"
    assert body["room_index"] == 0
    assert body["room_names"] == ["Forecourt", "Garage", "Bunker Cache"]
    assert body["node"]["kind"] == "trap"
    assert body["can_retreat"] is True

    current = await async_client.get(
        f"/explorations/{exploration.id}/site",
        headers=superuser_token_headers,
    )
    assert current.status_code == 200
    assert current.json()["site_id"] == "red_rocket"


@pytest.mark.asyncio
async def test_site_enter_unknown_site_rejected(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Unknown site ids fail with 400."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    response = await async_client.post(
        f"/explorations/{exploration.id}/site/enter",
        json={"site_id": "no_such_site"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_site_resolve_and_retreat(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Resolve the forecourt choice, then retreat from the garage."""
    random.seed(11)
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await async_client.post(
        f"/explorations/{exploration.id}/site/enter",
        json={"site_id": "red_rocket"},
        headers=superuser_token_headers,
    )

    resolved = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={"choice_id": "detour"},
        headers=superuser_token_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["room_index"] == 1

    retreated = await async_client.post(
        f"/explorations/{exploration.id}/site/retreat",
        headers=superuser_token_headers,
    )
    assert retreated.status_code == 200
    body = retreated.json()
    assert body["status"] == "retreated"
    assert body["can_retreat"] is False

    current = await async_client.get(
        f"/explorations/{exploration.id}/site",
        headers=superuser_token_headers,
    )
    assert current.status_code == 200
    assert current.json() is None


@pytest.mark.asyncio
async def test_site_resolve_without_choice_rejected(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Resolving a choice node without choice_id fails with 400."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await async_client.post(
        f"/explorations/{exploration.id}/site/enter",
        json={"site_id": "red_rocket"},
        headers=superuser_token_headers,
    )

    response = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_site_available_lists_all_sites(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A level-appropriate dweller sees every site with its room count and level gate."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    response = await async_client.get(
        f"/explorations/{exploration.id}/site/available",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    sites = {site["id"]: site for site in response.json()}
    assert set(sites) == {
        "red_rocket",
        "super_duper_mart",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
        "gloomwater_bog",
        "gloomwater_bog_night",
        "outskirts_interchange",
    }
    assert sites["red_rocket"]["min_dweller_level"] == 3
    assert sites["red_rocket"]["room_total"] == 3
    assert sites["super_duper_mart"]["min_dweller_level"] == 5
    assert sites["super_duper_mart"]["room_total"] == 4


@pytest.mark.asyncio
async def test_site_available_level_gate_excludes_sites(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A level-4 dweller keeps red_rocket (min 3) but loses super_duper_mart (min 5)."""
    await crud.dweller.update(async_session, dweller.id, {"level": 4}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    response = await async_client.get(
        f"/explorations/{exploration.id}/site/available",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    site_ids = [site["id"] for site in response.json()]
    assert site_ids == [
        "red_rocket",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
        "gloomwater_bog",
        "gloomwater_bog_night",
        "outskirts_interchange",
    ]


@pytest.mark.asyncio
async def test_site_available_anti_farm_excludes_recent_clear(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A recently cleared site is hidden from the available list."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        site_id="red_rocket",
    )
    run.status = ExpeditionRunStatus.CLEARED
    run.finished_at = datetime.utcnow()
    async_session.add(run)
    await async_session.commit()

    response = await async_client.get(
        f"/explorations/{exploration.id}/site/available",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    site_ids = [site["id"] for site in response.json()]
    assert site_ids == [
        "super_duper_mart",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
        "collapsed_subway",
        "rusted_midway",
        "frozen_research_outpost",
        "raider_tollbooth",
        "gloomwater_bog",
        "gloomwater_bog_night",
        "outskirts_interchange",
    ]


@pytest.mark.asyncio
async def test_site_available_missing_exploration_404(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Unknown exploration ids fail with 404."""
    response = await async_client.get(
        f"/explorations/{uuid4()}/site/available",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_site_trivia_enter_hides_answer_key(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Entering the raider tollbooth serves the question and options without the answer key."""
    _, _, entered = await _enter_raider_tollbooth(async_client, superuser_token_headers, async_session, vault, dweller)
    body = entered.json()
    assert body["node"]["kind"] == "trivia"
    assert body["node"]["question"]
    assert body["node"]["options"]
    assert body["combat_state"] is None
    assert "correct_option_id" not in entered.text
    assert all(
        option["stat"] is None and option["difficulty"] is None and option["success_odds"] is None
        for option in body["node"]["options"]
    )


@pytest.mark.asyncio
async def test_site_trivia_correct_answer_pays_once(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A correct answer clears the site and pays once; resubmitting it fails without paying again."""
    exploration, question, _ = await _enter_raider_tollbooth(
        async_client, superuser_token_headers, async_session, vault, dweller
    )
    before = (await crud.exploration.get(async_session, exploration.id)).total_caps_found

    resolved = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={"choice_id": question.correct_option_id},
        headers=superuser_token_headers,
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "cleared"
    assert body["finale_paid"] is True
    assert body["outcome"]["caps_gained"] >= 40
    assert body["node"]["options"] == []

    after = (await crud.exploration.get(async_session, exploration.id)).total_caps_found
    assert after > before

    duplicate = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={"choice_id": question.correct_option_id},
        headers=superuser_token_headers,
    )
    assert duplicate.status_code == 400
    assert (await crud.exploration.get(async_session, exploration.id)).total_caps_found == after


@pytest.mark.asyncio
async def test_site_trivia_invalid_answer_rejected(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """An unknown answer id is rejected and leaves the pinned encounter untouched."""
    exploration, _, _ = await _enter_raider_tollbooth(
        async_client, superuser_token_headers, async_session, vault, dweller
    )
    before_run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    before_questions = dict(before_run.flags["trivia_questions"])

    response = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={"choice_id": "not-an-option"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400

    run_after = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run_after is not None
    assert run_after.status == ExpeditionRunStatus.IN_ROOM
    assert "combat" not in run_after.flags
    assert run_after.flags["trivia_questions"] == before_questions


@pytest.mark.asyncio
async def test_site_trivia_wrong_answer_starts_combat(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A wrong answer arms a playable fight; the fight rejects another answer id."""
    random.seed(11)
    exploration, question, _ = await _enter_raider_tollbooth(
        async_client, superuser_token_headers, async_session, vault, dweller
    )
    wrong_id = next(option.id for option in question.options if option.id != question.correct_option_id)

    resolved = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={"choice_id": wrong_id},
        headers=superuser_token_headers,
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "in_room"
    assert body["combat_state"] is not None
    assert body["node"]["options"] == []
    assert "Wrong answer" in body["outcome"]["text"]

    run_after = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run_after is not None
    assert run_after.flags["combat"]

    strike = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={},
        headers=superuser_token_headers,
    )
    assert strike.status_code == 200
    strike_body = strike.json()
    assert strike_body["status"] == "in_room"
    assert strike_body["combat_state"] is not None

    rejected = await async_client.post(
        f"/explorations/{exploration.id}/site/resolve",
        json={"choice_id": wrong_id},
        headers=superuser_token_headers,
    )
    assert rejected.status_code == 400
