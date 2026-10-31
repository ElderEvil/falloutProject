"""Guards that the checked-in k3s manifests match the deployment contract."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
K3S_DIR = REPO_ROOT / "deployment" / "k3s"


def _load(name: str) -> dict:
    return yaml.safe_load((K3S_DIR / name).read_text(encoding="utf-8"))


def _container(manifest: dict) -> dict:
    return manifest["spec"]["template"]["spec"]["containers"][0]


def test_backend_uses_a_dependency_readiness_probe_and_a_light_liveness_probe() -> None:
    container = _container(_load("backend-deployment.yaml"))

    assert container["livenessProbe"]["httpGet"]["path"] == "/healthcheck"
    assert container["readinessProbe"]["httpGet"]["path"] == "/readiness"
    assert "fo-shelter-be" in container["image"]


def test_frontend_uses_the_release_image_baseline() -> None:
    container = _container(_load("frontend-deployment.yaml"))

    assert "fo-shelter-fe" in container["image"]


def test_worker_manifest_matches_the_release_deployment_contract() -> None:
    manifest = _load("dramatiq-worker-deployment.yaml")
    container = _container(manifest)

    assert manifest["metadata"]["name"] == "dramatiq-worker"
    assert manifest["spec"]["replicas"] == 1
    assert manifest["spec"]["strategy"] == {"type": "Recreate"}
    assert container["name"] == "dramatiq-worker"
    assert "fo-shelter-be" in container["image"]
    assert container["envFrom"] == [{"secretRef": {"name": "backend-env"}}]
    assert container["env"][0]["name"] == "ENVIRONMENT"
    assert any(env["name"] == "FALLOUT_WORKER" and env["value"] == "1" for env in container["env"])

    command = " ".join([*container["command"], *container["args"]])
    assert "periodiq app.core.dramatiq app.api.tasks" in command
    assert "dramatiq --processes" in command
    assert "DRAMATIQ_PROCESSES" in command
    assert any(env["name"] == "DRAMATIQ_PROCESSES" and env["value"] == "4" for env in container["env"])
