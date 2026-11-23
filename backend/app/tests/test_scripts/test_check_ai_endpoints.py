import httpx
import pytest
from typer.testing import CliRunner

from app.cli.ops import _response_json_object, app


def test_response_json_object_returns_json_object() -> None:
    response = httpx.Response(200, json={"access_token": "test-token"})
    assert _response_json_object(response, "Login") == {"access_token": "test-token"}


@pytest.mark.parametrize(
    ("response", "match"),
    [
        (httpx.Response(200, content=b"not json"), "Login returned invalid JSON"),
        (httpx.Response(200, json=["not", "an", "object"]), "Login returned JSON list; expected an object"),
    ],
)
def test_response_json_object_rejects_malformed_payloads(response: httpx.Response, match: str) -> None:
    with pytest.raises(RuntimeError, match=match):
        _response_json_object(response, "Login")
