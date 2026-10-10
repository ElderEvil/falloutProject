"""Deployment must migrate successfully before starting a new application image."""

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[4] / ".github/workflows/deploy-hetzner.yml"


def test_migration_job_finishes_before_application_images_change() -> None:
    workflow = WORKFLOW.read_text()
    image_update = workflow.index("kubectl set image deployment/backend")
    migration = workflow.index("uv run alembic")
    assert migration < image_update
    assert "--for=condition=complete" in workflow[migration:image_update]


def test_maintenance_stops_writers_before_migration() -> None:
    workflow = WORKFLOW.read_text()
    assert "maintenance_mode" in workflow
    assert workflow.index("--replicas=0") < workflow.index("uv run alembic")
