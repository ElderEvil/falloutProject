"""Console authorization, validation, audit and shared scenario integration."""

import inspect
import logging
from uuid import uuid4

import pytest
from sqlalchemy import event

from app import crud
from app.crud.notification import notification as notification_crud
from app.crud.user_profile import profile_crud
from app.schemas.console import ConsoleRequest
from app.services.console_service import _commands, console_manifest, execute_console


@pytest.mark.parametrize("path", ["/system/console", "/system/console/manifest"])
async def test_console_rejects_non_admin(async_client, normal_user_token_headers, path):
    response = await async_client.request(
        "POST" if path.endswith("console") else "GET",
        path,
        headers=normal_user_token_headers,
        **({"json": {"command": "vault.list"}} if path.endswith("console") else {}),
    )
    assert response.status_code == 403


async def test_console_requires_auth(async_client):
    assert (await async_client.get("/system/console/manifest")).status_code == 401
    assert (await async_client.post("/system/console", json={"command": "vault.list"})).status_code == 401


async def test_manifest_matches_handlers(async_client, superuser_token_headers):
    response = await async_client.get("/system/console/manifest", headers=superuser_token_headers)
    assert response.status_code == 200
    manifest = response.json()
    assert {s["id"] for s in manifest["sites"]} >= {"collapsed_subway", "rusted_midway"}
    assert next(c for c in manifest["commands"] if c["name"] == "expedition.setup")["mutates"] is True
    for command in console_manifest().commands:
        spec = _commands[command.name]
        parameters = list(inspect.signature(spec.handler).parameters)[1:]
        assert set(parameters) == set(command.args_schema.get("properties", {}))


