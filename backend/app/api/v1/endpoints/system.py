"""System information endpoints."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.system import ChangelogEntry, InfoResponse
from app.services.changelog_service import changelog_service
from app.utils.version import get_app_version, get_python_version

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System"])


@router.get("/info", status_code=200)
async def get_info() -> InfoResponse:
    """Get application version and environment information.

    Returns:
        Application info including version, environment, and build details.
    """
    return InfoResponse(
        app_version=get_app_version(),
        api_version=settings.API_VERSION,
        environment=settings.ENVIRONMENT,
        python_version=get_python_version(),
        build_date=datetime.now(UTC).isoformat(),
    )


@router.get("/changelog", response_model=list[ChangelogEntry])
async def get_changelog(limit: int | None = 10, since: str | None = None) -> list[ChangelogEntry]:
    """Get changelog entries with optional version filtering.

    Returns:
        List of changelog entries.
    """
    return changelog_service.get_entries(limit=limit, since=since)


@router.get("/changelog/latest", response_model=ChangelogEntry)
async def get_latest_changelog() -> ChangelogEntry:
    """Get the most recent changelog entry.

    Returns:
        The latest changelog entry.
    """
    return changelog_service.get_latest()
