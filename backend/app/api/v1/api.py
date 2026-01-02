from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    dweller,
    exploration,
    game_control,
    junk,
    login,
    objective,
    outfit,
    pregnancy,
    profile,
    quest,
    radio,
    relationship,
    room,
    training,
    user,
    vault,
    weapon,
)

api_router = APIRouter()
api_router.include_router(login.router, tags=["login"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(dweller.router, prefix="/dwellers", tags=["Dweller"])
api_router.include_router(exploration.router, prefix="/explorations", tags=["Exploration"])
api_router.include_router(game_control.router, prefix="/game", tags=["Game"])
api_router.include_router(junk.router, prefix="/junk", tags=["Junk"])
api_router.include_router(objective.router, prefix="/objectives", tags=["Objective"])
api_router.include_router(outfit.router, prefix="/outfits", tags=["Outfit"])
api_router.include_router(pregnancy.router, prefix="/pregnancies", tags=["Pregnancy"])
api_router.include_router(profile.router, prefix="/users", tags=["Profile"])
api_router.include_router(quest.router, prefix="/quests", tags=["Quest"])
api_router.include_router(radio.router, prefix="/radio", tags=["Radio"])
api_router.include_router(relationship.router, prefix="/relationships", tags=["Relationship"])
api_router.include_router(room.router, prefix="/rooms", tags=["Room"])
api_router.include_router(training.router, prefix="/training", tags=["Training"])
api_router.include_router(user.router, prefix="/users", tags=["User"])
api_router.include_router(vault.router, prefix="/vaults", tags=["Vault"])
api_router.include_router(weapon.router, prefix="/weapons", tags=["Weapon"])
