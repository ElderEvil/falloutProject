"""Perk routes require ownership and retain server-side selection rules."""

from unittest.mock import AsyncMock

from app.core.enums import AgeGroupEnum, DwellerStatusEnum
from app.core.security import create_access_token
from app.services.notification_service import manager, sse_manager


async def test_owner_can_choose_but_foreign_user_cannot_read_or_select(
    async_client, async_session, dweller, vault, superuser, monkeypatch
):
    monkeypatch.setattr(manager, "send_personal_message", AsyncMock())
    monkeypatch.setattr(sse_manager, "publish", AsyncMock())
    dweller.level = 5
    dweller.intelligence = 4
    dweller.age_group = AgeGroupEnum.ADULT
    dweller.is_dead = False
    dweller.status = DwellerStatusEnum.IDLE
    superuser.is_superuser = False
    await async_session.commit()
    owner = {"Authorization": f"Bearer {create_access_token(vault.user_id)}"}
    foreign = {"Authorization": f"Bearer {create_access_token(superuser.id)}"}
    path = f"/dwellers/{dweller.id}/perks"
    assert (await async_client.get(path, headers=foreign)).status_code == 403
    assert (await async_client.post(path, json={"perk": "hacker"}, headers=foreign)).status_code == 403
    assert (await async_client.get(path)).status_code == 401
    catalog = await async_client.get(path, headers=owner)
    assert catalog.status_code == 200
    assert catalog.json()["selected_perk"] is None
    selected = await async_client.post(path, json={"perk": "hacker"}, headers=owner)
    assert selected.status_code == 200
    assert selected.json()["selected_perk"] == "hacker"
    assert (await async_client.post(path, json={"perk": "hacker"}, headers=owner)).status_code == 409
    assert (await async_client.post(path, json={"perk": "invented"}, headers=owner)).status_code == 422
