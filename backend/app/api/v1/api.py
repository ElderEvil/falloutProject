from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    debug,
    dweller,
    exploration,
    game_control,
    junk,
    notifications,
    objective,
    outfit,
    pregnancy,
    quest,
    radio,
    relationship,
    room,
    storage,
    stream,
    system,
    training,
    user,
    vault,
    weapon,
    websocket,
)
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
# Debug router only registered in debug/development mode
if settings.ENVIRONMENT in ("local", "development"):
    api_router.include_router(debug.router)
api_router.include_router(dweller.router)
api_router.include_router(exploration.router)
api_router.include_router(game_control.router)
api_router.include_router(junk.router)
api_router.include_router(notifications.router)
api_router.include_router(objective.router)
api_router.include_router(outfit.router)
api_router.include_router(pregnancy.router)
api_router.include_router(quest.router)
api_router.include_router(radio.router)
api_router.include_router(relationship.router)
api_router.include_router(room.router)
api_router.include_router(storage.router)
api_router.include_router(stream.router)
api_router.include_router(training.router)
api_router.include_router(user.router)
api_router.include_router(vault.router)
api_router.include_router(weapon.router)
api_router.include_router(websocket.router)
