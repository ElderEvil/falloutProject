"""CLI commands for one-off operations and infrastructure tasks.

Thin wrappers over the service layer or external APIs per AGENTS.md.

Usage (from backend/):
    uv run fo-cli fix-dweller-image-urls
    uv run fo-cli set-rustfs-policies
    uv run fo-cli check-ai [--api-url URL] [--skip-chat] [--expect TEXT]
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any

import httpx
import typer
from sqlalchemy import or_
from sqlmodel import select

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.dweller import Dweller

app = typer.Typer(
    name="ops",
    help="One-off operations: image URL fix, RustFS policies, live AI smoke test.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


def _response_json_object(response: httpx.Response, step: str) -> dict[str, Any]:
    """Parse an endpoint response as a JSON object with a controlled failure message."""
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{step} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(  # ruff: ignore[type-check-without-type-error] - smoke test reports failures uniformly.
            f"{step} returned JSON {type(payload).__name__}; expected an object"
        )
    return payload


def _failure(response: httpx.Response, step: str) -> RuntimeError:
    """Create a concise error without printing credentials or access tokens."""
    try:
        detail: Any = _response_json_object(response, step).get("detail", response.text)
    except RuntimeError:
        detail = response.text
    return RuntimeError(f"{step} failed with HTTP {response.status_code}: {str(detail)[:500]}")


@app.command(name="fix-dweller-image-urls")
def fix_dweller_image_urls() -> None:
    """Convert dweller image filenames to full storage URLs."""

    async def _run() -> tuple[int, int]:
        base_url = (settings.RUSTFS_PUBLIC_URL or "https://s3-api.evillab.dev").rstrip("/")

        async with async_session_maker() as session:
            result = await session.execute(
                select(Dweller).where(or_(Dweller.image_url.is_not(None), Dweller.thumbnail_url.is_not(None)))
            )
            dwellers = result.scalars().all()

            updated_url_count = 0
            updated_dweller_count = 0
            for dweller in dwellers:
                original_image = dweller.image_url
                original_thumbnail = dweller.thumbnail_url
                dweller_modified = False

                if original_image and "://" not in original_image and not original_image.startswith("/"):
                    dweller.image_url = f"{base_url}/dweller-images/{original_image}"
                    updated_url_count += 1
                    dweller_modified = True

                if original_thumbnail and "://" not in original_thumbnail and not original_thumbnail.startswith("/"):
                    dweller.thumbnail_url = f"{base_url}/dweller-thumbnails/{original_thumbnail}"
                    updated_url_count += 1
                    dweller_modified = True

                if dweller_modified:
                    updated_dweller_count += 1

            await session.commit()
            return updated_url_count, updated_dweller_count

    try:
        updated_url_count, updated_dweller_count = asyncio.run(_run())
    except Exception:
        logger.exception("fix-dweller-image-urls failed")
        typer.echo("Error: fix-dweller-image-urls failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(f"Updated {updated_url_count} URL(s) across {updated_dweller_count} dwellers")


@app.command(name="set-rustfs-policies")
def set_rustfs_policies() -> None:
    """Set public read policies on all whitelisted RustFS buckets."""
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    buckets = settings.RUSTFS_PUBLIC_BUCKET_WHITELIST
    client = boto3.client(
        "s3",
        endpoint_url=settings.RUSTFS_PUBLIC_URL or "https://s3-api.evillab.dev",
        aws_access_key_id=settings.RUSTFS_ACCESS_KEY or "",
        aws_secret_access_key=settings.RUSTFS_SECRET_KEY or "",
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": ["arn:aws:s3:::{bucket}/*"],
            }
        ],
    }
    serialized_policy = json.dumps(policy)

    failed: list[str] = []
    for bucket in buckets:
        try:
            bucket_policy = serialized_policy.replace("{bucket}", bucket)
            client.put_bucket_policy(Bucket=bucket, Policy=bucket_policy)
            typer.echo(f"Set public policy for: {bucket}")
        except (BotoCoreError, ClientError) as exc:
            typer.echo(f"Failed to set policy for {bucket}: {exc}", err=True)
            failed.append(bucket)

    if failed:
        raise typer.Exit(code=1)


@app.command(name="check-ai")
def check_ai(
    api_url: Annotated[
        str,
        typer.Option(help="API base URL for the live smoke test"),
    ] = "http://127.0.0.1:8000",
    message: Annotated[
        str,
        typer.Option(help="Chat message used for the live provider check"),
    ] = "Reply with exactly: gateway-api-check",
    expect: Annotated[
        str | None,
        typer.Option(help="Optional exact response expected from the model"),
    ] = None,
    skip_chat: Annotated[
        bool,
        typer.Option(help="Check health, login, and dweller access without a model call"),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option(help="Per-request timeout in seconds"),
    ] = 60.0,
) -> None:
    """Smoke-test the authenticated local chat API against a live server.

    Requires the API to be running. Logs in as FIRST_SUPERUSER_EMAIL, selects the
    first local dweller, and sends one chat message. This writes one local chat
    history entry and makes one real model request. Use --skip-chat for a free
    authentication/readiness-only check.
    """

    async def _run() -> dict[str, Any]:
        base_url = api_url.rstrip("/")
        summary: dict[str, Any] = {
            "api_url": base_url,
            "ai_mode": settings.ai_provider_mode,
            "gateway_route": settings.PYDANTIC_AI_GATEWAY_ROUTE,
            "gateway_base_url": settings.PYDANTIC_AI_GATEWAY_BASE_URL,
            "gateway_key_configured": bool(settings.PYDANTIC_AI_GATEWAY_API_KEY),
            "openai_key_configured": bool(settings.OPENAI_API_KEY),
        }

        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            health = await client.get("/healthcheck")
            if health.is_error:
                raise _failure(health, "Health check")
            summary["health_status"] = health.status_code

            login = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": str(settings.FIRST_SUPERUSER_EMAIL),
                    "password": settings.FIRST_SUPERUSER_PASSWORD,
                },
            )
            if login.is_error:
                raise _failure(login, "Default-user login")
            token = _response_json_object(login, "Default-user login").get("access_token")
            if not isinstance(token, str) or not token:
                raise RuntimeError("Default-user login succeeded but did not return an access token")
            summary["login_status"] = login.status_code

            headers = {"Authorization": f"Bearer {token}"}
            dwellers = await client.get("/api/v1/dwellers/", headers=headers)
            if dwellers.is_error:
                raise _failure(dwellers, "Dweller lookup")
            records = dwellers.json()
            if not records:
                raise RuntimeError("No local dwellers found; create one before running the chat check")
            summary["dwellers_status"] = dwellers.status_code
            summary["dweller_available"] = True

            if skip_chat:
                summary["chat_checked"] = False
                return summary

            chat = await client.post(
                f"/api/v1/chat/{records[0]['id']}",
                headers=headers,
                json={"message": message},
            )
            if chat.is_error:
                raise _failure(chat, "Gateway chat API check")
            payload = _response_json_object(chat, "Gateway chat API check")
            response_text = payload.get("response", "")
            summary.update(
                chat_checked=True,
                chat_status=chat.status_code,
                response_received=bool(response_text),
                response_matches_expectation=expect is None or response_text == expect,
                dweller_message_id_present=bool(payload.get("dweller_message_id")),
                action_type=(payload.get("action_suggestion") or {}).get("action_type"),
            )
            if expect is not None and response_text != expect:
                raise RuntimeError("Chat response did not match --expect")
            return summary

    try:
        summary = asyncio.run(_run())
    except (httpx.HTTPError, RuntimeError) as exc:
        typer.echo(f"AI endpoint check failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("AI endpoint check passed")
    for key, value in summary.items():
        typer.echo(f"{key}: {value}")


if __name__ == "__main__":
    app()
