import pytest
from sqlmodel import select

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.user import User
from app.models.vault import Vault
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_debug_quest_start_404(async_client, async_session):
    """Debug test to reproduce the 404 error when starting a quest.

    The issue: Quest is created and assigned to vault, but endpoint returns 404.
    """
    from app.tests.utils.user import user_authentication_headers

    # Setup
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create quest
    quest = Quest(
        title="Debug Quest",
        short_description="Debug",
        long_description="Debug quest",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    print(f"\nCreated quest with ID: {quest.id}")

    # Verify quest exists in DB
    result = await async_session.execute(select(Quest).where(Quest.id == quest.id))
    found_quest = result.scalar_one_or_none()
    print(f"Quest found in DB: {found_quest is not None}")

    # Assign to vault
    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest.id, vault_id=vault.id)
    await async_session.commit()
    print("Assigned quest to vault")

    # Check VaultQuestCompletionLink
    link_query = select(VaultQuestCompletionLink).where(
        VaultQuestCompletionLink.vault_id == vault.id, VaultQuestCompletionLink.quest_id == quest.id
    )
    link_result = await async_session.execute(link_query)
    link = link_result.scalar_one_or_none()
    print(f"VaultQuestCompletionLink: {link}")
    print(f"  is_visible: {link.is_visible if link else 'N/A'}")
    print(f"  is_completed: {link.is_completed if link else 'N/A'}")
    print(f"  started_at: {link.started_at if link else 'N/A'}")

    # Create dweller
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    # Try to start quest
    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    # First test a simple endpoint
    test_response = await async_client.get("/quests/", headers=headers)
    print(f"Test GET /quests/ status: {test_response.status_code}")

    response = await async_client.post(
        f"/quests/{vault.id}/{quest.id}/start",
        headers=headers,
    )

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")

    # Should be 200 (no requirements) or 400 (if requirements not met)
    # But currently getting 404
    assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}: {response.text}"
