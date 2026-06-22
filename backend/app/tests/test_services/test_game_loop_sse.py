"""Tests for SSE publishing in the game loop.

These tests verify that game tick SSE events are published exactly once
per vault. See bug-report-duplicate-sse.md for context.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.vault import Vault
from app.services.game_loop import game_loop_service
from app.services.stream_manager import sse_manager


@pytest.mark.asyncio
async def test_process_vault_tick_publishes_sse_once(
    async_session: AsyncSession,
    vault: Vault,
):
    """process_vault_tick publishes SSE exactly once."""
    with patch.object(sse_manager, "publish", new_callable=MagicMock) as mock_publish:
        result = await game_loop_service.process_vault_tick(async_session, vault.id)

        mock_publish.assert_called_once()
        args, _kwargs = mock_publish.call_args
        _vault_id, topic, _data = args
        assert topic == "game_ticks"
        assert "results" in (args[2] if len(args) > 2 else {})
    assert result is not None


@pytest.mark.asyncio
async def test_process_game_tick_publishes_sse_once_per_vault(
    async_session: AsyncSession,
    vault: Vault,
):
    """process_game_tick publishes SSE exactly ONCE per vault (not twice).

    Before the fix, process_game_tick published AFTER process_vault_tick
    returned, and process_vault_tick ALSO published — causing 2 SSE events
    per vault. This test pins the expected count to 1.
    """
    # Prime: create a GameState so the vault is "active"
    await game_loop_service.process_vault_tick(async_session, vault.id)

    with patch.object(sse_manager, "publish", new_callable=MagicMock) as mock_publish:
        stats = await game_loop_service.process_game_tick(async_session)

        # This assertion FAILS before the fix (it's called twice)
        mock_publish.assert_called_once()
        args, _kwargs = mock_publish.call_args
        _vault_id, topic, _data = args
        assert topic == "game_ticks"
    assert stats["vaults_processed"] >= 1


@pytest.mark.asyncio
async def test_process_vault_tick_no_sse_when_paused(
    async_session: AsyncSession,
    vault: Vault,
):
    """paused vaults do NOT publish SSE."""
    await game_loop_service.process_vault_tick(async_session, vault.id)
    await game_loop_service.pause_vault(async_session, vault.id)

    with patch.object(sse_manager, "publish", new_callable=MagicMock) as mock_publish:
        result = await game_loop_service.process_vault_tick(async_session, vault.id)

        assert result["status"] == "paused"
        mock_publish.assert_not_called()
