"""Guard: every API route must require authentication unless explicitly public.

The 2026-09-01 audit found unauthenticated state-mutating endpoints (the dev
debug router, then the weapon/junk/outfit/objective routers). This test keeps
that class of regression out: a new route without an auth dependency fails the
suite unless it is listed in PUBLIC_ROUTES with a reason.

The OpenAPI schema is the source of truth here — FastAPI's ``app.routes`` is
lazy about included routers, so walking it alone sees almost no routes and the
guard would pass vacuously.
"""

from main import app

#: Paths that are intentionally reachable without a bearer token.
PUBLIC_ROUTES: dict[str, str] = {
    "/healthcheck": "infrastructure probe",
    "/api/v1/auth/login": "unauthenticated login",
    "/api/v1/auth/refresh": "refresh token exchange",
    "/api/v1/auth/forgot-password": "password reset request",
    "/api/v1/auth/reset-password": "password reset",
    "/api/v1/auth/verify-email": "email verification link",
    "/api/v1/users/open": "registration",
    "/api/v1/system/info": "public build info",
    "/api/v1/system/changelog": "public changelog",
    "/api/v1/system/changelog/latest": "public changelog",
}

HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _unsecured_operations() -> list[str]:
    """Every documented operation that advertises no security requirement."""
    spec = app.openapi()
    return sorted(
        f"{method.upper()} {path}"
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if method in HTTP_METHODS and not operation.get("security")
    )


def test_every_route_requires_authentication() -> None:
    unsecured = [operation for operation in _unsecured_operations() if operation.split(" ", 1)[1] not in PUBLIC_ROUTES]

    assert not unsecured, (
        "Routes reachable without authentication. Add an auth dependency, or add the path to "
        "PUBLIC_ROUTES with a reason if it is intentionally public:\n  " + "\n  ".join(unsecured)
    )


def test_guard_actually_sees_the_api() -> None:
    """A route-count floor so a silent schema/import change cannot make this vacuous."""
    documented = app.openapi()["paths"]
    assert len(documented) > 100, f"openapi only documents {len(documented)} paths; the guard would be vacuous"


def test_public_route_allowlist_has_no_dead_entries() -> None:
    """A stale allowlist entry would silently exempt a route that no longer exists."""
    documented = set(app.openapi()["paths"])
    dead = sorted(path for path in PUBLIC_ROUTES if path not in documented)

    assert not dead, f"PUBLIC_ROUTES lists paths that are not documented routes: {dead}"
