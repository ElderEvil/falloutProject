from app.utils.static_data import game_data_store


def get_static_game_data():
    """
    Get static game data from cache.

    Note: This is intentionally sync because it just returns a cached object.
    FastAPI Tip #9 recommends async dependencies, but for simple cache lookups
    that don't do I/O, sync is actually better (no unnecessary thread pool overhead).
    """
    return game_data_store
