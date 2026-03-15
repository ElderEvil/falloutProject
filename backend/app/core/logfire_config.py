import logging

logger = logging.getLogger(__name__)


class LogfireState:
    """Mutable container for logfire initialization state."""

    initialized: bool = False


_logfire_state = LogfireState()


def is_logfire_enabled() -> bool:
    return _logfire_state.initialized


def configure_logfire() -> None:
    from app.core.config import settings

    if not settings.logfire_enabled:
        logger.debug("Logfire not configured (LOGFIRE_TOKEN not set)")
        return

    try:
        import logfire

        logfire.configure(
            token=settings.LOGFIRE_TOKEN,
            environment=settings.ENVIRONMENT,
            service_name="fallout-shelter-api",
        )

        _logfire_state.initialized = True
        logger.info("Logfire observability configured successfully")

    except ImportError:
        logger.warning("Logfire package not installed. Install with: uv add logfire")
    except Exception:
        logger.exception("Failed to configure Logfire")
