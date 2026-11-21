"""Tests for ``scripts/size-report.py``.

The script is a policy instrument: its category definitions decide whether the repo is inside or
outside the advisory budget, so the classification and the numstat accounting are pinned here.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "size-report.py"


def load_script() -> ModuleType:
    """Import the hyphenated script by path.

    The module must be registered before execution: `@dataclass` resolves its own module's namespace
    through `sys.modules` and fails with `NoneType` when the entry is missing.
    """
    spec = importlib.util.spec_from_file_location("size_report", SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["size_report"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report() -> ModuleType:
    return load_script()


def test_categories_keep_schema_history_out_of_production(report: ModuleType) -> None:
    """Migrations and tests are their own categories; catalog data is not production."""
    grouped = report.category_paths(
        [
            "backend/app/services/room_service.py",
            "backend/app/alembic/baseline_versions/x_add_rooms.py",
            "backend/app/tests/test_services/test_room_service.py",
            "backend/app/data/quests/single_stage/power_struggle.json",
            "frontend/src/modules/rooms/stores/rooms.ts",
            "frontend/src/core/types/api.generated.ts",
            "frontend/tests/unit/stores/rooms.test.ts",
        ]
    )

    assert grouped[report.BACKEND_PRODUCTION] == ["backend/app/services/room_service.py"]
    assert grouped[report.BACKEND_MIGRATIONS] == ["backend/app/alembic/baseline_versions/x_add_rooms.py"]
    assert grouped[report.BACKEND_CATALOG] == ["backend/app/data/quests/single_stage/power_struggle.json"]
    assert grouped[report.FRONTEND_PRODUCTION] == ["frontend/src/modules/rooms/stores/rooms.ts"]
    assert grouped[report.FRONTEND_GENERATED] == ["frontend/src/core/types/api.generated.ts"]
    assert grouped[report.FRONTEND_TESTS] == ["frontend/tests/unit/stores/rooms.test.ts"]


def test_ratio_survives_an_empty_denominator(report: ModuleType) -> None:
    """A ref with no production files must not raise ZeroDivisionError."""
    assert report.ratio(10, 0) == 0.0
    assert report.ratio(10, 4) == 2.5


def test_delta_sign_and_zero(report: ModuleType) -> None:
    """Zero stays unsigned; growth carries an explicit plus."""
    assert report.format_delta(0) == "0"
    assert report.format_delta(1388) == "+1,388"
    assert report.format_delta(-6) == "-6"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - literal git arguments in a test helper
        [shutil.which("git") or "git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_renamed_file_credits_its_new_path(report: ModuleType, tmp_path: Path) -> None:
    """A rename is attributed to the new path, not silently dropped."""
    repo = tmp_path / "repo"
    service = repo / "backend" / "app" / "services"
    service.mkdir(parents=True)
    _git(repo, "init", "-q")
    (service / "old_service.py").write_text("a = 1\nb = 2\nc = 3\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "mv", "backend/app/services/old_service.py", "backend/app/services/new_service.py")
    with (service / "new_service.py").open("a") as handle:
        handle.write("d = 4\ne = 5\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "rename and extend")

    categories = {
        report.BACKEND_PRODUCTION: ["backend/app/services/new_service.py"],
        report.BACKEND_MIGRATIONS: [],
        report.BACKEND_TESTS: [],
        report.FRONTEND_PRODUCTION: [],
        report.FRONTEND_GENERATED: [],
        report.FRONTEND_TESTS: [],
        report.BACKEND_CATALOG: [],
        report.FRONTEND_CATALOG: [],
    }
    added = report.added_lines(repo, "HEAD~1", "HEAD", categories)

    assert added[report.BACKEND_PRODUCTION] == 2


def test_report_prints_per_side_rows_beside_the_targets(report: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    """Backend and frontend production print as separate rows, not only as a sum."""
    snapshot = report.Snapshot(
        ref="HEAD",
        lines=dict.fromkeys(report.CATEGORY_ORDER, 0),
        files=dict.fromkeys(report.CATEGORY_ORDER, 0),
        modules=0,
        feature_docs=0,
        migrations=0,
        large_files=[],
    )
    built = report.Report(
        base=snapshot,
        head=snapshot,
        base_commit="0" * 40,
        head_commit="0" * 40,
        changed_files=0,
        added=dict.fromkeys(report.CATEGORY_ORDER, 0),
    )
    report.print_report(built)

    printed = capsys.readouterr().out
    assert "Backend production" in printed
    assert "Frontend production" in printed
    assert "Handwritten production" in printed
