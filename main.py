from fastapi import FastAPI

from app.api.endpoints.junk import router as junk_router
from app.api.endpoints.outfit import router as outfit_router
from app.api.endpoints.weapon import router as weapon_router
from app.db.base import create_db_and_tables

app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def root():
    return "Hello world"


database_api = FastAPI()

database_api.include_router(junk_router, tags=["Junk"])
database_api.include_router(outfit_router, tags=["Outfit"])
database_api.include_router(weapon_router, tags=["Weapon"])

app.mount("/database", database_api)
