"""Static catalog files retain validators and never cache missing-file responses."""

from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.routing import Mount

from main import app


async def test_static_catalog_cache_and_revalidation():
    static_route = next(route for route in app.routes if isinstance(route, Mount) and route.path == "/static")
    static_app = Starlette(routes=[static_route])
    async with AsyncClient(transport=ASGITransport(app=static_app), base_url="http://test") as client:
        response = await client.get("/static/room_images/Vault%20Door%20Adv.png")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=604800"
        assert response.headers["content-type"] == "image/png"
        assert response.headers["cross-origin-resource-policy"] == "cross-origin"
        head = await client.head("/static/room_images/Vault%20Door%20Adv.png")
        assert head.headers["cache-control"] == response.headers["cache-control"]
        assert head.content == b""
        unchanged = await client.get(
            "/static/room_images/Vault%20Door%20Adv.png", headers={"If-None-Match": response.headers["etag"]}
        )
        assert unchanged.status_code == 304
        assert unchanged.headers["cache-control"] == response.headers["cache-control"]
        missing = await client.get("/static/does-not-exist.png")
        assert missing.status_code == 404
        assert "cache-control" not in missing.headers
        traversal = await client.get("/static/%2e%2e/main.py")
        assert traversal.status_code == 404