@pytest.mark.parametrize(
    ("command", "args", "expected"),
    [
        ("expedition.setp", {}, "Did you mean expedition.setup?"),
        ("expedition.setup", {}, "dweller_id"),
        ("vault.state", {"vault_id": "not-a-uuid"}, "vault_id"),
        ("vault.list", {"shell": "rm -rf /"}, "Extra inputs"),
    ],
)
async def test_console_rejects_invalid_commands(async_client, superuser_token_headers, command, args, expected):
    response = await async_client.post(
        "/system/console", headers=superuser_token_headers, json={"command": command, "args": args}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert expected in " ".join(response.json()["lines"])


async def test_inspection_and_audit(async_client, superuser_token_headers, vault, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.console_service"):
        response = await async_client.post(
            "/system/console",
            headers=superuser_token_headers,
            json={"command": "vault.state", "args": {"vault_id": str(vault.id)}},
        )
    assert response.status_code == 200
    assert str(vault.number) in response.json()["lines"][0]
    record = next(r for r in caplog.records if r.message.startswith("Admin console succeeded:"))
    assert record.console["actor_id"]
    assert record.console["args"] == {"vault_id": str(vault.id)}
    assert record.console["outcome"] == "succeeded"


async def test_failed_command_is_audited(async_session, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.console_service"):
        result = await execute_console(async_session, uuid4(), ConsoleRequest(command="nope"))
    assert result.ok is False
    assert any(
        r.message.startswith("Admin console failed:") and r.console["outcome"] == "failed" for r in caplog.records
    )


async def test_setup_uses_existing_dweller_and_offers_site(async_session, vault, dweller):
    before = await crud.dweller.get_multi_by_vault(async_session, vault.id)
    result = await execute_console(
        async_session,
        vault.user_id,
        ConsoleRequest(
            command="expedition.setup",
            args={"vault_id": str(vault.id), "dweller_id": str(dweller.id), "site_id": "collapsed_subway"},
        ),
    )
    assert result.ok, result.lines
    assert "siteId=collapsed_subway" in result.links[0].to
    journeys = await crud.exploration.get_by_vault(async_session, vault_id=vault.id, active_only=True)
    assert len(journeys) == 1
    assert journeys[0].dweller_id == dweller.id
    assert any(event.get("site_id") == "collapsed_subway" for event in journeys[0].events)
    assert len(await crud.dweller.get_multi_by_vault(async_session, vault.id)) == len(before)
    status = await execute_console(
        async_session,
        vault.user_id,
        ConsoleRequest(
            command="expedition.status",
            args={"vault_id": str(vault.id)},
        ),
    )
    assert "Collapsed Subway" in " ".join(status.lines)


async def test_setup_invalid_site_changes_nothing(async_session, vault, dweller):
    vault_id = vault.id
    result = await execute_console(
        async_session,
        vault.user_id,
        ConsoleRequest(
            command="expedition.setup",
            args={"vault_id": str(vault.id), "dweller_id": str(dweller.id), "site_id": "invalid"},
        ),
    )
    assert result.ok is False
    await async_session.rollback()
    assert await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True) == []


async def test_setup_late_failure_preserves_only_committed_departure(async_session, vault, dweller):
    """The reused CLI operation explicitly persists departure before fast-forwarding."""
    vault_id, dweller_id, actor_id = vault.id, dweller.id, vault.user_id
    engine = async_session.bind.sync_engine

    def fail_fast_forward(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("UPDATE exploration SET"):
            raise RuntimeError("late scenario write failed")

    event.listen(engine, "before_cursor_execute", fail_fast_forward)
    try:
        with pytest.raises(RuntimeError, match="late scenario write failed"):
            await execute_console(
                async_session,
                actor_id,
                ConsoleRequest(
                    command="expedition.setup",
                    args={"vault_id": str(vault_id), "dweller_id": str(dweller_id), "site_id": "collapsed_subway"},
                ),
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_fast_forward)
    await async_session.rollback()
    journeys = await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True)
    assert len(journeys) == 1
    assert journeys[0].status.value == "active"
    assert not any(event.get("event") == "site_found" for event in journeys[0].events)
    notifications = await notification_crud.get_user_notifications(async_session, actor_id)
    assert not any((row.meta_data or {}).get("event") == "site_found" for row in notifications)


@pytest.mark.parametrize(("balance", "amount", "expected"), [(100, {}, 600), (999_900, {"amount": 500}, 999_999)])
async def test_greedisgood_respects_cap_without_earned_progress(async_session, vault, balance, amount, expected):
    vault_id, actor_id = vault.id, vault.user_id
    await crud.vault.update(async_session, vault_id, {"bottle_caps": balance})
    profile = await profile_crud.get_by_user_id(async_session, actor_id)
    earned_before = profile.total_caps_earned if profile else None
    result = await execute_console(
        async_session,
        actor_id,
        ConsoleRequest(
            command="greedisgood",
            args={"vault_id": str(vault_id), **amount},
        ),
    )
    assert result.ok
    await async_session.refresh(vault)
    assert vault.bottle_caps == expected
    profile = await profile_crud.get_by_user_id(async_session, actor_id)
    assert (profile.total_caps_earned if profile else None) == earned_before


@pytest.mark.parametrize("amount", [0, -500, 1_000_000])
async def test_greedisgood_rejects_invalid_amount(async_session, vault, amount):
    original, vault_id = vault.bottle_caps, vault.id
    result = await execute_console(
        async_session,
        vault.user_id,
        ConsoleRequest(
            command="greedisgood",
            args={"vault_id": str(vault_id), "amount": amount},
        ),
    )
    assert result.ok is False
    await async_session.rollback()
    reloaded = await crud.vault.get(async_session, vault_id)
    assert reloaded.bottle_caps == original


async def test_thereisnospoon_refills_only_to_capacity(async_session, vault):
    vault_id, actor_id = vault.id, vault.user_id
    await crud.vault.update(
        async_session,
        vault_id,
        {
            "power": 1,
            "power_max": 500,
            "food": 2,
            "food_max": 300,
            "water": 3,
            "water_max": 0,
        },
    )
    original_caps = vault.bottle_caps
    result = await execute_console(
        async_session,
        actor_id,
        ConsoleRequest(
            command="thereisnospoon",
            args={"vault_id": str(vault_id)},
        ),
    )
    assert result.ok
    await async_session.refresh(vault)
    assert (vault.power, vault.food, vault.water) == (500, 300, 0)
    assert vault.bottle_caps == original_caps


@pytest.mark.parametrize("command", ["greedisgood", "thereisnospoon"])
async def test_cheat_commit_failure_rolls_back_changes(async_session, vault, command):
    original = (vault.bottle_caps, vault.power, vault.food, vault.water)
    vault_id, actor_id = vault.id, vault.user_id

    def fail_commit(_session):
        raise RuntimeError("cheat commit failed")

    event.listen(async_session.sync_session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="cheat commit failed"):
            await execute_console(
                async_session,
                actor_id,
                ConsoleRequest(
                    command=command,
                    args={"vault_id": str(vault_id)},
                ),
            )
    finally:
        event.remove(async_session.sync_session, "before_commit", fail_commit)
    await async_session.rollback()
    reloaded = await crud.vault.get(async_session, vault_id)
    assert (reloaded.bottle_caps, reloaded.power, reloaded.food, reloaded.water) == original


async def test_cheat_is_forbidden_for_ordinary_user(async_client, normal_user_token_headers, async_session, vault):
    original = vault.bottle_caps
    response = await async_client.post(
        "/system/console",
        headers=normal_user_token_headers,
        json={
            "command": "greedisgood",
            "args": {"vault_id": str(vault.id), "amount": 500},
        },
    )
    assert response.status_code == 403
    await async_session.refresh(vault)
    assert vault.bottle_caps == original
