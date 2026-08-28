"""CLI command group: family-scenario — deterministic family/breeding test setup.

Thin wrapper over :class:`app.services.family_scenario_service.FamilyScenarioService`;
all business logic lives in the service layer per AGENTS.md.

Usage (from backend/):
    uv run fo-cli family-scenario setup --vault-id <UUID> --count 3
    uv run fo-cli family-scenario setup --vault-id <UUID> \
        --pairs "d1,d2" --stage MARRIED --affinity 95 \
        --pregnancy-due-minutes "15,60" --postpartum-hours "2,7" --child-ages-hours "1,4"
    uv run fo-cli family-scenario status --vault-id <UUID>
    uv run fo-cli family-scenario reset --vault-id <UUID> --yes
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import typer

from app.services.family_scenario_service import family_scenario_service
from app.utils.exceptions import ResourceNotFoundException

app = typer.Typer(
    name="family-scenario",
    help="Dev/QA: build deterministic family/breeding scenarios for manual testing.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


def _parse_pairs(pairs: str | None) -> list[tuple[UUID, UUID]] | None:
    """Parse a comma-separated list of pairs: ``"d1,d2;d3,d4"``."""
    if not pairs:
        return None
    result: list[tuple[UUID, UUID]] = []
    for chunk in pairs.split(";"):
        ids = [part.strip() for part in chunk.split(",") if part.strip()]
        if len(ids) != 2:
            raise typer.BadParameter(f"Each pair must be exactly two dweller ids, got {chunk!r}")
        try:
            result.append((UUID(ids[0]), UUID(ids[1])))
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid dweller id in --pairs chunk {chunk!r}: {exc}") from exc
    return result


def _parse_float_list(values: str | None) -> list[float] | None:
    """Parse a comma-separated list of numbers."""
    if not values:
        return None
    result: list[float] = []
    for token in values.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            result.append(float(stripped))
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid number {stripped!r} in --postpartum-hours / --child-ages-hours") from exc
    return result


def _parse_int_list(values: str | None) -> list[int] | None:
    """Parse a comma-separated list of integers."""
    if not values:
        return None
    result: list[int] = []
    for token in values.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            result.append(int(stripped))
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid integer {stripped!r} in --pregnancy-due-minutes") from exc
    return result


@app.command()
def setup(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
    count: Annotated[int, typer.Option("--count", "-c", min=1, max=20, help="Couples to auto-pair")] = 1,
    pairs: Annotated[
        str | None,
        typer.Option(
            "--pairs",
            help='Explicit dweller pairs (takes precedence over --count), e.g. "d1,d2;d3,d4"',
        ),
    ] = None,
    stage: Annotated[
        str,
        typer.Option(
            "--stage",
            help="Relationship stage for every couple: acquaintance, friend, romantic, partner, MARRIED, ex",
        ),
    ] = "partner",
    affinity: Annotated[
        int | None,
        typer.Option("--affinity", "-a", min=0, max=100, help="Affinity for every couple (defaults per stage)"),
    ] = None,
    room_id: Annotated[
        UUID | None, typer.Option("--room-id", help="Room to co-locate couples in (default: first living quarters)")
    ] = None,
    pregnancy_due_minutes: Annotated[
        str | None,
        typer.Option(
            "--pregnancy-due-minutes",
            help="Per-couple pregnancy due offsets (minutes), e.g. '15,60'. Negative = already overdue.",
        ),
    ] = None,
    postpartum_hours: Annotated[
        str | None,
        typer.Option(
            "--postpartum-hours",
            help="Per-couple DELIVERED timestamps (hours ago), e.g. '2,7' (tests the 6h cooldown edge).",
        ),
    ] = None,
    child_ages_hours: Annotated[
        str | None,
        typer.Option(
            "--child-ages-hours",
            help="Per-couple child ages (hours), e.g. '1,4' (tests the 3h growth edge).",
        ),
    ] = None,
    seed: Annotated[int | None, typer.Option("--seed", "-s", help="Deterministic RNG seed")] = None,
    no_colocate: Annotated[
        bool,
        typer.Option("--no-colocate", help="Do NOT move couples into a living-quarters room"),
    ] = False,
) -> None:
    """Create couples (and optional pregnancies/children) with controlled timings."""
    from app.schemas.common import RelationshipTypeEnum

    try:
        RelationshipTypeEnum(stage)
    except ValueError:
        valid = ", ".join(m.value for m in RelationshipTypeEnum)
        raise typer.BadParameter(f"Unknown stage {stage!r}. Valid stages: {valid}") from None

    parsed_pairs = _parse_pairs(pairs)
    parsed_pregnancy = _parse_int_list(pregnancy_due_minutes)
    parsed_postpartum = _parse_float_list(postpartum_hours)
    parsed_child_ages = _parse_float_list(child_ages_hours)

    async def _run(
        parsed_pairs: list[tuple[UUID, UUID]] | None,
        parsed_pregnancy: list[int] | None,
        parsed_postpartum: list[float] | None,
        parsed_child_ages: list[float] | None,
    ) -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            try:
                result = await family_scenario_service.setup(
                    db_session=session,
                    vault_id=vault_id,
                    count=count,
                    pairs=parsed_pairs,
                    stage=stage,
                    affinity=affinity,
                    room_id=room_id,
                    pregnancy_due_minutes=parsed_pregnancy,
                    postpartum_hours=parsed_postpartum,
                    child_ages_hours=parsed_child_ages,
                    seed=seed,
                    co_locate=not no_colocate,
                )
            except ValueError as exc:
                typer.echo(f"Error: {exc}", err=True)
                raise typer.Exit(code=1) from None
            except ResourceNotFoundException as exc:
                typer.echo(f"Error: {exc.detail}", err=True)
                raise typer.Exit(code=1) from None

            for couple in result.couples:
                room = couple.dweller_1.room_id
                room_str = f" (room {room})" if room else " (no room)"
                typer.echo(
                    f"  Couple #{couple.index + 1}: {couple.dweller_1.first_name} + {couple.dweller_2.first_name} "
                    f"[{couple.relationship.relationship_type}] affinity "
                    f"{couple.relationship.affinity}{room_str}"
                )
            for preg in result.pregnancies:
                due_in = max(0, (preg.due_at - datetime.now(UTC).replace(tzinfo=None)).total_seconds() / 60)
                typer.echo(f"  Pregnancy: due in {due_in:.0f} min")
            for preg in result.postpartum:
                hours_ago = max(0, (datetime.now(UTC).replace(tzinfo=None) - preg.updated_at).total_seconds() / 3600)
                typer.echo(f"  Postpartum: delivered {hours_ago:.1f} h ago")
            for child in result.children:
                typer.echo(f"  Child: {child.first_name} {child.last_name or ''}".rstrip())

            typer.echo("")
            typer.echo("Timeline:")
            for row in await family_scenario_service.get_status(session, vault_id):
                suffix = f" — {row.countdown}" if row.countdown else ""
                typer.echo(f"  [{row.kind:>13}] {row.label} ({row.detail}){suffix}")

    try:
        asyncio.run(_run(parsed_pairs, parsed_pregnancy, parsed_postpartum, parsed_child_ages))
        typer.echo("✓ family-scenario setup complete.")
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("family-scenario setup failed")
        typer.echo("Error: family-scenario setup failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def status(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
) -> None:
    """Print the current family timeline (relationships, pregnancies, children)."""

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            rows = await family_scenario_service.get_status(session, vault_id)
            if not rows:
                typer.echo("No family data in this vault yet. Run 'uv run fo-cli family-scenario setup' first.")
                return
            for row in rows:
                suffix = f" — {row.countdown}" if row.countdown else ""
                typer.echo(f"  [{row.kind:>13}] {row.label} ({row.detail}){suffix}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.exception("family-scenario status failed")
        typer.echo("Error: family-scenario status failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def reset(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Confirm deletion")] = False,
    include_children: Annotated[
        bool,
        typer.Option("--include-children", help="Also soft-delete child dwellers (default: keep them)"),
    ] = False,
) -> None:
    """Remove all relationships and pregnancies for the vault (children optional)."""

    async def _run() -> None:
        if not yes:
            typer.echo("This deletes all relationships and pregnancies for the vault. Pass --yes to confirm.")
            raise typer.Exit(code=1)

        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            counts = await family_scenario_service.reset(session, vault_id, include_children=include_children)
            typer.echo(
                f"Removed {counts['relationships']} relationships, {counts['pregnancies']} pregnancies, "
                f"{counts['children']} children."
            )

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("family-scenario reset failed")
        typer.echo("Error: family-scenario reset failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
