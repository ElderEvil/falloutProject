"""OAuth sign-in endpoints: provider discovery, authorize, callback, handoff."""

import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_redis_client
from app.core.config import settings
from app.db.session import get_async_session
from app.schemas.oauth import (
    OAuthHandoffRequest,
    OAuthLinkAuthorizeResponse,
    OAuthLinkedAccountsResponse,
    OAuthProvidersResponse,
)
from app.schemas.token import Token
from app.services.oauth_service import (
    OAUTH_BROWSER_COOKIE_MAX_AGE,
    OAUTH_BROWSER_COOKIE_NAME,
    oauth_service,
)
from app.utils.exceptions import OAuthFlowError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oauth", tags=["Authentication"])

DbSession = Annotated[AsyncSession, Depends(get_async_session)]
RedisClient = Annotated[Redis, Depends(get_redis_client)]


def _frontend_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(
        f"{settings.FRONTEND_URL}/auth/callback?{urlencode(params)}",
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/providers", response_model=OAuthProvidersResponse)
async def list_oauth_providers(response: Response) -> OAuthProvidersResponse:
    """Report which providers have a complete credential pair configured."""
    response.headers["Cache-Control"] = "no-store"
    return OAuthProvidersResponse(**oauth_service.providers())


@router.get("/accounts", response_model=OAuthLinkedAccountsResponse)
async def list_linked_accounts(
    current_user: CurrentActiveUser,
    db_session: DbSession,
    response: Response,
) -> OAuthLinkedAccountsResponse:
    """List the provider identities linked to the signed-in account."""
    response.headers["Cache-Control"] = "no-store"
    providers = await oauth_service.list_linked_accounts(db_session, current_user.id)
    return OAuthLinkedAccountsResponse(
        providers=providers,
        has_password=bool(current_user.hashed_password),
    )


@router.post("/{provider}/link", response_model=OAuthLinkAuthorizeResponse)
async def link_provider(
    provider: str,
    request: Request,
    current_user: CurrentActiveUser,
    db_session: DbSession,
    redis_client: RedisClient,
    response: Response,
) -> OAuthLinkAuthorizeResponse:
    """Start an authenticated provider link; the callback binds to this account."""
    authorize_url, browser_token = await oauth_service.start_link(
        provider,
        current_user.id,
        request.cookies.get(OAUTH_BROWSER_COOKIE_NAME),
        db_session,
        redis_client,
    )
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        OAUTH_BROWSER_COOKIE_NAME,
        browser_token,
        max_age=OAUTH_BROWSER_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "local",
        path=f"{settings.API_V1_STR}/auth/oauth",
    )
    return OAuthLinkAuthorizeResponse(authorize_url=authorize_url)


@router.delete("/{provider}", status_code=204)
async def unlink_provider(
    provider: str,
    current_user: CurrentActiveUser,
    db_session: DbSession,
) -> Response:
    """Remove a provider link, refusing to remove the last sign-in method."""
    await oauth_service.unlink_provider(db_session, current_user.id, provider)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/{provider}/authorize")
async def authorize_provider(provider: str, request: Request, redis_client: RedisClient) -> RedirectResponse:
    """Start the provider consent redirect and bind the flow to this browser."""
    authorize_url, browser_token = await oauth_service.start(
        provider, request.cookies.get(OAUTH_BROWSER_COOKIE_NAME), redis_client
    )
    response = RedirectResponse(authorize_url, status_code=302, headers={"Cache-Control": "no-store"})
    response.set_cookie(
        OAUTH_BROWSER_COOKIE_NAME,
        browser_token,
        max_age=OAUTH_BROWSER_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "local",
        path=f"{settings.API_V1_STR}/auth/oauth",
    )
    return response


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    db_session: DbSession,
    redis_client: RedisClient,
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    """Exchange the provider code, then hand off to the SPA without tokens in the URL."""
    provider_error = request.query_params.get("error")
    if provider_error:
        try:
            await oauth_service.discard_state(state or "", redis_client)
        except Exception:
            logger.exception("Failed to discard OAuth state")
            return _frontend_redirect(error="oauth_failed")
        code_name = "access_denied" if provider_error == "access_denied" else "provider_error"
        return _frontend_redirect(error=code_name)
    browser_token = request.cookies.get(OAUTH_BROWSER_COOKIE_NAME)
    if not browser_token:
        return _frontend_redirect(error="state_invalid")
    try:
        completion = await oauth_service.complete_flow(
            provider, code or "", state or "", browser_token, db_session, redis_client
        )
        if completion.purpose == "link":
            return _frontend_redirect(linked=provider)
        handoff_code = await oauth_service.create_handoff(completion.user.id, browser_token, redis_client)
    except OAuthFlowError as exc:
        return _frontend_redirect(error=exc.code)
    except Exception:
        logger.exception("OAuth callback failed")
        return _frontend_redirect(error="oauth_failed")
    return _frontend_redirect(code=handoff_code, provider=provider)


@router.post("/handoff", response_model=Token)
async def redeem_handoff(
    payload: OAuthHandoffRequest,
    request: Request,
    response: Response,
    db_session: DbSession,
    redis_client: RedisClient,
) -> Token:
    """Redeem a single-use handoff code for the token pair, bound to this browser."""
    token = await oauth_service.redeem_handoff(
        payload.code, request.cookies.get(OAUTH_BROWSER_COOKIE_NAME), db_session, redis_client
    )
    response.headers["Cache-Control"] = "no-store"
    return token
