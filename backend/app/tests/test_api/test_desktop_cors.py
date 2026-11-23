import json
from pathlib import Path

import pytest
import yaml
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from main import app

PREFLIGHT = {"Access-Control-Request-Method": "POST"}


async def _preflight(application, origin: str, extra: dict | None = None):
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        return await client.options("/api/v1/auth/login", headers={"Origin": origin, **PREFLIGHT, **(extra or {})})


@pytest.mark.parametrize("origin", ["tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"])
async def test_desktop_api_preflight_allows_app_origins(origin: str) -> None:
    response = await _preflight(app, origin, {"Access-Control-Request-Headers": "content-type,authorization"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


async def test_desktop_api_preflight_rejects_untrusted_origin() -> None:
    response = await _preflight(app, "https://untrusted.example")
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.fixture
def production_cors_app() -> CORSMiddleware:
    manifest = Path(__file__).resolve().parents[4] / "deployment/k3s/backend-deployment.yaml"
    deployment = yaml.safe_load(manifest.read_text())
    backend = next(item for item in deployment["spec"]["template"]["spec"]["containers"] if item["name"] == "backend")
    origins = json.loads(next(item["value"] for item in backend["env"] if item["name"] == "BACKEND_CORS_ORIGINS"))
    return CORSMiddleware(app, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


@pytest.mark.parametrize(
    ("origin", "expected_status"),
    [
        ("https://fallout.evillab.tech", 200),
        ("tauri://localhost", 200),
        ("http://tauri.localhost", 200),
        ("https://tauri.localhost", 200),
        ("https://untrusted.example", 400),
    ],
)
async def test_production_manifest_preflight_policy(
    production_cors_app: CORSMiddleware, origin: str, expected_status: int
) -> None:
    response = await _preflight(production_cors_app, origin)
    assert response.status_code == expected_status
    assert response.headers.get("access-control-allow-origin") == (origin if expected_status == 200 else None)
