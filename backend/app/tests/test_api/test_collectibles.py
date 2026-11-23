from __future__ import annotations

from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.collectible_service import collectible_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.vaults import create_fake_vault


async def _vault_for(async_session: AsyncSession, user_id: UUID):
    return await crud.vault.create(
        db_session=async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user_id)
    )


async def _dweller_in(async_session: AsyncSession, vault_id: UUID):
    data = create_fake_dweller()
    data.update({"first_name": "Claim", "last_name": "Holder"})
    return await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault_id))


async def test_collectibles_endpoint_lists_the_dwellers_current_vault_claims(
    async_client, superuser_token_headers, async_session
) -> None:
    user = await crud.user.get_by_email(email=settings.FIRST_SUPERUSER_EMAIL, db_session=async_session)
    vault = await _vault_for(async_session, user.id)
    dweller = await _dweller_in(async_session, vault.id)
    await collectible_service.award(async_session, vault_id=vault.id, dweller=dweller, collectible_key="strength")
    await async_session.commit()
    response = await async_client.get(f"/dwellers/{dweller.id}/collectibles", headers=superuser_token_headers)
    assert response.status_code == 200
    body = response.json()
    assert [item["key"] for item in body] == ["strength"]
    assert body[0]["stat"] == "strength"
    assert body[0]["image"] == "bobblehead_images/strength.png"


async def test_collectibles_endpoint_rejects_a_foreign_dweller(
    async_client, normal_user_token_headers, async_session
) -> None:
    owner = await crud.user.get_by_email(email=settings.FIRST_SUPERUSER_EMAIL, db_session=async_session)
    vault = await _vault_for(async_session, owner.id)
    dweller = await _dweller_in(async_session, vault.id)
    await async_session.commit()
    response = await async_client.get(f"/dwellers/{dweller.id}/collectibles", headers=normal_user_token_headers)
    assert response.status_code == 403
