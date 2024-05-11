import logfire
from fastapi import FastAPI
from sqladmin import Admin
from starlette import status

from app.admin.views import (
    DwellerAdmin,
    JunkAdmin,
    OutfitAdmin,
    QuestAdmin,
    QuestChainAdmin,
    QuestStepAdmin,
    RoomAdmin,
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
logfire.configure(pydantic_plugin=logfire.PydanticPlugin(record="all"))
logfire.instrument_fastapi(app)

admin = Admin(app, async_engine)


@app.get("/healthcheck", status_code=status.HTTP_200_OK)
def perform_healthcheck():
    return {"healthcheck": "Everything OK!"}


app.include_router(api_router_v1, prefix=settings.API_V1_STR)
admin.add_view(UserAdmin)
admin.add_view(VaultAdmin)
admin.add_view(RoomAdmin)
admin.add_view(DwellerAdmin)
admin.add_view(OutfitAdmin)
admin.add_view(WeaponAdmin)
admin.add_view(JunkAdmin)
admin.add_view(QuestChainAdmin)
admin.add_view(QuestAdmin)
admin.add_view(QuestStepAdmin)
