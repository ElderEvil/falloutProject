from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin
from starlette import status
from starlette.middleware.sessions import SessionMiddleware

from app.admin.auth import AdminAuth
from app.admin.views import (
    DwellerAdmin,
    JunkAdmin,
    LLInteractionAdmin,
    ObjectiveAdmin,
    OutfitAdmin,
    PromptAdmin,
    QuestAdmin,
    RoomAdmin,
    StorageAdmin,
    UserAdmin,
    VaultAdmin,
    WeaponAdmin,
)
from app.api.v1.api import api_router as api_router_v1
from app.core.config import settings
from app.db.session import async_engine

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

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
def perform_healthcheck():
    return {"healthcheck": "Everything OK!"}


app.include_router(api_router_v1, prefix=settings.API_V1_STR)
admin.add_view(UserAdmin)
admin.add_view(VaultAdmin)
admin.add_view(StorageAdmin)
admin.add_view(RoomAdmin)
admin.add_view(DwellerAdmin)
admin.add_view(OutfitAdmin)
admin.add_view(WeaponAdmin)
admin.add_view(JunkAdmin)
admin.add_view(QuestAdmin)
admin.add_view(ObjectiveAdmin)
admin.add_view(PromptAdmin)
admin.add_view(LLInteractionAdmin)
