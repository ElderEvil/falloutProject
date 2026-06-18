import logging
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.system import ChangelogEntry, InfoResponse
from app.services.changelog_service import changelog_service
from app.utils.version import get_app_version, get_python_version

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/info", status_code=200)
async def get_info() -> InfoResponse:
    """Get application version and environment information."""
    return InfoResponse(
        app_version=get_app_version(),
        api_version=settings.API_VERSION,
        environment=settings.ENVIRONMENT,
        python_version=get_python_version(),
        build_date=datetime.now(UTC).isoformat(),
    )


@router.get("/changelog", response_model=list[ChangelogEntry])
async def get_changelog(limit: Optional[int] = 10, since: Optional[str] = None):
    """Get changelog entries with optional version filtering."""
    return changelog_service.get_entries(limit=limit, since=since)


@router.get("/changelog/latest", response_model=ChangelogEntry)
async def get_latest_changelog():
    """Get the most recent changelog entry."""
    return changelog_service.get_latest()
