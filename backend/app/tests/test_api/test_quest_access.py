"""Quest endpoint access-control tests."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.quest import read_vault_quests


@pytest.mark.asyncio
async def test_read_vault_quests_checks_access_before_querying() -> None:
    """A caller without vault access cannot list that vault's quests."""
    db_session = AsyncMock()
    user = MagicMock()
    vault_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.quest.get_user_vault_or_403",
            new=AsyncMock(side_effect=HTTPException(status_code=403, detail="Forbidden")),
        ),
        patch("app.api.v1.endpoints.quest.crud.quest_crud.get_multi_for_vault", new=AsyncMock()) as get_quests,
        pytest.raises(HTTPException, match="Forbidden"),
    ):
        await read_vault_quests(vault_id, db_session, user)

    get_quests.assert_not_awaited()
