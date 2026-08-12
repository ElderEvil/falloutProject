"""
Memory usage benchmark for FastAPI dependency graph.

Measures RSS at startup and after a realistic API workload.
Focuses on the dependency graph memory that 0.140.0 optimized.
"""

import gc
import os
import sys
import time
import tracemalloc
from pathlib import Path

# ── Ensure the app package is importable ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["ASYNC_DATABASE_URI"] = "sqlite+aiosqlite:///./test_bench.db"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["SECRET_KEY"] = "benchmark-secret-key-not-for-production"
os.environ["FIRST_SUPERUSER"] = "admin@example.com"
os.environ["FIRST_SUPERUSER_PASSWORD"] = "bench-password"
os.environ["PROJECT_NAME"] = "Benchmark"
os.environ["ENVIRONMENT"] = "test"


def get_rss() -> int:
    """Return RSS in bytes from /proc/self/status."""
    with Path("/proc/self/status").open() as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024  # kB → bytes
    return 0


def fmt_mb(b: int) -> str:
    return f"{b / 1024 / 1024:.2f} MB"


def measure_dependency_graph_memory() -> float:
    """Use tracemalloc to snapshot memory held by Dependant/cache_key objects."""
    tracemalloc.start()
    gc.collect()

    # Force import of the heavy dependency modules
    from fastapi import Depends, FastAPI
    from fastapi.dependencies.models import Dependant

    app = FastAPI()

    # Register endpoints with various dependency patterns
    for i in range(50):
        # Create endpoints with nested deps to expand the dependency graph
        async def dep_a(i=i) -> dict[str, int]:
            return {"a": i}

        async def dep_b(d: dict[str, int] = Depends(dep_a), i=i) -> dict[str, int]:
            return {**d, "b": i}

        async def dep_c(d: dict[str, int] = Depends(dep_b), i=i) -> dict[str, int]:
            return {**d, "c": i}

        async def handler(d: dict[str, int] = Depends(dep_c), i=i) -> dict[str, int]:
            return d

        app.get(f"/endpoint-{i}")(handler)

    gc.collect()
    snapshot = tracemalloc.take_snapshot()

    # Filter to fastapi internals
    stats = snapshot.statistics("lineno")
    dep_memory = 0
    for stat in stats:
        if "fastapi/dependencies" in stat.traceback[0].filename or "fastapi/routing" in stat.traceback[0].filename:
            dep_memory += stat.size

    tracemalloc.stop()
    return dep_memory


def benchmark() -> dict:
    results = {}

    # ── 1. Baseline RSS before any FastAPI import ─────────────────────────
    gc.collect()
    time.sleep(0.5)
    results["rss_before_import"] = get_rss()

    # ── 2. Import FastAPI and measure RSS ─────────────────────────────────
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    gc.collect()
    time.sleep(0.5)
    results["rss_after_import"] = get_rss()

    # ── 3. Create app with many routes and dependencies ───────────────────
    from fastapi import Depends

    app = FastAPI(title="Benchmark", version="0.1.0")

    # Register 50 endpoints with dependency chains (2-3 levels deep)
    for i in range(50):

        async def level_1(i=i) -> dict[str, int]:
            return {"l1": i}

        async def level_2(d: dict[str, int] = Depends(level_1), i=i) -> dict[str, int]:
            return {"l1": d["l1"], "l2": i}

        async def final_handler(d: dict[str, int] = Depends(level_2)) -> dict[str, int]:
            return d

        app.get(f"/chain-{i}")(final_handler)

    # Register 20 endpoints without deps for baseline comparison
    for i in range(20):

        async def no_dep_handler(i=i) -> dict[str, int]:
            return {"no_dep": i}

        app.get(f"/simple-{i}")(no_dep_handler)

    gc.collect()
    time.sleep(0.5)
    results["rss_after_app_build"] = get_rss()

    # ── 4. After handling requests ────────────────────────────────────────
    client = TestClient(app)

    # Hit each endpoint a few times to warm up dependency cache
    for _ in range(3):
        for i in range(50):
            r = client.get(f"/chain-{i}")
            r.raise_for_status()
        for i in range(20):
            r = client.get(f"/simple-{i}")
            r.raise_for_status()

    gc.collect()
    time.sleep(0.5)
    results["rss_after_requests"] = get_rss()

    # ── 5. Tracemalloc: dependency graph memory ───────────────────────────
    dep_graph_mem = measure_dependency_graph_memory()
    results["dependency_graph_memory"] = dep_graph_mem

    return results


if __name__ == "__main__":
    import json

    print("Running memory benchmark...")
    results = benchmark()

    print("\n─── Memory Benchmark Results ───")
    print(f"  RSS before import:            {fmt_mb(results['rss_before_import'])}")
    print(f"  RSS after import:             {fmt_mb(results['rss_after_import'])}")
    print(f"  RSS after app build:          {fmt_mb(results['rss_after_app_build'])}")
    print(f"  RSS after 210 requests:       {fmt_mb(results['rss_after_requests'])}")
    print(f"  Dependency graph (tracemalloc): {fmt_mb(results['dependency_graph_memory'])}")

    print(f"\n  Import overhead:              {fmt_mb(results['rss_after_import'] - results['rss_before_import'])}")
    print(f"  App build overhead:            {fmt_mb(results['rss_after_app_build'] - results['rss_after_import'])}")
    print(f"  Request handling overhead:     {fmt_mb(results['rss_after_requests'] - results['rss_after_app_build'])}")
    print("─────────────────────────────────")

    results_fmt = {k: fmt_mb(v) if isinstance(v, int) else v for k, v in results.items()}
    print(f"\nJSON: {json.dumps(results_fmt, indent=2)}")
