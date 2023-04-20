from fastapi import APIRouter

from app.api.endpoints import junk, outfit, room, weapon

api_router = APIRouter()
api_router.include_router(junk.router, tags=["junk"])
api_router.include_router(outfit.router, tags=["outfits"])
api_router.include_router(room.router, tags=["rooms"])
api_router.include_router(weapon.router, tags=["weapons"])
