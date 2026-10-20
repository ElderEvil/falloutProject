"""Explicit, guarded baseline adoption; independent of application startup."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated, Any

import typer
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

BACKEND = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("baseline_versions") / "baseline_b7e3d9c1a5f2.json"
app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
logger = logging.getLogger(__name__)


def schema_state(connection: Connection) -> dict[str, list[list[Any]]]:
    """Read PostgreSQL details that Alembic autogenerate may omit."""
    queries = {
        "columns": (
            "SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), "
            "a.attnotnull, pg_get_expr(d.adbin, d.adrelid) "
            "FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
            "AND a.attnum > 0 AND NOT a.attisdropped ORDER BY c.relname, a.attnum"
        ),
        "constraints": (
            "SELECT c.relname, con.conname, pg_get_constraintdef(con.oid) "
            "FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' ORDER BY c.relname, con.conname"
        ),
        "indexes": (
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' ORDER BY tablename, indexname"
        ),
        "enums": (
            "SELECT t.typname, e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE n.nspname = 'public' ORDER BY t.typname, e.enumsortorder"
        ),
    }
    return {name: [list(row) for row in connection.execute(text(query))] for name, query in queries.items()}


def _head(config_name: str) -> str:
    config = Config(str(BACKEND / config_name))
    config.set_main_option("script_location", str(BACKEND / "app/alembic"))
    revision = ScriptDirectory.from_config(config).get_current_head()
    if revision is None:
        raise RuntimeError(f"No head in {config_name}")
    return revision


async def inspect_database(database: str, *, apply: bool = False, freeze: bool = False) -> dict[str, Any]:
    """Check the named target, optionally recording its baseline marker atomically."""
    url = make_url(str(settings.ASYNC_DATABASE_URI))
    if url.database != database:
        raise RuntimeError("Configured database does not match --database; check POSTGRES_DB and ASYNC_DATABASE_URI.")
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            if not apply:
                await connection.execute(text("SET TRANSACTION READ ONLY"))
            await connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            await connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            exists = await connection.scalar(text("SELECT to_regclass('public.alembic_version') IS NOT NULL"))
            if not exists:
                raise RuntimeError("No Alembic version table; initialize an empty database with upgrade, not adoption.")
            if apply:
                # Maintenance stops application writers. These locks also prevent a
                # concurrent writer from changing tables while verification/stamping runs.
                tables = await connection.scalars(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
                )
                for table in tables:
                    quoted = connection.dialect.identifier_preparer.quote_identifier(table)
                    await connection.execute(text(f"LOCK TABLE public.{quoted} IN EXCLUSIVE MODE"))
            revisions = list(await connection.scalars(text("SELECT version_num FROM public.alembic_version")))
            major = int(await connection.scalar(text("SHOW server_version_num")) or 0) // 10000
            schema = await connection.run_sync(schema_state)
            if freeze:
                legacy = _head("alembic.ini")
                if revisions != [legacy]:
                    raise RuntimeError("Reference database must be at the single current legacy head.")
                return {
                    "legacy_revision": legacy,
                    "baseline_revision": _head("alembic-squash.ini"),
                    "postgres_major": major,
                    "schema": schema,
                }
            manifest = json.loads(MANIFEST.read_text())
            baseline = manifest["baseline_revision"]
            if baseline != _head("alembic-squash.ini"):
                raise RuntimeError("Manifest and baseline head differ; regenerate and rehearse the release artifacts.")
            if major != manifest["postgres_major"]:
                raise RuntimeError("PostgreSQL major differs from the rehearsed reference.")
            if revisions not in ([manifest["legacy_revision"]], [baseline]):
                raise RuntimeError(
                    "Database is not at the frozen legacy head or baseline; finish legacy upgrades first."
                )
            changed = [name for name, rows in manifest["schema"].items() if schema[name] != rows]
            if changed:
                raise RuntimeError(
                    f"Schema drift in {', '.join(changed)}; adoption refused. Reconcile and rehearse first."
                )
            if apply and revisions != [baseline]:
                result = await connection.execute(
                    text("UPDATE public.alembic_version SET version_num = :baseline WHERE version_num = :legacy"),
                    {"baseline": baseline, "legacy": manifest["legacy_revision"]},
                )
                if result.rowcount != 1:
                    raise RuntimeError("Revision changed during adoption; no stamp committed.")
            return {"database": database, "baseline": baseline, "applied": apply, "schema_matches": True}
    finally:
        await engine.dispose()


def _run(database: str, *, apply: bool = False, freeze: bool = False) -> dict[str, Any]:
    try:
        return asyncio.run(inspect_database(database, apply=apply, freeze=freeze))
    except (RuntimeError, SQLAlchemyError) as exc:
        if isinstance(exc, SQLAlchemyError):
            logger.exception("Baseline database operation failed")
            message = "Database operation failed; no stamp committed. See logs for details."
        else:
            message = str(exc)
        typer.echo(message, err=True)
        raise typer.Exit(code=1) from None


@app.command()
def check(database: Annotated[str, typer.Option(help="Must match the configured database name")]) -> None:
    """Read-only check against the frozen schema; never stamp or run backfills."""
    typer.echo(json.dumps(_run(database), indent=2))


@app.command()
def adopt(
    database: Annotated[str, typer.Option(help="Must match the configured database name")],
    apply: Annotated[bool, typer.Option(help="Record the marker after verification; requires stopped writers")] = False,
) -> None:
    """Check by default; --apply changes only the version marker in one transaction."""
    typer.echo(json.dumps(_run(database, apply=apply), indent=2))


@app.command()
def freeze(
    database: Annotated[str, typer.Option(help="Empty reference database upgraded through the legacy history")],
    output: Annotated[Path, typer.Option(help="New manifest file; refuses to overwrite an existing artifact")],
) -> None:
    """Write a release manifest after replaying the final legacy chain."""
    result = _run(database, freeze=True)
    with output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    typer.echo(f"Wrote {output}")


if __name__ == "__main__":
    app()
