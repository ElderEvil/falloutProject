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
    assert any(env["name"] == "DRAMATIQ_PROCESSES" and env["value"] == "2" for env in container["env"])


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


def test_image_cleanup_job_is_privileged_and_keeps_two_releases() -> None:
    job = _load("image-cleanup-job.yaml")
    pod = job["spec"]["template"]["spec"]
    container = pod["containers"][0]

    assert job["spec"]["backoffLimit"] == 2
    assert job["spec"]["activeDeadlineSeconds"] == 600
    assert pod["automountServiceAccountToken"] is False
    assert pod["restartPolicy"] == "Never"
    assert container["securityContext"] == {"privileged": True, "runAsUser": 0}
    assert any(env["name"] == "KEEP_RELEASES" and env["value"] == "2" for env in container["env"])
    assert any(volume["hostPath"]["path"] == "/" for volume in pod["volumes"])

    script = " ".join([*container["command"], *container["args"]])
    assert "set -euo pipefail" in script
    assert "fo-shelter-be" in script
    assert "fo-shelter-fe" in script
    assert "LC_ALL=C sort -V" in script
    assert "tail -n" in script
    assert "userSpecifiedImage" in script
    assert "crictl rmi" in script
    assert "--prune" not in script


def test_traefik_preserves_client_ip_and_existing_chart_settings() -> None:
    config = _load("traefik-config.yaml")
    values = yaml.safe_load(config["spec"]["valuesContent"])

    assert values["service"]["spec"]["externalTrafficPolicy"] == "Local"
    assert values["entryPoints"]["websecure"]["forwardedHeaders"]["trustedIPs"] == ["0.0.0.0/0"]
    assert values["entryPoints"]["websecure"]["proxyProtocol"]["trustedIPs"] == ["0.0.0.0/0"]


def test_service_manifest_matches_live_names_and_ingress() -> None:
    documents = [document for document in yaml.safe_load_all((K3S_DIR / "services.yaml").read_text()) if document]
    services = {document["metadata"]["name"]: document for document in documents}

    assert set(services) == {"backend-service", "frontend-service", "postgres-service"}
    assert all(service["spec"]["type"] == "ClusterIP" for service in services.values())
    assert services["backend-service"]["spec"]["ports"][0]["port"] == 8000
    assert services["frontend-service"]["spec"]["ports"][0]["port"] == 3000
    assert services["postgres-service"]["spec"]["ports"][0]["port"] == 5432

    deployments = {
        "backend-service": "backend-deployment.yaml",
        "frontend-service": "frontend-deployment.yaml",
        "postgres-service": "postgres-deployment.yaml",
    }
    for service_name, filename in deployments.items():
        deployment = _load(filename)
        pod_labels = deployment["spec"]["template"]["metadata"]["labels"]
        assert services[service_name]["spec"]["selector"].items() <= pod_labels.items()

    ingress = _load("ingress.yaml")
    backend_names = {
        path["backend"]["service"]["name"] for rule in ingress["spec"]["rules"] for path in rule["http"]["paths"]
    }
    assert backend_names == {"backend-service", "frontend-service"}
