from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_deployment_uses_valid_release_images_and_detailed_health() -> None:
    dockerfile = (ROOT / "frontend/Dockerfile").read_text()
    workflow = (ROOT / ".github/workflows/deploy-hetzner.yml").read_text()

    assert "FROM node:26.8.1-alpine" in dockerfile
    assert "26.13.0" not in dockerfile
    assert "default: 'latest'" not in workflow
    assert "healthcheck?detailed=true" in workflow
