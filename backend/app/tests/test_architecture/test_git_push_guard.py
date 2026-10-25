"""Exercise the installed pre-push hook against disposable local Git remotes."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOK_SOURCE = REPO_ROOT / "scripts" / "pre-push"
INSTALL_COMMAND = (
    (REPO_ROOT / "README.md")
    .read_text()
    .split("### Git push protection", 1)[1]
    .split("```bash\n", 1)[1]
    .split("```", 1)[0]
)
GIT = shutil.which("git")
SHELL = shutil.which("sh")
assert GIT is not None, "Git is required to test the push guard"
assert SHELL is not None, "A POSIX shell is required to test the push guard"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    # All arguments are controlled test inputs; no shell or external service is involved.
    return subprocess.run([GIT, *args], cwd=repo, check=check, capture_output=True, text=True)  # ruff: ignore[subprocess-without-shell-equals-true]


def _install(repo: Path) -> subprocess.CompletedProcess[str]:
    """Run the documented installer exactly as a developer would."""
    return subprocess.run([SHELL, "-c", INSTALL_COMMAND], cwd=repo, check=False, capture_output=True, text=True)  # ruff: ignore[subprocess-without-shell-equals-true]


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


@pytest.fixture
def install_repo(push_repo: tuple[Path, Path, str]) -> tuple[Path, Path, str]:
    """Track the hook source so linked worktrees can install it too."""
    work, _, _ = push_repo
    source = work / "scripts/pre-push"
    source.parent.mkdir()
    shutil.copyfile(HOOK_SOURCE, source)
    _git(work, "add", "scripts/pre-push")
    _git(work, "commit", "-m", "chore: include push guard source")
    (work / ".git/hooks/pre-push").unlink()
    _git(work, "config", "--unset", "core.hooksPath")
    return push_repo


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


@pytest.mark.parametrize("symlink", [False, True])
def test_installer_preserves_an_existing_hook(install_repo: tuple[Path, Path, str], symlink: bool) -> None:
    work, _, _ = install_repo
    hook = work / ".git/hooks/pre-push"
    if symlink:
        hook.symlink_to("missing-custom-hook")
    else:
        hook.write_text("#!/bin/sh\n# existing developer checks\nexit 1\n")
    original = hook.readlink() if symlink else hook.read_bytes()

    result = _install(work)

    assert result.returncode != 0
    assert "Existing pre-push hook" in result.stderr
    assert (hook.readlink() if symlink else hook.read_bytes()) == original
    assert not (hook.parent / "missing-custom-hook").exists()


def test_installer_rejects_a_relative_hooks_path(install_repo: tuple[Path, Path, str]) -> None:
    work, _, _ = install_repo
    _git(work, "config", "core.hooksPath", ".git/hooks")
    linked = work.parent / "linked"
    _git(work, "worktree", "add", "-b", "fix/linked", str(linked))

    result = _install(linked)

    assert result.returncode != 0
    assert "Relative core.hooksPath" in result.stderr
    assert _git(work, "config", "--get", "core.hooksPath").stdout.strip() == ".git/hooks"
    assert not (work / ".git/hooks/pre-push").exists()


@pytest.mark.parametrize("absolute_path", [False, True])
def test_linked_worktrees_share_the_installed_guard(install_repo: tuple[Path, Path, str], absolute_path: bool) -> None:
    work, remote, initial_sha = install_repo
    hooks_dir = work / "shared hooks" if absolute_path else work / ".git/hooks"
    if absolute_path:
        _git(work, "config", "core.hooksPath", str(hooks_dir))
    linked = work.parent / "linked"
    _git(work, "worktree", "add", "-b", "fix/linked", str(linked))

    result = _install(linked)

    assert result.returncode == 0, result.stderr
    assert (hooks_dir / "pre-push").read_bytes() == HOOK_SOURCE.read_bytes()
    for checkout in (work, linked):
        pushed = _git(checkout, "push", "origin", "HEAD:refs/heads/master", check=False)
        assert pushed.returncode != 0
        assert "Push blocked:" in pushed.stderr
    assert _git(remote, "rev-parse", "refs/heads/master").stdout.strip() == initial_sha
