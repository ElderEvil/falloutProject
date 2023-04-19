from fastapi import APIRouter

from app.api.endpoints import junk, outfit, weapon

api_router = APIRouter()
api_router.include_router(junk.router, prefix="/junk", tags=["junk"])
api_router.include_router(outfit.router, prefix="/outfits", tags=["outfits"])
api_router.include_router(weapon.router, prefix="/weapons", tags=["weapons"])
