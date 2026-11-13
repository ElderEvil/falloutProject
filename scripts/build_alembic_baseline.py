#!/usr/bin/env python3
"""Regenerate the opt-in Alembic baseline from the legacy migration graph.

Replays the legacy graph into a scratch PostgreSQL database, dumps the schema and
migration-owned seeds, rewrites the baseline SQL/revision/manifest, and updates the
manifest path and regression-test constants. It never commits and only touches the
scratch database it creates or explicitly reuses.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import NoReturn
from urllib.parse import quote, urlparse

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
VERSIONS = BACKEND / "app/alembic/baseline_versions"
TOOLS = BACKEND / "app/alembic/baseline_tools.py"
TEST = BACKEND / "app/tests/test_alembic/test_baseline_experiment.py"


def _die(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)  # ruff: ignore[subprocess-without-shell-equals-true]


def _capture(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> str:
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        command, cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return result.stdout


def _detect_container(engine: str) -> str:
    output = _capture([engine, "ps", "--format", "{{.Names}}\t{{.Image}}"])
    candidates = []
    for line in output.splitlines():
        name, _, image = line.partition("\t")
        if "postgres" in image.lower():
            candidates.append(name)
    if not candidates:
        _die(
            f"no running PostgreSQL container found via {engine}; pass --container or install psql/pg_dump"
        )
    return candidates[0]


class _Client:
    def __init__(
        self, *, engine: str | None, container: str | None, env: dict[str, str]
    ) -> None:
        self.env = env
        self.user = env.get("POSTGRES_USER", "postgres")
        uri = env.get("ASYNC_DATABASE_URI", "")
        self.database = (
            urlparse(uri).path.lstrip("/")
            if uri
            else env.get("POSTGRES_DB", "fallout_db")
        )
        self.host = env.get("POSTGRES_SERVER", "localhost")
        self.port = env.get("POSTGRES_PORT", "5432")
        self.direct = (
            shutil.which("psql") is not None and shutil.which("pg_dump") is not None
        )
        self.engine = engine
        self.container = container
        if not self.direct:
            if engine is None:
                _die("psql/pg_dump are not installed and no container engine was found")
            self.container = container or _detect_container(engine)

    def _pg_env(self) -> dict[str, str]:
        env = {**os.environ, **self.env}
        password = self.env.get("POSTGRES_PASSWORD")
        if password:
            env["PGPASSWORD"] = password
        return env

    def _command(self, program: str, database: str) -> list[str]:
        if self.direct:
            command = [program, "-h", self.host, "-p", self.port]
        else:
            command = [self.engine or "podman", "exec", self.container or "", program]
        return [*command, "-U", self.user, "-d", database]

    def _psql(self, sql: str, *, database: str | None = None) -> str:
        command = self._command("psql", database or self.database)
        return _capture(
            [*command, "-v", "ON_ERROR_STOP=1", "-tAc", sql],
            env=self._pg_env() if self.direct else None,
        )

    def _database_exists(self, name: str) -> bool:
        return (
            name
            in self._psql(
                "SELECT datname FROM pg_database", database="postgres"
            ).splitlines()
        )

    def _dump(self, args: list[str], *, database: str) -> bytes:
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [*self._command("pg_dump", database), *args],
            env=self._pg_env() if self.direct else None,
            capture_output=True,
            check=True,
        )
        return result.stdout


def _clean_dump(lines: list[str], item_check: str | None) -> list[str]:
    out: list[str] = []
    skip_table = False
    for line in lines:
        stripped = line.rstrip()
        if skip_table:
            if stripped.endswith((");", ";")):
                skip_table = False
            continue
        if stripped.startswith("CREATE TABLE public.alembic_version"):
            skip_table = True
            continue
        if stripped.startswith("ALTER TABLE ONLY public.alembic_version"):
            if not stripped.endswith(";"):
                skip_table = True
            continue
        if not stripped.strip():
            continue
        if stripped.startswith(("--", "\\")):
            continue
        if stripped.startswith(("SET ", "SELECT pg_catalog.")):
            continue
        if stripped.strip() == "CREATE SCHEMA public;":
            continue
        if item_check and stripped.startswith(
            "    CONSTRAINT ck_item_item_type CHECK ("
        ):
            out.append(item_check)
            continue
        out.append(stripped)
    return out


def _item_type_check(client: _Client, database: str) -> str | None:
    definition = client._psql(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'ck_item_item_type' AND conrelid = 'public.item'::regclass",
        database=database,
    ).strip()
    values = re.findall(r"'([^']+)'::character varying", definition)
    if not values:
        return None
    joined = ", ".join(f"'{value}'" for value in values)
    return f"    CONSTRAINT ck_item_item_type CHECK (item_type IN ({joined}))"


def _existing_revision() -> tuple[Path, str]:
    revisions = sorted(VERSIONS.glob("*_baseline.py"))
    if len(revisions) != 1:
        _die(
            f"expected exactly one baseline revision in {VERSIONS}, found {len(revisions)}"
        )
    path = revisions[0]
    match = re.search(
        r'^revision = "squash_([0-9a-f]+)"$',
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not match:
        _die(f"cannot read the baseline revision id from {path}")
    return path, match.group(1)


def _validate_target(database: str, app_database: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        _die(f"invalid database name: {database!r}")
    if len(database.encode("utf-8")) > 63:
        _die(
            f"database name exceeds PostgreSQL's 63-byte identifier limit: {database!r}"
        )
    if database == app_database:
        _die(
            f"refusing to use the configured application database ({app_database!r}) "
            "as the scratch target; pass a different --database"
        )
    if database in {"postgres", "template0", "template1"}:
        _die(f"refusing to use the system database {database!r} as the scratch target")


def _scratch_uri(client: _Client, database: str) -> str:
    password = client.env.get("POSTGRES_PASSWORD", "")
    user = quote(client.user, safe="")
    auth = f"{user}:{quote(password, safe='')}@" if password else f"{user}@"
    port = f":{client.port}" if client.port else ""
    return f"postgresql+asyncpg://{auth}{client.host}{port}/{database}"


def _snapshot(paths: set[Path]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)


def _prepare_target(
    client: _Client,
    database: str,
    *,
    skip_migrations: bool,
    migration_env: dict[str, str],
) -> None:
    if skip_migrations:
        if not client._database_exists(database):
            _die(
                f"database {database!r} does not exist; omit --skip-migrations to create it"
            )
        return
    client._psql(
        f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)', database="postgres"
    )
    client._psql(
        f'CREATE DATABASE "{database}" OWNER "{client.user}"', database="postgres"
    )
    _run(
        ["uv", "run", "alembic", "-c", "alembic-legacy.ini", "upgrade", "head"],
        cwd=BACKEND,
        env=migration_env,
    )


def _publish(
    *,
    target_sql: Path,
    target_manifest: Path,
    target_revision: Path,
    revision_path: Path,
    old_head: str,
    head: str,
    sql: str,
    revision_text: str,
    tools_text: str,
    test_text: str,
    freeze: Callable[[], str],
    tools_path: Path = TOOLS,
    test_path: Path = TEST,
    versions_dir: Path = VERSIONS,
) -> None:
    affected = {
        target_sql,
        target_manifest,
        target_revision,
        revision_path,
        tools_path,
        test_path,
    }
    stale_paths = (
        {versions_dir / f"baseline_{old_head}.{suffix}" for suffix in ("sql", "json")}
        if old_head != head
        else set()
    )
    snapshot = _snapshot(affected | stale_paths)
    try:
        target_sql.write_text(sql, encoding="utf-8")
        target_revision.write_text(revision_text, encoding="utf-8")
        if old_head != head and revision_path != target_revision:
            revision_path.unlink()
        target_manifest.write_text(freeze(), encoding="utf-8")
        tools_path.write_text(tools_text, encoding="utf-8")
        test_path.write_text(test_text, encoding="utf-8")
        for stale in stale_paths:
            stale.unlink(missing_ok=True)
    except BaseException:
        _restore(snapshot)
        raise


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", default="fallout_baseline_ref", help="scratch database name"
    )
    parser.add_argument(
        "--container", help="running PostgreSQL container to exec psql/pg_dump in"
    )
    parser.add_argument(
        "--engine", choices=["podman", "docker"], help="container engine"
    )
    parser.add_argument("--keep", action="store_true", help="keep the scratch database")
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="reuse an existing scratch database at the legacy head",
    )
    args = parser.parse_args()

    engine = args.engine
    if engine is None:
        engine = (
            "podman"
            if shutil.which("podman")
            else "docker"
            if shutil.which("docker")
            else None
        )
    env = {
        **_load_env_file(BACKEND / ".env"),
        **{
            k: v
            for k, v in os.environ.items()
            if k.startswith("POSTGRES_") or k == "ASYNC_DATABASE_URI"
        },
    }
    client = _Client(engine=engine, container=args.container, env=env)
    database = args.database
    migration_env = {
        **os.environ,
        **env,
        "POSTGRES_DB": database,
        "ASYNC_DATABASE_URI": _scratch_uri(client, database),
    }

    _validate_target(database, client.database)
    created = not args.skip_migrations
    revision_path, old_head = _existing_revision()
    try:
        _prepare_target(
            client,
            database,
            skip_migrations=args.skip_migrations,
            migration_env=migration_env,
        )
        head = client._psql(
            "SELECT version_num FROM alembic_version", database=database
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{6,}", head):
            _die(f"unexpected legacy head: {head!r}")
        heads = _capture(
            ["uv", "run", "alembic", "-c", "alembic-legacy.ini", "heads"],
            cwd=BACKEND,
            env=migration_env,
        ).strip()
        if heads.count("(head)") != 1 or head not in heads:
            _die(f"legacy graph does not have a single applied head: {heads!r}")

        item_check = _item_type_check(client, database)
        if item_check is None:
            print("warning: ck_item_item_type not found; keeping the dumped definition")
        schema = _clean_dump(
            client._dump(
                ["--schema-only", "--no-owner", "--no-privileges", "--schema=public"],
                database=database,
            )
            .decode()
            .splitlines(),
            item_check,
        )
        seeds = _clean_dump(
            client._dump(
                [
                    "--data-only",
                    "--inserts",
                    "--no-owner",
                    "--no-privileges",
                    "--table=public.objective",
                    "--table=public.prompt",
                ],
                database=database,
            )
            .decode()
            .splitlines(),
            None,
        )
        sql = "\n".join(schema + seeds) + "\n"

        revision_text = revision_path.read_text(encoding="utf-8")
        revision_text = revision_text.replace(f"squash_{old_head}", f"squash_{head}")
        revision_text = revision_text.replace(
            f"baseline_{old_head}.sql", f"baseline_{head}.sql"
        )
        revision_text = revision_text.replace(f"through {old_head}", f"through {head}")
        if old_head == head:
            target_revision = revision_path
        else:
            target_revision = (
                VERSIONS / f"{date.today():%Y_%m_%d}_0001-squash_{head}_baseline.py"
            )

        tools_text = TOOLS.read_text(encoding="utf-8")
        tools_text = re.sub(
            r'MANIFEST = Path\(__file__\)\.with_name\("baseline_versions"\) / "baseline_[0-9a-f]+\.json"',
            f'MANIFEST = Path(__file__).with_name("baseline_versions") / "baseline_{head}.json"',
            tools_text,
        )
        test_text = TEST.read_text(encoding="utf-8")
        test_text = re.sub(
            r'BASELINE = "squash_[0-9a-f]+"', f'BASELINE = "squash_{head}"', test_text
        )
        test_text = re.sub(
            r'LEGACY_HEAD = "[0-9a-f]+"', f'LEGACY_HEAD = "{head}"', test_text
        )

        target_sql = VERSIONS / f"baseline_{head}.sql"
        target_manifest = VERSIONS / f"baseline_{head}.json"

        def freeze() -> str:
            with tempfile.TemporaryDirectory() as tmp:
                temp_manifest = Path(tmp) / "manifest.json"
                _run(
                    [
                        "uv",
                        "run",
                        "python",
                        "-m",
                        "app.alembic.baseline_tools",
                        "freeze",
                        "--database",
                        database,
                        "--output",
                        str(temp_manifest),
                    ],
                    cwd=BACKEND,
                    env=migration_env,
                )
                return temp_manifest.read_text(encoding="utf-8")

        _publish(
            target_sql=target_sql,
            target_manifest=target_manifest,
            target_revision=target_revision,
            revision_path=revision_path,
            old_head=old_head,
            head=head,
            sql=sql,
            revision_text=revision_text,
            tools_text=tools_text,
            test_text=test_text,
            freeze=freeze,
        )

        tables = sum(1 for line in schema if line.startswith("CREATE TABLE"))
        enums = sum(1 for line in schema if line.startswith("CREATE TYPE"))
        indexes = sum(
            1
            for line in schema
            if line.startswith(("CREATE INDEX", "CREATE UNIQUE INDEX"))
        )
        inserts = sum(1 for line in seeds if line.startswith("INSERT INTO"))
        print(f"legacy head: {head}")
        print(f"baseline: {target_revision.name}")
        print(f"sql: {target_sql.name} ({len(schema) + len(seeds)} lines)")
        print(f"manifest: {target_manifest.name}")
        print(
            f"schema: tables={tables} enums={enums} indexes={indexes} seeds={inserts}"
        )
        print(
            "next: run uv run pytest app/tests/test_alembic/test_baseline_experiment.py"
        )
    finally:
        if not created:
            print(f"reused database: {database}")
        elif not args.keep:
            client._psql(
                f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)',
                database="postgres",
            )
        else:
            print(f"kept database: {database}")


if __name__ == "__main__":
    _main()
