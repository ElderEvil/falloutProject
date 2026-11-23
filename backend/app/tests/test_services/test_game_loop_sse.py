"""Exactly-once SSE publishing for game ticks (see bug-report-duplicate-sse.md)."""

from unittest.mock import MagicMock, patch

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.stream_manager import sse_manager
from app.models.vault import Vault
from app.services.game_loop_service import game_loop_service


async def test_tick_publishes_sse_once_per_vault_and_never_when_paused(async_session, session_factory, vault):
    # Priming the tick creates the GameState that makes the vault "active".
    await game_loop_service.process_vault_tick(async_session, vault.id)

    with patch.object(sse_manager, "publish", new_callable=MagicMock) as mock_publish:
        stats = await game_loop_service.process_game_tick(session_factory)

        mock_publish.assert_called_once()
        _vault_id, topic, data = mock_publish.call_args.args
        assert topic == "game_ticks"
        assert {"resources", "dweller_snapshot"} <= data["results"]["updates"].keys()
    assert stats["vaults_processed"] >= 1

    await game_loop_service.pause_vault(async_session, vault.id)
    with patch.object(sse_manager, "publish", new_callable=MagicMock) as mock_publish:
        result = await game_loop_service.process_vault_tick(async_session, vault.id)
        assert result["status"] == "paused"
        mock_publish.assert_not_called()
