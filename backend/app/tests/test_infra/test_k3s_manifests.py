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


def test_postgres_observability_config_is_pinned() -> None:
    """The production Postgres manifest must keep the live data path and enable profiling."""
    manifest = _load("postgres-deployment.yaml")
    container = _container(manifest)

    assert container["image"] == "postgres:18-alpine"
    assert any(mount["mountPath"] == "/var/lib/postgresql" for mount in container["volumeMounts"])
    args = " ".join(container["args"])
    assert "pg_stat_statements,auto_explain" in args
    assert "track_io_timing=on" in args
    assert "auto_explain.log_min_duration=200ms" in args
    assert "pg_stat_statements.track=all" in args


def test_service_manifest_matches_live_names_and_ingress() -> None:
    documents = [document for document in yaml.safe_load_all((K3S_DIR / "services.yaml").read_text()) if document]
    services = {document["metadata"]["name"]: document for document in documents}

    assert set(services) == {"backend-service", "frontend-service", "postgres-service"}
    assert all(service["spec"]["type"] == "ClusterIP" for service in services.values())
    assert services["backend-service"]["spec"]["ports"][0]["port"] == 8000
    assert services["frontend-service"]["spec"]["ports"][0]["port"] == 3000
    assert services["postgres-service"]["spec"]["ports"][0]["port"] == 5432

    ingress = _load("ingress.yaml")
    backend_names = {
        path["backend"]["service"]["name"] for rule in ingress["spec"]["rules"] for path in rule["http"]["paths"]
    }
    assert backend_names == {"backend-service", "frontend-service"}
