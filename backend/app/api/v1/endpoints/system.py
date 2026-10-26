"""System information endpoints."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentSuperuser
from app.core.config import settings
from app.core.game_config import game_config
from app.db.session import get_async_session
from app.schemas.console import ConsoleManifest, ConsoleRequest, ConsoleResult
from app.schemas.pagination import PageLimit
from app.schemas.system import ChangelogEntry, FeaturesResponse, InfoResponse
from app.services.changelog_service import changelog_service
from app.services.console_service import console_manifest, execute_console
from app.utils.version import get_app_version, get_python_version

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System"])


@router.get("/console/manifest")
async def get_console_manifest(_user: CurrentSuperuser) -> ConsoleManifest:
    """Describe the allowlisted commands for an authenticated superuser."""
    return console_manifest()


@router.post("/console")
async def run_console(
    request: ConsoleRequest, user: CurrentSuperuser, session: Annotated[AsyncSession, Depends(get_async_session)]
) -> ConsoleResult:
    """Execute one audited, structured admin command."""
    return await execute_console(session, user.id, request)


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
async def get_changelog(limit: PageLimit | None = 10, since: str | None = None) -> list[ChangelogEntry]:
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


@router.get("/features", response_model=FeaturesResponse)
async def get_features() -> FeaturesResponse:
    """Get the feature switches clients use to hide what is switched off."""
    return FeaturesResponse(
        race_mechanics=game_config.features.race_mechanics,
        faction_mechanics=game_config.features.faction_mechanics,
    )
