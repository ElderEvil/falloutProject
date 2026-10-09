"""Tests for the map-scenario CLI (per-group icon population)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from app.cli.main import cli
from app.cli.map_scenario import FALLBACK_PLACE_NAME, _seed_name_by_group
from app.utils.place_groups import load_place_groups

runner = CliRunner()


def test_every_group_is_covered_by_the_scenario():
    """Every catalog group must resolve to a marker so each icon is exercised.

    Groups are name-derived, so a group with no seeded place cannot appear on the
    map at all; the fallback archetype is reached via an ungrouped place.
    """
    seeded = _seed_name_by_group()
    covered = set(seeded) | {"wasteland_site"}
    assert covered == {group["key"] for group in load_place_groups()}


def _patched_session():
    session = AsyncMock()
    patcher = patch("app.cli.map_scenario.async_session_maker")
    maker = patcher.start()
    maker.return_value.__aenter__ = AsyncMock(return_value=session)
    maker.return_value.__aexit__ = AsyncMock(return_value=False)
    return session, patcher


def test_populate_registers_one_marker_per_group():
    vault_id = uuid4()
    dweller_id = uuid4()

    with patch("app.cli.map_scenario.wl_crud") as crud:
        crud.get_or_create_location = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        crud.get_or_create_state = AsyncMock()
        crud.link_dweller = AsyncMock()
        _, patcher = _patched_session()
        try:
            result = runner.invoke(cli, ["map-scenario", "populate", str(vault_id), "--dweller", str(dweller_id)])
        finally:
            patcher.stop()

    assert result.exit_code == 0
    expected = len(load_place_groups())
    assert crud.get_or_create_location.await_count == expected
    assert crud.get_or_create_state.await_count == expected
    assert crud.link_dweller.await_count == expected
    # Every link unlocks so the marker renders.
    assert all(call.kwargs["is_unlocked"] for call in crud.link_dweller.await_args_list)

    markers = json.loads(result.output)["markers"]
    assert len(markers) == expected
    assert {m["group"] for m in markers} == {group["key"] for group in load_place_groups()}
    assert any(m["name"] == FALLBACK_PLACE_NAME and m["group"] == "wasteland_site" for m in markers)


def test_populate_errors_without_a_dweller_to_link():
    vault_id = uuid4()
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    session.exec = AsyncMock(return_value=execute_result)

    with patch("app.cli.map_scenario.async_session_maker") as maker:
        maker.return_value.__aenter__ = AsyncMock(return_value=session)
        maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = runner.invoke(cli, ["map-scenario", "populate", str(vault_id)])

    assert result.exit_code == 1
    assert "no dweller" in result.output.lower()
