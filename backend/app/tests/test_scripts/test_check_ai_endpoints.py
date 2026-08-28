"""Tests for the local AI endpoint smoke-test response parsing."""

import httpx
import pytest
from typer.testing import CliRunner

from app.cli.ops import _response_json_object, app


def test_response_json_object_returns_json_object() -> None:
    """A normal API object response remains available to the smoke test."""
    response = httpx.Response(200, json={"access_token": "test-token"})

    assert _response_json_object(response, "Login") == {"access_token": "test-token"}


def test_response_json_object_rejects_invalid_json() -> None:
    """Invalid endpoint JSON becomes the script's controlled RuntimeError."""
    response = httpx.Response(200, content=b"not json")

    with pytest.raises(RuntimeError, match="Login returned invalid JSON"):
        _response_json_object(response, "Login")


def test_response_json_object_rejects_non_object_json() -> None:
    """A list response cannot be mistaken for a token or chat payload object."""
    response = httpx.Response(200, json=["not", "an", "object"])

    with pytest.raises(RuntimeError, match="Login returned JSON list; expected an object"):
        _response_json_object(response, "Login")


def test_check_ai_rejects_an_unexpected_remote_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The production smoke check fails before attempting an authenticated request."""

    class TestClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str) -> httpx.Response:
            payload = {"status": "ok"} if url == "/healthcheck" else {"environment": "local"}
            return httpx.Response(200, json=payload)

        async def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            raise AssertionError("Login must not run for an unexpected environment")

    monkeypatch.setattr("app.cli.ops.httpx.AsyncClient", lambda **_kwargs: TestClient())

    result = CliRunner().invoke(app, ["check-ai", "--expect-environment", "production"])

    assert result.exit_code == 1
    assert "Expected environment 'production', got 'local'" in result.output
