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

#: Operations intentionally reachable without a bearer token, keyed by "METHOD path" so
#: a new unsecured method on an already-exempt path still fails the guard.
PUBLIC_OPERATIONS: dict[str, str] = {
    "GET /healthcheck": "infrastructure probe",
    "POST /api/v1/auth/login": "unauthenticated login",
    "POST /api/v1/auth/refresh": "refresh token exchange",
    "POST /api/v1/auth/forgot-password": "password reset request",
    "POST /api/v1/auth/reset-password": "password reset",
    "POST /api/v1/auth/verify-email": "email verification link",
    "POST /api/v1/users/open": "registration",
    "GET /api/v1/system/info": "public build info",
    "GET /api/v1/system/changelog": "public changelog",
    "GET /api/v1/system/changelog/latest": "public changelog",
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
    unsecured = [operation for operation in _unsecured_operations() if operation not in PUBLIC_OPERATIONS]

    assert not unsecured, (
        "Operations reachable without authentication. Add an auth dependency, or add the operation "
        "to PUBLIC_OPERATIONS with a reason if it is intentionally public:\n  " + "\n  ".join(unsecured)
    )


def test_guard_actually_sees_the_api() -> None:
    """A route-count floor so a silent schema/import change cannot make this vacuous."""
    documented = app.openapi()["paths"]
    assert len(documented) > 100, f"openapi only documents {len(documented)} paths; the guard would be vacuous"


def test_public_route_allowlist_has_no_dead_entries() -> None:
    """A stale entry would silently exempt an operation that no longer exists."""
    documented = _unsecured_operations()
    dead = sorted(operation for operation in PUBLIC_OPERATIONS if operation not in documented)

    assert not dead, f"PUBLIC_OPERATIONS lists operations that are no longer unsecured: {dead}"
