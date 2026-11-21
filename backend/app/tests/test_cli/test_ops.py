"""Tests for ops CLI commands."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from app.cli.main import cli

runner = CliRunner()


def _patch_ops_session(rooms: list) -> MagicMock:
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = rooms
    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    patcher = patch("app.cli.ops.async_session_maker")
    mock_session_maker = patcher.start()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher


def test_fix_room_image_urls_repairs_stale_merged_room():
    stale = SimpleNamespace(
        name="Living room",
        tier=1,
        size=9,
        size_min=3,
        image_url="/static/room_images/FOS Living Quarters 1-1.png",
    )
    fresh = SimpleNamespace(
        name="Power Generator",
        tier=1,
        size=3,
        size_min=3,
        image_url="/static/room_images/FOS Power 1-1.png",
    )
    patcher = _patch_ops_session([stale, fresh])

    try:
        result = runner.invoke(cli, ["ops", "fix-room-image-urls"])
    finally:
        patcher.stop()

    assert result.exit_code == 0, result.output
    assert stale.image_url == "/static/room_images/FOS Living Quarters 1-3.png"
    assert fresh.image_url == "/static/room_images/FOS Power 1-1.png"
    assert "1 room" in result.output
