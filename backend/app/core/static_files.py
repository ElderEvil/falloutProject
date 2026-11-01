"""Cache public catalog files while retaining Starlette's validators and path checks."""

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class CachedStaticFiles(StaticFiles):
    """Use a bounded lifetime because catalog URLs can be replaced in place."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in {200, 206, 304}:
            response.headers["Cache-Control"] = "public, max-age=604800"
            # The API is a different origin from the frontend. fastapi-guard emits
            # CORP: same-origin on every response, which makes Chrome reject
            # cross-origin <img> loads. Catalog images are intentionally public.
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        return response
