"""CLI: seed-places — idempotent canonical world-place registry seeding via place_seed_service."""

from __future__ import annotations

import asyncio
import logging

import typer

from app.services.place_seed_service import seed_places_from_json

logger = logging.getLogger(__name__)


def seed_places() -> None:
    """Insert missing canonical registry rows from seed_places.json (idempotent)."""

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            inserted = await seed_places_from_json(session)
            typer.echo(f"✓ Seeded {inserted} new place(s) into the world registry.")

    try:
        asyncio.run(_run())
        typer.echo("✓ seed-places complete.")
    except Exception as exc:
        logger.exception("seed-places failed")
        typer.echo("Error: seed-places failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc
