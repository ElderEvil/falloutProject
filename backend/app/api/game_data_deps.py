"""Static game data dependency provider."""

from app.utils.static_data import game_data_store


async def get_static_game_data():
    """Get static game data from cache.

    Returns:
        StaticGameData: Cached static game data store.
    """
    return game_data_store
