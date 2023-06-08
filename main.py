from fastapi import FastAPI
from sqladmin import Admin
from sqlmodel import SQLModel
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.v1.api import api_router as api_router_v1
from app.core.config import settings
from app.db.session import async_engine
from app.models.admin import DwellerAdmin, JunkAdmin, OutfitAdmin, QuestAdmin, RoomAdmin, UserAdmin, WeaponAdmin

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)
admin = Admin(app, async_engine)


@app.on_event("startup")
async def init_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@app.on_event("shutdown")
def shutdown_event():
    ...


@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"message": "Bad request"},
    )


@app.get("/healthcheck", status_code=status.HTTP_200_OK)
def perform_healthcheck():
    return {"healthcheck": "Everything OK!"}


app.include_router(api_router_v1, prefix=settings.API_V1_STR)
admin.add_view(UserAdmin)
admin.add_view(DwellerAdmin)
admin.add_view(JunkAdmin)
admin.add_view(OutfitAdmin)
admin.add_view(QuestAdmin)
admin.add_view(RoomAdmin)
admin.add_view(WeaponAdmin)
