import logging

logger = logging.getLogger(__name__)

_logfire_initialized = False


def is_logfire_enabled() -> bool:
    return _logfire_initialized


def configure_logfire() -> None:
    global _logfire_initialized

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

        _logfire_initialized = True
        logger.info("Logfire observability configured successfully")

    except ImportError:
        logger.warning("Logfire package not installed. Install with: uv add logfire")
    except Exception:
        logger.exception("Failed to configure Logfire")
