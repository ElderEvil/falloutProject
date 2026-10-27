"""Shared confirmation and CSRF-protected POST boundary for SQLAdmin actions."""

import secrets
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from redis.asyncio import Redis
from sqladmin.flash import flash
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.admin.csrf import issue_token, validate_token
from app.core.config import settings
from app.crud.user import user as user_crud
from app.services.account_merge_service import merge_users
from app.services.admin_service import (
    INCIDENT_BATCH_SIZE,
    describe_support_target,
    list_incident_controls,
    perform_support_action,
    set_incident_controls,
)
from app.utils.exceptions import DomainError

if TYPE_CHECKING:
    from app.admin.views import AdminModelView

ACCOUNT_MERGE_PREVIEW_SESSION_KEY = "account_merge_preview"
ACCOUNT_MERGE_PREVIEW_TTL_SECONDS = 10 * 60


def _record_id(value: str) -> UUID:
    if not value or "," in value:
        raise ValueError("Select exactly one record for this action.")
    return UUID(value)


async def confirm_action(view: "AdminModelView", request: Request, operation: str) -> Response:
    try:
        record_id = _record_id(request.query_params.get("pks", ""))
        async with view.session_maker() as session:
            target = await describe_support_target(
                session, view.identity, record_id, operation=operation, actor_id=str(request.session["user_id"])
            )
    except (DomainError, ValueError) as error:
        return await _render_error(view, request, operation, error)
    return await view.templates.TemplateResponse(
        request,
        "support_action.html",
        {
            "model_view": view,
            "title": view.support_operations[operation],
            "operation": operation,
            "record_id": str(record_id),
            "target": target,
            "csrf_token": issue_token(request),
        },
    )


async def submit_action(view: "AdminModelView", request: Request) -> Response:
    form = await request.form()
    if not validate_token(request, str(form.get("csrf_token", ""))):
        return Response("Invalid confirmation token. Reload the action and try again.", status_code=403)
    operation = str(form.get("operation", ""))
    if operation not in view.support_operations:
        return Response(status_code=400)
    try:
        record_id = _record_id(str(form.get("pks", "")))
        async with view.session_maker() as session:
            await perform_support_action(
                session, view.identity, operation, record_id, actor_id=str(request.session["user_id"])
            )
    except (DomainError, ValueError) as error:
        return await _render_error(view, request, operation, error)
    flash(request, f"{view.support_operations[operation]} completed.", category="success")
    return RedirectResponse(request.url_for("admin:list", identity=view.identity), status_code=303)


async def _render_error(
    view: "AdminModelView", request: Request, operation: str, error: DomainError | ValueError
) -> Response:
    return await view.templates.TemplateResponse(
        request,
        "support_action.html",
        {
            "model_view": view,
            "title": view.support_operations.get(operation, "Vault incident controls"),
            "error": error.detail if isinstance(error, DomainError) else str(error),
        },
        status_code=error.status_code if isinstance(error, DomainError) else 400,
    )


async def _render_merge_form(
    view: Any,
    request: Request,
    *,
    source: str = "",
    target: str = "",
    reason: str = "",
    q: str = "",
    search_results: list[Any] | None = None,
    error: DomainError | ValueError | None = None,
    status_code: int = 200,
) -> Response:
    return await view.templates.TemplateResponse(
        request,
        "merge_accounts.html",
        {
            "title": "Merge accounts",
            "csrf_token": issue_token(request),
            "source": source,
            "target": target,
            "reason": reason,
            "q": q,
            "search_results": search_results or [],
            "error": (error.detail if isinstance(error, DomainError) else str(error) if error is not None else None),
        },
        status_code=status_code,
    )


def _issue_merge_preview(request: Request, preview: Any, actor_id: str, reason: str) -> str:
    token = secrets.token_urlsafe(24)
    request.session[ACCOUNT_MERGE_PREVIEW_SESSION_KEY] = {
        "token": token,
        "source_id": str(preview.source_id),
        "target_id": str(preview.target_id),
        "actor_id": str(actor_id),
        "reason": reason,
        "issued_at": time.time(),
    }
    return token


def _read_merge_preview(request: Request, submitted: str, actor_id: str) -> dict[str, Any] | None:
    state = request.session.get(ACCOUNT_MERGE_PREVIEW_SESSION_KEY)
    if not isinstance(state, dict):
        return None
    if not secrets.compare_digest(str(state.get("token", "")), submitted):
        return None
    if str(state.get("actor_id", "")) != str(actor_id):
        return None
    issued_at = state.get("issued_at")
    if not isinstance(issued_at, (int, float)) or time.time() - issued_at > ACCOUNT_MERGE_PREVIEW_TTL_SECONDS:
        request.session.pop(ACCOUNT_MERGE_PREVIEW_SESSION_KEY, None)
        return None
    return state


async def _search_merge_users(view: Any, query: str) -> list[Any]:
    if not query:
        return []
    async with view.session_maker() as session:
        return await user_crud.search_identities(session, query, limit=20)


