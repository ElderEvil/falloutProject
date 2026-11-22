import httpx
import pytest
from typer.testing import CliRunner

from app.cli.ops import _response_json_object, app


def test_response_json_object_returns_json_object() -> None:
    response = httpx.Response(200, json={"access_token": "test-token"})

    assert _response_json_object(response, "Login") == {"access_token": "test-token"}


def test_response_json_object_rejects_invalid_json() -> None:
    response = httpx.Response(200, content=b"not json")

    with pytest.raises(RuntimeError, match="Login returned invalid JSON"):
        _response_json_object(response, "Login")


def test_response_json_object_rejects_non_object_json() -> None:
    response = httpx.Response(200, json=["not", "an", "object"])

    with pytest.raises(RuntimeError, match="Login returned JSON list; expected an object"):
        _response_json_object(response, "Login")
