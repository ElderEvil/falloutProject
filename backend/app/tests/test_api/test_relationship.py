from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.models.relationship import Relationship
from app.schemas.dweller import DwellerCreateCommonOverride
from app.schemas.relationship import VaultRelationshipRead
from app.services.dweller_service import dweller_service
from app.services.relationship_service import relationship_service
from app.utils.exceptions import AccessDeniedException, ValidationException

pytestmark = pytest.mark.asyncio(scope="module")

EP = "app.api.v1.endpoints.relationship."


async def _vault(async_session, number):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    assert user is not None
    return await crud.vault.create_with_user_id(
        db_session=async_session, obj_in={"number": number, "population_max": 50}, user_id=user.id
    )


async def _dwellers(async_session, vault):
    return [
        await dweller_service.create_random_dweller(
            async_session,
            vault.id,
            obj_in=DwellerCreateCommonOverride(gender=gender, visual_attributes={"race": "human"}),
        )
        for gender in ("male", "female")
    ]


async def _create_acquaintance_relationship(
    async_client, async_session, superuser_token_headers, vault_number: int
) -> str:
    """Create a vault, two dwellers and a fresh acquaintance relationship (affinity 0)."""
    vault = await _vault(async_session, vault_number)
    dweller1, dweller2 = await _dwellers(async_session, vault)
    create_response = await async_client.post(
        "/relationships/",
        headers=superuser_token_headers,
        json={"dweller_1_id": str(dweller1.id), "dweller_2_id": str(dweller2.id)},
    )
    assert create_response.status_code == 200
    return create_response.json()["id"]


def _make_mock_relationship(**overrides: object) -> MagicMock:
    now = datetime.now(UTC)
    attrs: dict[str, object] = {
        "id": overrides.pop("id", uuid4()),
        "dweller_1_id": overrides.pop("dweller_1_id", uuid4()),
        "dweller_2_id": overrides.pop("dweller_2_id", uuid4()),
        "relationship_type": overrides.pop("relationship_type", "acquaintance"),
        "affinity": overrides.pop("affinity", 50),
        "created_at": overrides.pop("created_at", now),
        "updated_at": overrides.pop("updated_at", now),
        **overrides,
    }
    mock = MagicMock()
    for key, value in attrs.items():
        setattr(mock, key, value)
    return mock


