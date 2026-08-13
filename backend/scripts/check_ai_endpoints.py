"""Smoke-test the authenticated local chat API and its configured AI provider.

Run from ``backend/`` while the API is already running:

    uv run python scripts/check_ai_endpoints.py

The default check logs in as ``FIRST_SUPERUSER_EMAIL``, selects the first local
dweller, and sends one chat message. It therefore writes one local chat history
entry and makes one real model request. Use ``--skip-chat`` for a free
authentication/readiness-only check.
"""

import argparse
import asyncio
import sys
from typing import Any

import httpx

from app.core.config import settings

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_MESSAGE = "Reply with exactly: gateway-api-check"


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"API base URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--message", default=DEFAULT_MESSAGE, help="Chat message used for the live provider check")
    parser.add_argument(
        "--expect",
        help="Optional exact response expected from the model; exits non-zero if it differs",
    )
    parser.add_argument(
        "--skip-chat", action="store_true", help="Check health, login, and dweller access without a model call"
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request timeout in seconds (default: 60)")
    return parser.parse_args()


def failure(response: httpx.Response, step: str) -> RuntimeError:
    """Create a concise error without printing credentials or access tokens."""
    try:
        detail: Any = response_json_object(response, step).get("detail", response.text)
    except RuntimeError:
        detail = response.text
    return RuntimeError(f"{step} failed with HTTP {response.status_code}: {str(detail)[:500]}")


def response_json_object(response: httpx.Response, step: str) -> dict[str, Any]:
    """Parse an endpoint response as a JSON object with a controlled failure message."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{step} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(  # ruff: ignore[type-check-without-type-error] - main deliberately reports failures uniformly.
            f"{step} returned JSON {type(payload).__name__}; expected an object"
        )
    return payload


async def run_check(args: argparse.Namespace) -> dict[str, Any]:
    """Call health, authentication, dweller, and optionally chat endpoints."""
    base_url = args.api_url.rstrip("/")
    summary: dict[str, Any] = {
        "api_url": base_url,
        "ai_mode": settings.ai_provider_mode,
        "gateway_route": settings.PYDANTIC_AI_GATEWAY_ROUTE,
        "gateway_base_url": settings.PYDANTIC_AI_GATEWAY_BASE_URL,
        "gateway_key_configured": bool(settings.PYDANTIC_AI_GATEWAY_API_KEY),
        "openai_key_configured": bool(settings.OPENAI_API_KEY),
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=args.timeout) as client:
        health = await client.get("/healthcheck")
        if health.is_error:
            raise failure(health, "Health check")
        summary["health_status"] = health.status_code

        login = await client.post(
            "/api/v1/auth/login",
            data={"username": str(settings.FIRST_SUPERUSER_EMAIL), "password": settings.FIRST_SUPERUSER_PASSWORD},
        )
        if login.is_error:
            raise failure(login, "Default-user login")
        token = response_json_object(login, "Default-user login").get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Default-user login succeeded but did not return an access token")
        summary["login_status"] = login.status_code

        headers = {"Authorization": f"Bearer {token}"}
        dwellers = await client.get("/api/v1/dwellers/", headers=headers)
        if dwellers.is_error:
            raise failure(dwellers, "Dweller lookup")
        records = dwellers.json()
        if not records:
            raise RuntimeError("No local dwellers found; create one before running the chat check")
        summary["dwellers_status"] = dwellers.status_code
        summary["dweller_available"] = True

        if args.skip_chat:
            summary["chat_checked"] = False
            return summary

        chat = await client.post(
            f"/api/v1/chat/{records[0]['id']}",
            headers=headers,
            json={"message": args.message},
        )
        if chat.is_error:
            raise failure(chat, "Gateway chat API check")
        payload = response_json_object(chat, "Gateway chat API check")
        response_text = payload.get("response", "")
        summary.update(
            chat_checked=True,
            chat_status=chat.status_code,
            response_received=bool(response_text),
            response_matches_expectation=args.expect is None or response_text == args.expect,
            dweller_message_id_present=bool(payload.get("dweller_message_id")),
            action_type=(payload.get("action_suggestion") or {}).get("action_type"),
        )
        if args.expect is not None and response_text != args.expect:
            raise RuntimeError("Chat response did not match --expect")
        return summary


def main() -> int:
    """Run the smoke test and return an appropriate shell status."""
    args = parse_args()
    try:
        summary = asyncio.run(run_check(args))
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"AI endpoint check failed: {exc}", file=sys.stderr)
        return 1

    print("AI endpoint check passed")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
