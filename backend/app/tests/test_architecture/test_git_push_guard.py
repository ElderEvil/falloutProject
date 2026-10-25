"""Exercise the installed pre-push hook against disposable local Git remotes."""

import shutil
import subprocess
from pathlib import Path

import pytest

HOOK_SOURCE = Path(__file__).resolve().parents[4] / "scripts" / "pre-push"
GIT = shutil.which("git")
assert GIT is not None, "Git is required to test the push guard"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    # All arguments are controlled test inputs; no shell or external service is involved.
    return subprocess.run([GIT, *args], cwd=repo, check=check, capture_output=True, text=True)  # ruff: ignore[subprocess-without-shell-equals-true]


@pytest.fixture
def push_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    work = tmp_path / "work"
    remote = tmp_path / "remote.git"
    work.mkdir()
    _git(work, "init", "--bare", str(remote))
    _git(work, "init", "-b", "master")
    _git(work, "config", "user.name", "Push guard test")
    _git(work, "config", "user.email", "push-guard@example.invalid")
    _git(work, "config", "commit.gpgsign", "false")
    _git(work, "config", "core.hooksPath", ".git/hooks")
    _git(work, "remote", "add", "origin", str(remote))
    payload = work / "payload.txt"
    payload.write_text("initial\n")
    _git(work, "add", "payload.txt")
    _git(work, "commit", "-m", "chore: initial state")
    initial_sha = _git(work, "rev-parse", "HEAD").stdout.strip()
    _git(work, "push", "origin", "HEAD:refs/heads/master")
    _git(work, "switch", "-c", "fix/example")
    payload.write_text("changed\n")
    _git(work, "commit", "-am", "fix: example change")
    installed_hook = work / ".git/hooks/pre-push"
    shutil.copyfile(HOOK_SOURCE, installed_hook)
    installed_hook.chmod(0o755)
    return work, remote, initial_sha


@pytest.mark.parametrize(
    "args",
    [
        ("HEAD:refs/heads/master",),
        ("fix/example:refs/heads/master",),
        ("--force", "HEAD:refs/heads/master"),
        ("--delete", "master"),
        ("HEAD:refs/heads/fix/new", "HEAD:refs/heads/master"),
    ],
)
def test_push_to_master_is_blocked(push_repo: tuple[Path, Path, str], args: tuple[str, ...]) -> None:
    work, remote, initial_sha = push_repo
    result = _git(work, "push", "origin", *args, check=False)
    assert result.returncode != 0
    assert "Push blocked: direct updates to master require a pull request." in result.stderr
    assert _git(remote, "rev-parse", "refs/heads/master").stdout.strip() == initial_sha
    assert not _git(remote, "for-each-ref", "refs/heads/fix/new").stdout


def test_plain_push_from_master_is_blocked(push_repo: tuple[Path, Path, str]) -> None:
    work, remote, initial_sha = push_repo
    _git(work, "branch", "-f", "master", "HEAD")
    _git(work, "switch", "master")
    result = _git(work, "push", "-u", "origin", "HEAD", check=False)
    assert result.returncode != 0
    assert "Push blocked:" in result.stderr
    assert _git(remote, "rev-parse", "refs/heads/master").stdout.strip() == initial_sha


@pytest.mark.parametrize("destination", ["refs/heads/fix/new", "refs/heads/master-backup", "refs/tags/master"])
def test_unprotected_destinations_are_allowed(push_repo: tuple[Path, Path, str], destination: str) -> None:
    work, remote, _ = push_repo
    _git(work, "push", "origin", f"HEAD:{destination}")
    assert _git(remote, "rev-parse", destination).stdout == _git(work, "rev-parse", "HEAD").stdout


def test_master_can_be_pushed_to_a_feature_branch(push_repo: tuple[Path, Path, str]) -> None:
    work, remote, _ = push_repo
    _git(work, "branch", "-f", "master", "HEAD")
    _git(work, "switch", "master")
    _git(work, "push", "origin", "HEAD:refs/heads/fix/new")
    assert _git(remote, "rev-parse", "refs/heads/fix/new").stdout == _git(work, "rev-parse", "HEAD").stdout
