"""One-shot production smoke check for the AI Gateway and Logfire wiring.

Runs as a Job built from the backend pod spec, never inside the serving API
container: a cold interpreter plus a model call shares the container's memory
limit, which is tight enough that the probe can OOMKill the app it is verifying.
"""

from __future__ import annotations

import asyncio
import sys

from app.core.config import settings
from app.core.logfire_config import configure_logfire, is_logfire_enabled
from app.services.ai_service import get_ai_service

PROBE_PROMPT = "Reply with exactly: gateway-production-check"


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if settings.ai_provider_mode != "gateway":
        _fail("AI Gateway is not configured")
    if not settings.logfire_enabled:
        _fail("LOGFIRE_TOKEN is not configured")

    configure_logfire()

    service = get_ai_service()
    if not (service.using_gateway and service.is_available()):
        _fail("AI Gateway model is unavailable")

    result = asyncio.run(service.chat_completion_with_usage([{"role": "user", "content": PROBE_PROMPT}]))
    if not result.text:
        _fail("Gateway returned an empty response")
    if not is_logfire_enabled():
        _fail("Logfire instrumentation did not initialize")

    print("Gateway and Logfire verification request completed")


if __name__ == "__main__":
    main()
