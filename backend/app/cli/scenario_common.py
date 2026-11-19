"""Shared runner for scenario CLI commands: maps domain errors to one line, logs other failures with exit 1."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import typer

from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)


def run_scenario_command(
    command: str,
    run: Callable[[], Coroutine[Any, Any, None]],
    *,
    success_message: bool = True,
    detail_errors: bool = True,
) -> None:
    """Run a scenario coroutine with shared exit/error mapping; detail_errors prints the exception detail."""
    try:
        asyncio.run(run())
        if success_message:
            typer.echo(f"✓ {command} complete.")
    except typer.Exit:
        raise
    except Exception as exc:
        if detail_errors and isinstance(exc, (ResourceNotFoundException, ValueError)):
            detail = exc.detail if isinstance(exc, ResourceNotFoundException) else str(exc)
            typer.echo(f"Error: {detail}", err=True)
            raise typer.Exit(code=1) from None
        logger.exception("%s failed", command)
        typer.echo(f"Error: {command} failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc
