"""Audited superuser commands over the same services used by fo-cli.

Scenario setup retains the CLI's explicit multi-stage transaction ownership:
departure may remain durable if fast-forward/report creation fails. No shell or
subprocess is involved, and this surface only dispatches existing dwellers.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Any

from pydantic import UUID4, BaseModel, ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.schemas.console import (
    ConsoleArgs,
    ConsoleCommand,
    ConsoleLink,
    ConsoleManifest,
    ConsoleRequest,
    ConsoleResult,
    ConsoleSite,
    ExpeditionSetupArgs,
    HelpArgs,
    VaultArgs,
)
from app.services import catalog_service
from app.services.exploration.expedition_scenario_service import expedition_scenario_service
from app.utils.exceptions import DomainError, ValidationException

logger = logging.getLogger(__name__)


async def _vault_list(session: AsyncSession) -> ConsoleResult:
    vaults = await crud.vault.get_multi(session, limit=100)
    return ConsoleResult(lines=[f"Vault {vault.number}: {vault.id}" for vault in vaults] or ["No vaults."])


async def _vault_state(session: AsyncSession, vault_id: UUID4) -> ConsoleResult:
    vault = await crud.vault.get(session, vault_id)
    return ConsoleResult(
        lines=[
            f"Vault {vault.number} — {vault.id}",
            f"Caps {vault.bottle_caps} | Happiness {vault.happiness} | Mode {vault.vault_mode}",
            (
                f"Power {vault.power}/{vault.power_max} | Food {vault.food}/{vault.food_max} | "
                f"Water {vault.water}/{vault.water_max}"
            ),
        ]
    )


async def _dweller_list(session: AsyncSession, vault_id: UUID4) -> ConsoleResult:
    await crud.vault.get(session, vault_id)
    dwellers = await crud.dweller.get_multi_by_vault(session, vault_id, limit=200)
    return ConsoleResult(
        lines=[f"{d.display_name} | level {d.level} | {d.status} | {d.id}" for d in dwellers] or ["No dwellers."]
    )


async def _expedition_status(session: AsyncSession, vault_id: UUID4) -> ConsoleResult:
    await crud.vault.get(session, vault_id)
    status = await expedition_scenario_service.get_status(session, vault_id)
    if status is None:
        return ConsoleResult(lines=["No active explorations."])
    lines: list[str] = []
    links: list[ConsoleLink] = []
    for entry in status.explorations:
        lines.extend(
            [
                f"{entry.dweller_name} | {entry.status} | level {entry.dweller_level}",
                "Available sites: " + (", ".join(site.name for site in entry.available_sites) or "none"),
            ]
        )
        links.append(ConsoleLink(label=entry.dweller_name, to=f"/vault/{vault_id}/exploration/{entry.exploration_id}"))
    return ConsoleResult(lines=lines, links=links)


async def _expedition_setup(
    session: AsyncSession, vault_id: UUID4, dweller_id: UUID4, site_id: str, duration_hours: int
) -> ConsoleResult:
    result = await expedition_scenario_service.setup(
        session,
        vault_id=vault_id,
        dweller_id=dweller_id,
        discovered_site_id=site_id,
        duration_hours=duration_hours,
    )
    return ConsoleResult(
        lines=[f"{result.dweller.display_name} found {site_id}. Enter before the dweller arrives home."],
        links=[
            ConsoleLink(
                label="Open expedition site",
                to=f"/vault/{result.vault.id}/exploration/{result.exploration.id}?siteId={site_id}",
            )
        ],
    )


@dataclass(frozen=True)
class _Command:
    description: str
    args: type[BaseModel]
    handler: Callable[..., Awaitable[ConsoleResult]]
    mutates: bool = False


async def _help(_session: AsyncSession, command: str | None = None) -> ConsoleResult:
    commands = _commands if command is None else {command: _lookup(command)}
    lines = []
    for name, spec in commands.items():
        schema = spec.args.model_json_schema()
        fields = schema.get("properties", {})
        arguments = " ".join(
            f"--{key.replace('_', '-')} <value>" + ("" if key in schema.get("required", []) else " (optional)")
            for key in fields
        )
        lines.extend([f"{name} {arguments}".rstrip(), f"  {spec.description}"])
    return ConsoleResult(lines=lines)


_commands = {
    "help": _Command("List commands or explain one command.", HelpArgs, _help),
    "vault.list": _Command("List vault numbers and IDs (first 100).", ConsoleArgs, _vault_list),
    "vault.state": _Command("Inspect vault resources and morale.", VaultArgs, _vault_state),
    "dweller.list": _Command("List dwellers, statuses and IDs (first 200).", VaultArgs, _dweller_list),
    "expedition.status": _Command("Inspect active journeys and available sites.", VaultArgs, _expedition_status),
    "expedition.setup": _Command(
        "Send an existing dweller to a ready-to-play site. Preserves level and SPECIAL; skips travel. "
        "Departure remains saved if a later setup stage fails.",
        ExpeditionSetupArgs,
        _expedition_setup,
        mutates=True,
    ),
}


def _lookup(command: str) -> _Command:
    if command in _commands:
        return _commands[command]
    suggestions = get_close_matches(command, _commands, n=1)
    hint = f" Did you mean {suggestions[0]}?" if suggestions else " Use help to list commands."
    raise ValidationException(f"Unknown command: {command}.{hint}")


def console_manifest() -> ConsoleManifest:
    """Expose argument schemas and catalog sites without duplicating validation."""
    return ConsoleManifest(
        commands=[
            ConsoleCommand(
                name=name, description=spec.description, mutates=spec.mutates, args_schema=spec.args.model_json_schema()
            )
            for name, spec in _commands.items()
        ],
        sites=[
            ConsoleSite(id=site.id, name=site.name, min_level=site.min_dweller_level)
            for site in catalog_service.load_expedition_sites()
        ],
    )


async def execute_console(session: AsyncSession, actor_id: UUID4, request: ConsoleRequest) -> ConsoleResult:
    """Validate, dispatch and audit every invocation at the operation boundary."""
    audit: dict[str, Any] = {"actor_id": str(actor_id), "command": request.command, "args": request.args}
    logger.info("Admin console invoked: %s", json.dumps(audit), extra={"console": audit})
    outcome = "failed"
    try:
        spec = _lookup(request.command)
        args = spec.args.model_validate(request.args)
        result = await spec.handler(session, **args.model_dump())
        outcome = "succeeded"
    except Exception as error:
        if isinstance(error, ValidationError):
            details = "; ".join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in error.errors())
            return ConsoleResult(ok=False, lines=[details])
        if isinstance(error, (DomainError, ValueError)):
            return ConsoleResult(ok=False, lines=[str(error.detail) if isinstance(error, DomainError) else str(error)])
        logger.exception("Admin console failed", extra={"console": audit})
        raise
    else:
        return result
    finally:
        logger.info(
            "Admin console %s: %s", outcome, json.dumps(audit), extra={"console": {**audit, "outcome": outcome}}
        )
