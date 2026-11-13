"""Run the backend CI hook command against committed changes in a disposable repo."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
BASH = shutil.which("bash") or pytest.fail("Bash is required for CI hook tests")
GIT = shutil.which("git") or pytest.fail("Git is required for CI hook tests")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [GIT, *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.mark.parametrize("invalid_change", [True, False])
def test_ci_checks_committed_changes_without_gating_legacy_files(tmp_path: Path, invalid_change: bool) -> None:
    """A clean index must not hide new failures or pull unrelated legacy debt into the gate."""
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/backend-ci.yml").read_text())
    step = next(step for step in workflow["jobs"]["backend-ci"]["steps"] if step.get("name") == "Run linter (prek)")
    # Run the real prek binary from the test environment, without uv project discovery in the fixture repo.
    command = step["run"].removeprefix("uv run ")
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.name", "CI scope test")
    _git(tmp_path, "config", "user.email", "ci-scope@example.invalid")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    _git(tmp_path, "config", "core.hooksPath", ".git/hooks")
    backend = tmp_path / "backend"
    backend.mkdir()
    (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n  - repo: builtin\n    hooks:\n      - id: check-json\n")
    (backend / "legacy.json").write_text("invalid legacy json\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "chore: baseline")
    base_ref = _git(tmp_path, "rev-parse", "HEAD")
    (backend / "changed.json").write_text("invalid new json\n" if invalid_change else "{}\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "chore: change")
    assert not _git(tmp_path, "status", "--porcelain")

    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [BASH, "-c", command],
        cwd=backend,
        env={**os.environ, "BASE_REF": base_ref, "HEAD_REF": "HEAD"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert (result.returncode != 0) == invalid_change, result.stdout + result.stderr
    assert "Skipped" not in result.stdout
