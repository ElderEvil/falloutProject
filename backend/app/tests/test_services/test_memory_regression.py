"""Memory regression test — detects unexpected RSS growth.

Measures RSS at startup and after a realistic API workload.
Serves as a guard rail against dependency-graph memory regressions
like the one fixed in FastAPI 0.140.0 (PR #16049).

Run with:
    pytest app/tests/test_services/test_memory_regression.py -v --tb=short

This test is tagged as ``slow`` — it takes ~10 s because it spins up
a TestClient and fires 70+ requests.
"""

from pathlib import Path

import pytest

# ── Mark as slow ────────────────────────────────────────────────────
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not Path("/proc/self/status").exists(),
        reason="RSS measurement requires /proc (Linux only)",
    ),
]


def get_rss_mb() -> float:
    """Return RSS in MB from /proc/self/status."""
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024  # kB → MB
    return 0.0


@pytest.fixture(scope="module")
def _app_and_client() -> tuple:
    """Build a FastAPI app with a large dependency graph and return a TestClient.

    Captures RSS baseline before/after the app is built and asserts that
    constructing the dependency graph does not balloon memory.
    """
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    rss_before = get_rss_mb()

    app = FastAPI(title="MemRegression", version="0.1.0")

    # ── 50 endpoints with 3-deep dependency chains ──────────────────
    for i in range(50):

        async def level_1(i=i) -> dict[str, int]:
            return {"l1": i}

        async def level_2(d: dict[str, int] = Depends(level_1), i=i) -> dict[str, int]:
            return {"l1": d["l1"], "l2": i}

        async def final_handler(d: dict[str, int] = Depends(level_2)) -> dict[str, int]:
            return d

        app.get(f"/chain-{i}")(final_handler)

    # ── 20 simple endpoints (no deps) ───────────────────────────────
    for i in range(20):

        async def no_dep_handler(i=i) -> dict[str, int]:
            return {"no_dep": i}

        app.get(f"/simple-{i}")(no_dep_handler)

    rss_after = get_rss_mb()
    growth = rss_after - rss_before
    # App build should add at most 10 MB (typical overhead is <1 MB standalone,
    # higher inside pytest because of already-loaded conftest modules).
    assert growth < 10.0, (
        f"App build RSS grew {growth:.1f} MB ({rss_before:.1f} → {rss_after:.1f}), exceeds 10 MB limit"
    )

    return app, TestClient(app)


class TestMemoryRegression:
    """Guard against dependency-graph memory leaks."""

    # ── Configurable thresholds ─────────────────────────────────────
    # RSS is measured inside pytest which already loaded the full app,
    # so absolute values include all imports + conftest fixtures.
    # The growth test is the meaningful regression detector.
    RSS_GROWTH_MAX = 15.0  # MB — request handling should not balloon

    def test_rss_growth_after_requests(self, _app_and_client):  # noqa: PT019 — value IS used below
        """RSS should not grow excessively after handling 200+ requests."""
        _app, client = _app_and_client
        rss_before = get_rss_mb()

        # Hit each endpoint 3 times = 210 requests
        for _ in range(3):
            for i in range(50):
                r = client.get(f"/chain-{i}")
                assert r.status_code == 200
            for i in range(20):
                r = client.get(f"/simple-{i}")
                assert r.status_code == 200

        rss_after = get_rss_mb()
        growth = rss_after - rss_before

        assert growth < self.RSS_GROWTH_MAX, (
            f"RSS grew {growth:.1f} MB ({rss_before:.1f} → {rss_after:.1f}), exceeds limit {self.RSS_GROWTH_MAX} MB"
        )

    def test_dependency_endpoints_respond_correctly(self, _app_and_client):  # noqa: PT019
        """Verify dependency-chained endpoints return correct values."""
        _, client = _app_and_client
        r = client.get("/chain-0")
        assert r.status_code == 200
        assert r.json() == {"l1": 0, "l2": 0}

        r = client.get("/chain-49")
        assert r.status_code == 200
        assert r.json() == {"l1": 49, "l2": 49}

    def test_simple_endpoints_respond_correctly(self, _app_and_client):  # noqa: PT019
        """Verify simple endpoints work."""
        _, client = _app_and_client
        r = client.get("/simple-0")
        assert r.status_code == 200
        assert r.json() == {"no_dep": 0}

        r = client.get("/simple-19")
        assert r.status_code == 200
        assert r.json() == {"no_dep": 19}
