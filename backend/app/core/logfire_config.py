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

    try:
        import logfire

        configure_options = {
            "send_to_logfire": "if-token-present",
            "environment": settings.ENVIRONMENT,
            "service_name": "fallout-shelter-api",
        }
        if settings.LOGFIRE_TOKEN:
            configure_options["token"] = settings.LOGFIRE_TOKEN

        logfire.configure(**configure_options)
        logfire.instrument_pydantic_ai(include_content=False)

        _logfire_state.initialized = True
        logger.info("Logfire observability and Pydantic AI instrumentation configured successfully")

    except ImportError:
        logger.warning("Logfire package not installed. Install with: uv add logfire")
    except Exception:
        logger.exception("Failed to configure Logfire")
