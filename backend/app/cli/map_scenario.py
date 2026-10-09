"""Dev/QA: populate a vault's map with one place per site-type group.

Registers a seeded place for every group in the catalog (plus one ungrouped
place for the wasteland_site fallback) as an unlocked discovery, so each marker
archetype icon is visible on the map for a quick visual check.
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated
from uuid import UUID

import typer
from sqlmodel import select

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum
from app.crud.world_location import world_location as wl_crud
from app.db.session import async_session_maker
from app.models.dweller import Dweller
from app.utils.place_groups import load_place_groups
from app.utils.place_seed import load_seed_entries

app = typer.Typer(
    name="map-scenario",
    help="Dev/QA: populate a vault's map with a place per site-type group.",
    no_args_is_help=True,
)

# The wasteland_site fallback has no seeded name, so register an ungrouped place
# to exercise that (effective) archetype icon too.
FALLBACK_PLACE_NAME = "Unmapped Wasteland Site"


def _seed_name_by_group() -> dict[str, str]:
    """First seeded place display name per group."""
    by_group: dict[str, str] = {}
    for entry in load_seed_entries():
        group = entry.get("group")
        if group and group not in by_group:
            by_group[group] = entry["name"]
    return by_group


@app.command()
def populate(
    vault_id: Annotated[str, typer.Argument(help="Target vault UUID")],
    dweller_id: Annotated[
        str | None, typer.Option("--dweller", help="Discoverer to link (defaults to the vault's first dweller)")
    ] = None,
) -> None:
    """Register one unlocked discovery per site-type group on a vault's map."""
    try:
        vault_uuid = UUID(vault_id)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid vault UUID: {vault_id!r}") from exc

    discoverer_uuid: UUID | None = None
    if dweller_id is not None:
        try:
            discoverer_uuid = UUID(dweller_id)
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid dweller UUID: {dweller_id!r}") from exc

    async def _run() -> dict:
        async with async_session_maker() as session:
            discoverer = discoverer_uuid
            if discoverer is None:
                dweller = (await session.exec(select(Dweller).where(Dweller.vault_id == vault_uuid).limit(1))).first()
                if dweller is None:
                    typer.echo("This vault has no dweller to link; create one first.", err=True)
                    raise typer.Exit(code=1)
                discoverer = dweller.id

            seed_names = _seed_name_by_group()
            markers = []
            for group in load_place_groups():
                key = group["key"]
                name = seed_names.get(key) or (FALLBACK_PLACE_NAME if key == "wasteland_site" else None)
                if name is None:
                    continue
                location = await wl_crud.get_or_create_location(session, name)
                await wl_crud.get_or_create_state(session, vault_uuid, location.id, LocationTypeEnum.DISCOVERY)
                await wl_crud.link_dweller(
                    session,
                    discoverer,
                    location.id,
                    DwellerLocationRelationEnum.VISITED,
                    is_unlocked=True,
                )
                markers.append({"group": key, "name": name, "icon": group["icon"]})
            return {"vault_id": str(vault_uuid), "markers": markers}

    typer.echo(json.dumps(asyncio.run(_run()), indent=2, default=str))
