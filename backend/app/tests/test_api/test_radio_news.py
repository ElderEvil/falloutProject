import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.tests.factory.vaults import random_vault_number

pytestmark = pytest.mark.asyncio(scope="module")


async def _founding_day_vault(async_session: AsyncSession):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    return await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": random_vault_number()},
        user_id=user.id,
    )


async def test_radio_news_airs_on_the_founding_day(async_client, async_session, superuser_token_headers):
    vault = await _founding_day_vault(async_session)

    response = await async_client.get(f"/vaults/{vault.id}/radio-news", headers=superuser_token_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "daily"
    assert body["script"]


async def test_radio_news_regenerate_on_the_founding_day_is_not_a_conflict(
    async_client, async_session, superuser_token_headers
):
    vault = await _founding_day_vault(async_session)

    response = await async_client.post(f"/vaults/{vault.id}/radio-news/regenerate", headers=superuser_token_headers)

    assert response.status_code == 200
    assert response.json()["trigger"] == "manual"
