from fastapi import APIRouter

from app.api.v1.endpoints import chat, dweller, junk, login, outfit, quest, room, user, vault, weapon

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(dweller.router, prefix="/dwellers", tags=["Dweller"])
api_router.include_router(junk.router, prefix="/junk", tags=["Junk"])
api_router.include_router(outfit.router, prefix="/outfits", tags=["Outfit"])
api_router.include_router(quest.router, prefix="/quests", tags=["Quest"])
api_router.include_router(room.router, prefix="/rooms", tags=["Room"])
api_router.include_router(user.router, prefix="/users", tags=["User"])
api_router.include_router(vault.router, prefix="/vaults", tags=["Vault"])
api_router.include_router(weapon.router, prefix="/weapons", tags=["Weapon"])
