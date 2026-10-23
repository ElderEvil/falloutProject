"""Shared confirmation and CSRF-protected POST boundary for SQLAdmin actions."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqladmin.flash import flash
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.admin.csrf import issue_token, validate_token
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


def _record_id(value: str) -> UUID:
    if not value or "," in value:
        raise ValueError("Select exactly one record for this action.")
    return UUID(value)


async def confirm_action(view: "AdminModelView", request: Request, operation: str) -> Response:
    try:
        record_id = _record_id(request.query_params.get("pks", ""))
        async with view.session_maker() as session:
            target = await describe_support_target(session, view.identity, record_id)
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
