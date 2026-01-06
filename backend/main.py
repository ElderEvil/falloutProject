import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin
from starlette import status
from starlette.middleware.sessions import SessionMiddleware

from app.admin.auth import AdminAuth
from app.admin.views import (
    ChatMessageAdmin,
    DwellerAdmin,
    ExplorationAdmin,
    IncidentAdmin,
    JunkAdmin,
    LLInteractionAdmin,
    NotificationAdmin,
    ObjectiveAdmin,
    OutfitAdmin,
    PregnancyAdmin,
    PromptAdmin,
    QuestAdmin,
    RelationshipAdmin,
    RoomAdmin,
    StorageAdmin,
    TrainingAdmin,
    UserAdmin,
    UserProfileAdmin,
    VaultAdmin,
    WeaponAdmin,
)
from app.api.v1.api import api_router as api_router_v1
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import async_engine, get_async_session
from app.middleware.request_id import RequestIdMiddleware
from app.services.health_check import HealthCheckService
from app.utils.seed_objectives import seed_objectives_from_json
from app.utils.seed_quests import seed_quests_from_json

# Configure logging with centralized setup
setup_logging(
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
    log_file=settings.LOG_FILE_PATH,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """
    Lifespan context manager for FastAPI startup and shutdown events.

    Performs health checks on startup and cleanup on shutdown.
    """
    # Startup: Check service health
    logger.info(
        "Starting Fallout Shelter API",
        extra={
            "environment": settings.ENVIRONMENT,
            "api_version": settings.API_VERSION,
            "log_level": settings.LOG_LEVEL,
            "json_logging": settings.LOG_JSON_FORMAT,
        },
    )

    health_check_service = HealthCheckService()
    results = await health_check_service.check_all_services(async_engine)
    health_check_service.log_health_check_results(results)

    # Seed quests and objectives from JSON files
    async for session in get_async_session():
        quest_count = await seed_quests_from_json(session)
        objective_count = await seed_objectives_from_json(session)

        if quest_count > 0:
            logger.info("Quest seeding complete: %d quests added", quest_count)
        if objective_count > 0:
            logger.info("Objective seeding complete: %d objectives added", objective_count)
        break

    logger.info("Fallout Shelter API startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Fallout Shelter API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Add request ID middleware (first, so it wraps all other middleware)
app.add_middleware(RequestIdMiddleware)

# Add session middleware for admin authentication
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Create authentication backend
authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)

# Create admin with authentication
admin = Admin(app, async_engine, authentication_backend=authentication_backend)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthcheck", status_code=status.HTTP_200_OK)
async def perform_healthcheck(*, detailed: bool = False):
    """
    Health check endpoint.

    Args:
        detailed: If True, return detailed health information for all services

    Returns:
        Basic health status or detailed service information
    """
    if not detailed:
        return {"status": "ok"}

    # Detailed health check
    health_check_service = HealthCheckService()
    results = await health_check_service.check_all_services(async_engine)

    return {
        "status": "ok" if all(r.status.value == "healthy" for r in results.values()) else "degraded",
        "services": {
            service_name: {
                "status": result.status.value,
                "message": result.message,
                "details": result.details,
            }
            for service_name, result in results.items()
        },
    }


app.include_router(api_router_v1, prefix=settings.API_V1_STR)
admin.add_view(UserAdmin)
admin.add_view(UserProfileAdmin)
admin.add_view(VaultAdmin)
admin.add_view(StorageAdmin)
admin.add_view(RoomAdmin)
admin.add_view(DwellerAdmin)
admin.add_view(RelationshipAdmin)
admin.add_view(PregnancyAdmin)
admin.add_view(TrainingAdmin)
admin.add_view(IncidentAdmin)
admin.add_view(ExplorationAdmin)
admin.add_view(ChatMessageAdmin)
admin.add_view(NotificationAdmin)
admin.add_view(OutfitAdmin)
admin.add_view(WeaponAdmin)
admin.add_view(JunkAdmin)
admin.add_view(QuestAdmin)
admin.add_view(ObjectiveAdmin)
admin.add_view(PromptAdmin)
admin.add_view(LLInteractionAdmin)
