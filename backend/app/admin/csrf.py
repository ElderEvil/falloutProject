"""CSRF token helpers for the SQLAdmin panel.

SQLAdmin registers every ``@action`` as a state-changing GET and adds no CSRF
validation of its own, so the vault incident toggles are replaced with a
session-backed CSRF-protected POST page. These helpers issue and validate the
token stored in the admin session (``SessionMiddleware`` is configured in
``main.py``).
"""

import secrets

from starlette.requests import Request

CSRF_SESSION_KEY = "admin_csrf_token"


def issue_token(request: Request) -> str:
    """Return the session's CSRF token, creating and storing one if absent."""
    token = request.session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def validate_token(request: Request, submitted: str | None) -> bool:
    """Return True when the submitted token matches the session token."""
    expected = request.session.get(CSRF_SESSION_KEY)
    if not isinstance(expected, str) or not submitted:
        return False
    return secrets.compare_digest(expected, submitted)
