#!/usr/bin/env python3
"""Dependency-major performance baseline for the v3.1 upgrade set.

Captures repeatable "before" numbers for each tool in the 3.1 milestone
(Pydantic v3, HTTPX 2 / httpx2, websockets, Logfire, multidict, soupsieve,
Python, uvloop/zuvloop) so that each upgrade can be re-measured with an
identical command and compared.

It reuses, rather than reinvents, the repo's existing signals:
  - the full-app import surface + smoke env of ``scripts/check_backend_image.py``
  - the RSS reader from ``app/tests/test_services/test_memory_regression.py``
The runtime rows that need live infra (tick p50, API latency, DB connections,
image size) are *not* measured here; they are recorded from the existing
harnesses documented in ``docs/plans/2026-11-11-3.1-dependency-baseline.md``.

Run from the backend project so the venv interpreter is used:

    cd backend && uv run python ../scripts/dep-baseline.py \
        --out ../scripts/scenario_output/dep-baseline.json

Every measurement runs in a fresh interpreter (subprocess) so import order and
warm caches do not contaminate the next value.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Isolated import-time probes: name -> importable module.
IMPORT_PROBES: dict[str, str] = {
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic_settings",
    "fastapi": "fastapi",
    "sqlmodel": "sqlmodel",
    "sqlalchemy": "sqlalchemy",
    "httpx": "httpx",
    "httpx2": "httpx2",
    "logfire": "logfire",
    "websockets": "websockets",
    "multidict": "multidict",
    "soupsieve": "soupsieve",
    "uvloop": "uvloop",
    "dramatiq": "dramatiq",
    "redis": "redis",
    "asyncpg": "asyncpg",
}

# Env-only configuration mirroring scripts/check_backend_image.py, so the app
# import surface can be measured without a database or network.
SMOKE_ENV: dict[str, str] = {
    "SECRET_KEY": "dep-baseline-key",
    "EMAIL_TEST_USER": "test@example.com",
    "FIRST_SUPERUSER_USERNAME": "admin",
    "FIRST_SUPERUSER_EMAIL": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "dep-baseline-password",
    "USERS_OPEN_REGISTRATION": "false",
    "POSTGRES_SERVER": "localhost",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
    "POSTGRES_DB": "fallout",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "LOGFIRE_SEND_TO_LOGFIRE": "false",
}

# A representative API read model: nested list, enum, UUID, aware datetime and
# constrained fields. Kept inline so the probe measures the library hot path
# identically across pydantic majors without importing app config.
PYDANTIC_BENCH = """
import json, time, uuid
from datetime import UTC, datetime
from enum import StrEnum
from pydantic import BaseModel, Field

class Rarity(StrEnum):
    COMMON = "common"
    RARE = "rare"

class Item(BaseModel):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    rarity: Rarity
    value: int = Field(ge=0, le=100000)

class Dweller(BaseModel):
    id: uuid.UUID
    name: str
    level: int = Field(ge=1, le=100)
    created_at: datetime
    is_child: bool
    items: list[Item]

payload = {
    "id": str(uuid.uuid4()),
    "name": "Overseer",
    "level": 42,
    "created_at": datetime.now(UTC).isoformat(),
    "is_child": False,
    "items": [
        {"id": str(uuid.uuid4()), "name": f"item-{i}", "rarity": "rare" if i % 2 else "common", "value": i}
        for i in range(20)
    ],
}

N = 2000
Dweller.model_validate(payload)  # warm
t = time.perf_counter()
for _ in range(N):
    Dweller.model_validate(payload)
validate_us = (time.perf_counter() - t) / N * 1e6
print(json.dumps({"validate_us": validate_us}))
"""

# Full app import surface (whole-graph cost: fastapi + sqlmodel + pydantic +
# logfire + httpx + websockets + ...) plus RSS after import.
APP_IMPORT_BENCH = """
import json, time
from pathlib import Path

def rss_mb():
    for line in Path("/proc/self/status").open():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0

t = time.perf_counter()
for module in ("main", "app.api.tasks"):
    __import__(module)
__import__("pydantic_ai.models.typesafe")
import_ms = (time.perf_counter() - t) * 1000.0
print(json.dumps({"import_ms": import_ms, "rss_mb": rss_mb()}))
"""


def _run_json(code: str, env: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Run ``python -c code`` in a fresh interpreter and parse its last stdout line as JSON."""
    # Fixed argv: our own interpreter running repo-local probe code.
    proc = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        return None
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    if not lines:
        return None
    return json.loads(lines[-1])


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def measure_imports(repeats: int) -> dict[str, Any]:
    """Isolated per-package import time (median of ``repeats``)."""
    results: dict[str, Any] = {}
    for label, module in IMPORT_PROBES.items():
        samples: list[float] = []
        for _ in range(repeats):
            out = _run_json(
                "import json, time\n"
                f"t = time.perf_counter()\nimport {module}\n"
                "print(json.dumps({'ms': (time.perf_counter() - t) * 1000}))"
            )
            if out is not None:
                samples.append(out["ms"])
        results[label] = _median(samples)
    return results


def measure_interpreter(repeats: int) -> float | None:
    """Cold interpreter startup time, median of ``repeats``."""
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        subprocess.run([sys.executable, "-c", "pass"], check=True, capture_output=True)
        samples.append((time.perf_counter() - started) * 1000.0)
    return _median(samples)


def main() -> None:
    """Parse args, capture the baseline report, and print/write it as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="write the JSON report here")
    parser.add_argument("--repeat", type=int, default=5, help="samples per isolated probe")
    args = parser.parse_args()

    env = {**os.environ, **SMOKE_ENV}
    report: dict[str, Any] = {
        "captured_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "repeats": args.repeat,
        "import_ms": measure_imports(args.repeat),
        "interpreter_startup_ms": measure_interpreter(args.repeat),
        "app_import": _run_json(APP_IMPORT_BENCH, env=env),
        "pydantic_validate_us": None,
    }
    bench = _run_json(PYDANTIC_BENCH)
    if bench is not None:
        report["pydantic_validate_us"] = round(bench["validate_us"], 3)

    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
        print(f"\nWrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
