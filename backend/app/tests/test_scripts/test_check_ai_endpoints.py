"""Tests for the local AI endpoint smoke-test response parsing."""

import httpx
import pytest

from scripts.check_ai_endpoints import response_json_object


def test_response_json_object_returns_json_object() -> None:
    """A normal API object response remains available to the smoke test."""
    response = httpx.Response(200, json={"access_token": "test-token"})

    assert response_json_object(response, "Login") == {"access_token": "test-token"}


def test_response_json_object_rejects_invalid_json() -> None:
    """Invalid endpoint JSON becomes the script's controlled RuntimeError."""
    response = httpx.Response(200, content=b"not json")

    with pytest.raises(RuntimeError, match="Login returned invalid JSON"):
        response_json_object(response, "Login")


def test_response_json_object_rejects_non_object_json() -> None:
    """A list response cannot be mistaken for a token or chat payload object."""
    response = httpx.Response(200, json=["not", "an", "object"])

    with pytest.raises(RuntimeError, match="Login returned JSON list; expected an object"):
        response_json_object(response, "Login")
