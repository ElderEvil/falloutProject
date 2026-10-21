"""API tests for expedition site endpoints."""

import json
import random
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExpeditionRunStatus
from app.models.vault import Vault
from app.services.exploration_service import exploration_service


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
async def test_vault_site_opportunities_reports_open_run(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """An open run suppresses the card count instead of advertising sites mid-run."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    enter = await async_client.post(
        f"/explorations/{exploration.id}/site/enter",
        json={"site_id": "red_rocket"},
        headers=superuser_token_headers,
    )
    assert enter.status_code == 200

    response = await async_client.get(
        f"/explorations/vault/{vault.id}/site/opportunities",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json() == [{"exploration_id": str(exploration.id), "sites": [], "reason": "open"}]


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
    body = response.json()
    assert body["reason"] == "available"
    sites = {site["id"]: site for site in body["sites"]}
    assert set(sites) == {
        "red_rocket",
        "super_duper_mart",
        "abandoned_campsite",
        "roadside_supply_truck",
        "forgotten_shack",
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
    site_ids = [site["id"] for site in response.json()["sites"]]
    assert site_ids == ["red_rocket", "abandoned_campsite", "roadside_supply_truck", "forgotten_shack"]


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
    site_ids = [site["id"] for site in response.json()["sites"]]
    assert site_ids == ["super_duper_mart", "abandoned_campsite", "roadside_supply_truck", "forgotten_shack"]


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


@pytest.fixture
def level_gated_site_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services import catalog_service

    red_rocket = next(site for site in catalog_service.load_expedition_sites() if site.id == "red_rocket")
    (tmp_path / "expedition_sites.json").write_text(json.dumps({"sites": [red_rocket.model_dump(mode="json")]}))
    monkeypatch.setattr(catalog_service, "EXPLORATION_DIR", tmp_path)
    catalog_service.load_expedition_sites.cache_clear()
    yield
    catalog_service.load_expedition_sites.cache_clear()


@pytest.mark.asyncio
async def test_site_available_reports_level_reason(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    level_gated_site_catalog,
) -> None:
    """An empty list explains the level gate instead of looking like a missing feature."""
    await crud.dweller.update(async_session, dweller.id, {"level": 1}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    response = await async_client.get(
        f"/explorations/{exploration.id}/site/available",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"sites": [], "reason": "level"}


@pytest.mark.asyncio
async def test_site_available_reports_cooldown_reason(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    level_gated_site_catalog,
) -> None:
    """A legacy journey distinguishes an anti-farm cooldown from a genuinely empty catalog."""
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
    assert response.json() == {"sites": [], "reason": "cooldown"}


@pytest.mark.asyncio
async def test_vault_site_opportunities_lists_active_free_roam(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """The list page gets one availability record per active free-roam journey."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    response = await async_client.get(
        f"/explorations/vault/{vault.id}/site/opportunities",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert [entry["exploration_id"] for entry in body] == [str(exploration.id)]
    assert body[0]["reason"] == "available"
    assert {site["id"] for site in body[0]["sites"]} >= {"red_rocket", "super_duper_mart"}


@pytest.mark.asyncio
async def test_vault_site_opportunities_skips_soft_deleted_dweller(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A supported dweller soft delete must not fail the vault opportunity list."""
    await crud.dweller.update(async_session, dweller.id, {"level": 10}, commit=True)
    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await crud.dweller.soft_delete(async_session, dweller.id)

    response = await async_client.get(
        f"/explorations/vault/{vault.id}/site/opportunities",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json() == []
