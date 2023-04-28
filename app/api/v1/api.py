from fastapi import APIRouter

from app.api.v1.endpoints import junk, outfit, quest, room, weapon


api_router = APIRouter()
api_router.include_router(junk.router, prefix="/junk", tags=["Junk"])
api_router.include_router(outfit.router, prefix="/outfits", tags=["Outfit"])
api_router.include_router(quest.router, prefix="/quests", tags=["Quest"])
api_router.include_router(room.router, prefix="/rooms", tags=["Room"])
api_router.include_router(weapon.router, prefix="/weapons", tags=["Weapon"])
