"""Async provider for the cached static game data store."""

from app.utils.static_data import StaticGameData, game_data_store


async def get_static_game_data() -> StaticGameData:
    return game_data_store
