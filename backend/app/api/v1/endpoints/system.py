"""
System endpoints for application metadata and status.

Public endpoints (no authentication required) that provide version,
environment information, and health status for monitoring and UI display.
"""

import logging
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.utils.version import get_app_version, get_python_version

logger = logging.getLogger(__name__)
router = APIRouter()


class InfoResponse(BaseModel):
    """Application information response schema."""

    app_version: str
    api_version: str
    environment: str
    python_version: str
    build_date: str


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
        build_date=datetime.utcnow().isoformat(),
    )