async def render_merge_accounts(view: Any, request: Request) -> Response:
    """Render the merge form or execute a CSRF-protected preview/apply."""
    if request.method == "GET":
        request.session.pop(ACCOUNT_MERGE_PREVIEW_SESSION_KEY, None)
        q = request.query_params.get("q", "").strip()
        return await _render_merge_form(
            view,
            request,
            source=request.query_params.get("source", "").strip(),
            target=request.query_params.get("target", "").strip(),
            q=q,
            search_results=await _search_merge_users(view, q),
        )

    form = await request.form()
    if not validate_token(request, str(form.get("csrf_token", ""))):
        return Response("Invalid confirmation token. Reload the page and try again.", status_code=403)

    action = str(form.get("action", ""))
    actor_id = request.session.get("user_id")
    if not actor_id:
        return Response(status_code=403)

    if action == "apply":
        state = _read_merge_preview(request, str(form.get("preview_token", "")), str(actor_id))
        if state is None:
            return await _render_merge_form(
                view,
                request,
                error=ValueError("Preview expired or missing. Preview the merge again before applying."),
                status_code=400,
            )
        source = str(state["source_id"])
        target = str(state["target_id"])
        reason = str(state["reason"])
    elif action == "preview":
        source = str(form.get("source", "")).strip()
        target = str(form.get("target", "")).strip()
        reason = str(form.get("reason", "")).strip()
        if not source or not target or not reason or len(reason) > 500:
            return await _render_merge_form(
                view,
                request,
                source=source,
                target=target,
                reason=reason,
                error=ValueError("Source, target, and a reason of at most 500 characters are required."),
                status_code=400,
            )
    else:
        return await _render_merge_form(view, request, status_code=400)

    redis_client: Redis | None = None
    try:
        if action == "apply":
            redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        async with view.session_maker() as session:
            preview = await merge_users(
                session,
                source,
                target,
                actor=str(actor_id),
                reason=reason,
                dry_run=action == "preview",
                redis_client=redis_client,
            )
    except (DomainError, ValueError) as error:
        request.session.pop(ACCOUNT_MERGE_PREVIEW_SESSION_KEY, None)
        return await _render_merge_form(
            view,
            request,
            source=source,
            target=target,
            reason=reason,
            error=error,
            status_code=error.status_code if isinstance(error, DomainError) else 400,
        )
    finally:
        if redis_client is not None:
            await redis_client.aclose()

    if action == "preview":
        preview_token = _issue_merge_preview(request, preview, str(actor_id), reason)
        return await view.templates.TemplateResponse(
            request,
            "merge_accounts.html",
            {
                "title": "Merge accounts",
                "csrf_token": issue_token(request),
                "source": source,
                "target": target,
                "reason": reason,
                "preview": preview,
                "preview_token": preview_token,
            },
        )

    request.session.pop(ACCOUNT_MERGE_PREVIEW_SESSION_KEY, None)
    if preview.already_merged:
        flash(request, f"Already merged (audit {preview.audit_id}).", category="info")
    else:
        flash(request, f"Merge completed (audit {preview.audit_id}).", category="success")
    if preview.token_invalidation_failed:
        flash(request, "Merge completed, but the source refresh token could not be invalidated.", category="warning")
    if preview.audit_id is not None:
        destination = request.url_for("admin:details", identity="account-merge", pk=str(preview.audit_id))
    else:
        destination = request.url_for("admin:list", identity="account-merge")
    return RedirectResponse(destination, status_code=303)


async def render_incident_controls(view: "AdminModelView", request: Request) -> Response:
    try:
        page = int(request.query_params.get("page", "1"))
        async with view.session_maker() as session:
            vaults = await list_incident_controls(session, page)
    except (DomainError, ValueError) as error:
        return await _render_error(view, request, "incidents", error)
    return await view.templates.TemplateResponse(
        request,
        "vault_incidents.html",
        {
            "vaults": vaults[:INCIDENT_BATCH_SIZE],
            "has_next": len(vaults) > INCIDENT_BATCH_SIZE,
            "page": page,
            "csrf_token": issue_token(request),
        },
    )


async def submit_incident_controls(view: "AdminModelView", request: Request) -> Response:
    form = await request.form()
    if not validate_token(request, str(form.get("csrf_token", ""))):
        return Response(status_code=403)
    operation = str(form.get("action", ""))
    scope = str(form.get("scope", ""))
    if operation not in ("disable", "enable") or scope not in ("selected", "all"):
        return Response(status_code=400)
    try:
        ids = None if scope == "all" else [UUID(str(value)) for value in form.getlist("vault_id")]
        async with view.session_maker() as session:
            count = await set_incident_controls(
                session, disabled=operation == "disable", vault_ids=ids, actor_id=str(request.session["user_id"])
            )
    except (DomainError, ValueError) as error:
        return await _render_error(view, request, "incidents", error)
    flash(request, f"Updated incident settings for {count} vaults.", category="success")
    return RedirectResponse(request.url_for("admin:view-vault-incidents_page"), status_code=303)
