"""Recovery drill scripts must refuse unsafe work and classify fixtures without containers."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / "scripts"
BASH = shutil.which("bash")
DRILL = SCRIPTS / "k3s-datastore-drill.sh"
RESTORE = SCRIPTS / "restore-drill.sh"

pytestmark = pytest.mark.skipif(BASH is None, reason="Requires bash")


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - checked-in scripts
        [BASH, *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )


@pytest.mark.parametrize("name", ["restore-drill.sh", "k3s-datastore-drill.sh"])
def test_scripts_parse(name: str) -> None:
    script = SCRIPTS / name
    if not script.exists():
        pytest.skip(f"{name} is not present")
    result = _run("-n", str(script))
    assert result.returncode == 0, result.stderr


def _fixture(tmp_path: Path, *relative: str) -> Path:
    data = tmp_path / "k3s"
    for item in relative:
        path = data / item
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    return data


@pytest.mark.parametrize(
    ("layout", "expected", "exit_code"),
    [
        (("server/db/state.db",), "sqlite", 0),
        (("server/db/etcd/member/wal",), "etcd", 0),
        ((), "unknown", 1),
    ],
)
def test_detect_classifies_datastore(tmp_path: Path, layout: tuple[str, ...], expected: str, exit_code: int) -> None:
    data = _fixture(tmp_path, *layout)
    result = _run(str(DRILL), "detect", "--data-dir", str(data))
    assert result.returncode == exit_code, result.stderr
    assert json.loads(result.stdout)["datastore"] == expected


def test_detect_reports_token_presence_without_printing_it(tmp_path: Path) -> None:
    data = _fixture(tmp_path, "server/db/state.db")
    token = data / "server/token"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text("super-secret-token-value")
    result = _run(str(DRILL), "detect", "--data-dir", str(data))
    assert json.loads(result.stdout)["token_present"] is True
    assert "super-secret-token-value" not in result.stdout + result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="Requires an unprivileged user")
def test_snapshot_refuses_non_root(tmp_path: Path) -> None:
    result = _run(str(DRILL), "snapshot", "--out", str(tmp_path / "snapshot"))
    assert result.returncode != 0
    assert "must run as root" in result.stderr


def _snapshot(tmp_path: Path, *, datastore: str, version: str, include_artifact: bool) -> Path:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    files = []
    if include_artifact:
        artifact = snapshot / "sqlite-db.tar.gz"
        artifact.write_bytes(b"not-a-real-tar")
        files.append({"path": "sqlite-db.tar.gz", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()})
    token = snapshot / "server-token"
    token.write_bytes(b"token")
    files.append({"path": "server-token", "sha256": hashlib.sha256(token.read_bytes()).hexdigest()})
    meta = {
        "datastore": datastore,
        "k3s_version": version,
        "node_name": "test",
        "data_dir": "/var/lib/rancher/k3s",
        "created_at": "2026-11-13T00:00:00Z",
        "files": files,
        "token_sha256": hashlib.sha256(token.read_bytes()).hexdigest(),
        "markers": {
            "default_namespace": None,
            "kube_system_namespace": None,
            "kube_root_ca_configmap": None,
        },
    }
    (snapshot / "snapshot.meta.json").write_text(json.dumps(meta))
    return snapshot


def _fake_engine(tmp_path: Path) -> dict[str, str]:
    tools = tmp_path / "bin"
    tools.mkdir()
    engine = tools / "podman"
    engine.write_text("#!/usr/bin/env bash\nexit 1\n")
    engine.chmod(0o755)
    return {**os.environ, "PATH": f"{tools}:{os.environ['PATH']}"}


@pytest.mark.skipif(os.geteuid() == 0, reason="Rehearse refuses to run as root")
def test_rehearse_derives_image_and_refuses_missing_pull(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, datastore="sqlite", version="v1.29.6+k3s2", include_artifact=True)
    result = _run(
        str(DRILL),
        "rehearse",
        "--snapshot",
        str(snapshot),
        "--engine",
        "podman",
        env=_fake_engine(tmp_path),
    )
    assert result.returncode != 0
    assert "rancher/k3s:v1.29.6-k3s2" in result.stderr
    assert "not pre-pulled" in result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="Rehearse refuses to run as root")
def test_rehearse_refuses_datastore_mismatch(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, datastore="sqlite", version="v1.29.6+k3s2", include_artifact=False)
    result = _run(
        str(DRILL),
        "rehearse",
        "--snapshot",
        str(snapshot),
        "--engine",
        "podman",
        env=_fake_engine(tmp_path),
    )
    assert result.returncode != 0
    assert "datastore types disagree" in result.stderr


def test_restore_drill_requires_dump() -> None:
    result = _run(str(RESTORE))
    assert result.returncode != 0
    assert "--dump is required" in result.stderr