async def test_get_vault_relationships_empty(async_client, async_session, superuser_token_headers):
    vault = await _vault(async_session, 899)

    response = await async_client.get(f"/relationships/vault/{vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


async def test_initiate_romance(async_client, async_session, superuser_token_headers):
    vault = await _vault(async_session, 896)
    dweller1, dweller2 = await _dwellers(async_session, vault)

    create_response = await async_client.post(
        "/relationships/",
        headers=superuser_token_headers,
        json={"dweller_1_id": str(dweller1.id), "dweller_2_id": str(dweller2.id)},
    )
    relationship_id = create_response.json()["id"]

    result = await async_session.execute(select(Relationship).where(Relationship.id == UUID(relationship_id)))
    relationship = result.scalar_one()
    relationship.affinity = 75
    await async_session.commit()

    response = await async_client.put(f"/relationships/{relationship_id}/romance", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["relationship_type"] == "romantic"


async def test_get_vault_relationships_includes_bond_progress(async_client, superuser_token_headers):
    vault_id = uuid4()
    relationship = VaultRelationshipRead.model_validate(
        _make_mock_relationship(),
        update={
            "bond_change_per_tick": 3,
            "bond_tick_seconds": 60,
            "conception_potential": "possible",
            "same_race": True,
            "average_charisma": 8,
            "can_make_partners": False,
            "discomfort_severity": None,
            "discomfort_source": None,
        },
    )
    with (
        patch(f"{EP}get_user_vault_or_403", AsyncMock()),
        patch(
            f"{EP}relationship_service.get_vault_relationships_with_progress", AsyncMock(return_value=[relationship])
        ),
    ):
        response = await async_client.get(f"/relationships/vault/{vault_id}", headers=superuser_token_headers)

    assert response.status_code == 200
    item = response.json()[0]
    assert item["bond_change_per_tick"] == 3
    assert item["bond_tick_seconds"] == 60
    assert item["conception_potential"] == "possible"
    assert item["same_race"] is True
    assert item["average_charisma"] == 8
    assert item["discomfort_severity"] is None
    assert item["discomfort_source"] is None
    assert item["can_make_partners"] is False


async def test_get_relationship_access_denied(async_client, superuser_token_headers):
    mock_rel = _make_mock_relationship()
    with (
        patch(f"{EP}relationship_crud.get", AsyncMock(return_value=mock_rel)),
        patch(
            f"{EP}verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.get(f"/relationships/{mock_rel.id}", headers=superuser_token_headers)
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "suffix"), [("put", "romance"), ("put", "partner"), ("delete", ""), ("put", "marry")]
)
async def test_relationship_actions_not_found(async_client, superuser_token_headers, method, suffix):
    fake_id = uuid4()
    url = f"/relationships/{fake_id}" + (f"/{suffix}" if suffix else "")
    with patch(f"{EP}relationship_crud.get", AsyncMock(return_value=None)):
        response = await getattr(async_client, method)(url, headers=superuser_token_headers)
    assert response.status_code == 404
    assert "Relationship not found" in response.json()["detail"]


@pytest.mark.parametrize(
    ("suffix", "vault_number", "detail"),
    [("romance", 893, "Affinity too low for romance"), ("partner", 894, "Affinity too low for partnership")],
)
async def test_low_affinity_rejected(
    async_client, async_session, superuser_token_headers, suffix, vault_number, detail
):
    relationship_id = await _create_acquaintance_relationship(
        async_client, async_session, superuser_token_headers, vault_number=vault_number
    )

    response = await async_client.put(f"/relationships/{relationship_id}/{suffix}", headers=superuser_token_headers)
    assert response.status_code == 400
    assert detail in response.json()["detail"]


async def test_break_up_acquaintance_succeeds(async_client, async_session, superuser_token_headers):
    relationship_id = await _create_acquaintance_relationship(
        async_client, async_session, superuser_token_headers, vault_number=895
    )

    response = await async_client.delete(f"/relationships/{relationship_id}", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Relationship ended"

    get_response = await async_client.get(f"/relationships/{relationship_id}", headers=superuser_token_headers)
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["relationship_type"] == "ex"
    assert data["affinity"] == 0


async def test_marry(async_client, async_session, superuser_token_headers):
    vault = await _vault(async_session, 892)
    dweller1, dweller2 = await _dwellers(async_session, vault)

    relationship = await relationship_service.get_or_create_relationship(async_session, dweller1.id, dweller2.id)
    relationship.affinity = 85
    relationship.relationship_type = "partner"
    dweller1.partner_id = dweller2.id
    dweller2.partner_id = dweller1.id
    await async_session.commit()

    response = await async_client.put(f"/relationships/{relationship.id}/marry", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["relationship_type"] == "MARRIED"

    await async_session.refresh(dweller1)
    await async_session.refresh(dweller2)
    assert dweller1.partner_id == dweller2.id
    assert dweller2.partner_id == dweller1.id


async def test_marry_value_error(async_client, superuser_token_headers):
    mock_rel = _make_mock_relationship()
    with (
        patch(f"{EP}relationship_crud.get", AsyncMock(return_value=mock_rel)),
        patch(f"{EP}verify_dweller_access", AsyncMock(return_value=None)),
        patch(
            f"{EP}relationship_service.marry",
            AsyncMock(side_effect=ValidationException("Affinity too low for marriage")),
        ),
    ):
        response = await async_client.put(f"/relationships/{mock_rel.id}/marry", headers=superuser_token_headers)
    assert response.status_code == 400
    assert "Affinity too low" in response.json()["detail"]


async def test_compatibility_access_denied_dweller_1(async_client, superuser_token_headers):
    d1_id, d2_id = uuid4(), uuid4()
    with (
        patch(
            f"{EP}verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.get(
            f"/relationships/compatibility/{d1_id}/{d2_id}", headers=superuser_token_headers
        )
    assert response.status_code == 403


async def test_process_vault_breeding_success(async_client, superuser_token_headers):
    vault_id = uuid4()
    mock_stats = {"conceptions": 1, "births": 0, "pairs_processed": 3, "relationships_processed": 5}
    with (
        patch(f"{EP}get_user_vault_or_403", AsyncMock(return_value=None)),
        patch(
            "app.services.game_loop_service.game_loop_service._process_breeding",
            AsyncMock(return_value=mock_stats),
        ),
    ):
        response = await async_client.post(f"/relationships/vault/{vault_id}/process", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Breeding and relationships processed successfully"
    assert data["stats"] == mock_stats
