import logging
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.system import ChangelogEntry, InfoResponse
from app.utils.exceptions import NotFoundException
from app.utils.version import get_app_version, get_python_version, parse_changelog, version_tuple

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/info", status_code=200)
async def get_info() -> InfoResponse:
    """
    Get application version and environment information.

    Public endpoint (no authentication required).
    Useful for monitoring, debugging, and displaying in UI.

    :returns: Application info including versions and environment
    :rtype: InfoResponse
    """
    return InfoResponse(
        app_version=get_app_version(),
        api_version=settings.API_VERSION,
        environment=settings.ENVIRONMENT,
        python_version=get_python_version(),
        build_date=datetime.now(UTC).isoformat(),
    )


@router.get("/changelog", response_model=list[ChangelogEntry])
async def get_changelog(limit: Optional[int] = 10, since: Optional[str] = None):
    changelog_path = settings.project_root / "CHANGELOG.md"
    versions = parse_changelog(changelog_path)

    if since:
        try:
            since_tuple = version_tuple(since)
            versions = [v for v in versions if version_tuple(v["version"]) > since_tuple]
        except (ValueError, AttributeError):
            pass

    versions.sort(key=lambda x: version_tuple(x["version"]), reverse=True)

    if limit:
        versions = versions[:limit]

    return versions


@router.get("/changelog/latest", response_model=ChangelogEntry)
async def get_latest_changelog():
    changelog_path = settings.project_root / "CHANGELOG.md"
    versions = parse_changelog(changelog_path)

    if not versions:
        raise NotFoundException(detail="No changelog entries available")

    versions.sort(key=lambda x: version_tuple(x["version"]), reverse=True)
    return versions[0]
