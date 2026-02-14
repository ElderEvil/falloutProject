import pytest

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_start_quest_assigns_and_starts(async_client, async_session):
    """Test that starting a quest assigns it to vault and returns success."""
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Test Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest.id, vault_id=vault.id)
    await async_session.commit()

    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.post(
        f"/quests/{vault.id}/{quest.id}/start",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
