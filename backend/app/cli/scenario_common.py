"""Shared runner for dev/QA scenario CLI commands.

Every scenario command wraps an async `_run()` in the same try/except block:
print the success line, map known domain errors to a one-line message, and
convert anything else into a logged failure with exit code 1.
"""

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
    """Run a scenario coroutine with the shared CLI exit and error mapping.

    ``detail_errors`` prints the ``ResourceNotFoundException``/``ValueError``
    detail; commands that only use generic failure handling turn it off.
    """
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
