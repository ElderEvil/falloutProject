import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_deployment_uses_valid_release_images_and_detailed_health() -> None:
    dockerfile = (ROOT / "frontend/Dockerfile").read_text()
    workflow = (ROOT / ".github/workflows/deploy-hetzner.yml").read_text()
    images = re.findall(r"^FROM node:(\S+)", dockerfile, re.MULTILINE)
    assert len(set(images)) == 1
    assert "default: 'latest'" not in workflow
    assert "contents: read" in workflow
    assert "healthcheck?detailed=true" in workflow
    assert "if k!='smtp'" not in workflow
