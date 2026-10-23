"""OAuth sign-in: provider flows, browser-bound state, and handoff redemption."""

import hmac
import json
import logging
import re
import secrets
from urllib.parse import urlencode
from uuid import UUID

import httpx
from pydantic import UUID4
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import OAuthProviderEnum
from app.core.security import generate_pkce_pair, hash_browser_token
from app.models.user import User
from app.schemas.token import Token
from app.services.auth_service import auth_service
from app.utils.exceptions import OAuthFlowError, ResourceConflictException

logger = logging.getLogger(__name__)

OAUTH_BROWSER_COOKIE_NAME = "oauth_bid"
OAUTH_BROWSER_COOKIE_MAX_AGE = 120 * 24 * 60 * 60
STATE_TTL_SECONDS = 600
HANDOFF_TTL_SECONDS = 60
REQUEST_TIMEOUT = 10.0

_AUTHORIZE_URLS = {
    OAuthProviderEnum.GOOGLE: "https://accounts.google.com/o/oauth2/v2/auth",
    OAuthProviderEnum.GITHUB: "https://github.com/login/oauth/authorize",
}
_TOKEN_URLS = {
    OAuthProviderEnum.GOOGLE: "https://oauth2.googleapis.com/token",
    OAuthProviderEnum.GITHUB: "https://github.com/login/oauth/access_token",
}
_SCOPES = {
    OAuthProviderEnum.GOOGLE: "openid email profile",
    OAuthProviderEnum.GITHUB: "read:user user:email",
}
_ALLOWED_PROVIDER_ERRORS = {
    "invalid_grant",
    "invalid_client",
    "invalid_request",
    "redirect_uri_mismatch",
    "unsupported_grant_type",
    "access_denied",
    "invalid_scope",
    "server_error",
    "temporarily_unavailable",
}
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_GITHUB_USER_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def _provider_error_code(response: httpx.Response) -> str:
    try:
        code = response.json().get("error")
    except ValueError:
        return "unknown"
    return code if isinstance(code, str) and code in _ALLOWED_PROVIDER_ERRORS else "unknown"


def _state_key(state: str) -> str:
    return f"oauth_state:{state}"


def _handoff_key(code: str) -> str:
    return f"oauth_handoff:{hash_browser_token(code)}"


def _google_email_is_authoritative(profile: dict) -> bool:
    """Gmail and Workspace (`hd`) mailboxes are Google-owned; third-party ones are not."""
    return bool(profile.get("hd")) or profile["email"].lower().endswith("@gmail.com")


def _username_base(profile: dict) -> str:
    raw = profile.get("name") or profile.get("login") or profile["email"].split("@")[0]
    slug = re.sub(r"[^a-z0-9_]", "", raw.lower())[:24]
    if len(slug) < 3:
        slug = f"user_{slug}"
    return slug or "user"


def _username_candidates(base: str) -> list[str]:
    candidates = [base, *(f"{base}{index}" for index in range(2, 100))]
    candidates.extend(f"{base}_{secrets.token_hex(2)}" for _ in range(10))
    return candidates


class OAuthService:
    """Provider-agnostic OAuth flow. Provider HTTP is injectable for tests."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def providers(self) -> dict[str, bool]:
        return {
            OAuthProviderEnum.GOOGLE.value: bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
            OAuthProviderEnum.GITHUB.value: bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET),
        }

    def is_enabled(self, provider: OAuthProviderEnum) -> bool:
        return self.providers()[provider.value]

    async def start(self, provider_name: str, browser_token: str | None, redis_client: Redis) -> tuple[str, str]:
        provider = self._parse_provider(provider_name)
        if not self.is_enabled(provider):
            raise OAuthFlowError("provider_disabled", status_code=404)
        browser_token = browser_token or secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        verifier, challenge = generate_pkce_pair()
        redirect_uri = self._redirect_uri(provider)
        await redis_client.setex(
            _state_key(state),
            STATE_TTL_SECONDS,
            json.dumps(
                {
                    "provider": provider.value,
                    "code_verifier": verifier,
                    "browser_hash": hash_browser_token(browser_token),
                    "redirect_uri": redirect_uri,
                }
            ),
        )
        params = {
            "client_id": self._client_id(provider),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _SCOPES[provider],
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{_AUTHORIZE_URLS[provider]}?{urlencode(params)}", browser_token

    async def complete(
        self,
        provider_name: str,
        code: str,
        state: str,
        browser_token: str | None,
        db_session: AsyncSession,
        redis_client: Redis,
    ) -> User:
        provider = self._parse_provider(provider_name)
        if not self.is_enabled(provider):
            raise OAuthFlowError("provider_disabled")
        if not code or not state:
            raise OAuthFlowError("state_invalid")
        raw_record = await redis_client.getdel(_state_key(state))
        if not raw_record:
            raise OAuthFlowError("state_invalid")
        record = json.loads(raw_record)
        if record.get("provider") != provider.value:
            raise OAuthFlowError("state_invalid")
        if not browser_token or not hmac.compare_digest(
            record.get("browser_hash", ""), hash_browser_token(browser_token)
        ):
            raise OAuthFlowError("state_invalid")
        profile = await self._exchange_code(provider, code, record["code_verifier"], record["redirect_uri"])
        return await self._resolve_user(db_session, provider, profile)

    async def discard_state(self, state: str, redis_client: Redis) -> None:
        """Consume a state record without exchanging a code (provider denial)."""
        if state:
            await redis_client.getdel(_state_key(state))

    async def create_handoff(self, user_id: UUID4, browser_token: str, redis_client: Redis) -> str:
        code = secrets.token_urlsafe(32)
        record = {"user_id": str(user_id), "browser_hash": hash_browser_token(browser_token)}
        await redis_client.setex(_handoff_key(code), HANDOFF_TTL_SECONDS, json.dumps(record))
        return code

    async def redeem_handoff(
        self,
        code: str,
        browser_token: str | None,
        db_session: AsyncSession,
        redis_client: Redis,
    ) -> Token:
        if not code or not browser_token:
            raise OAuthFlowError("handoff_invalid")
        raw_record = await redis_client.getdel(_handoff_key(code))
        if not raw_record:
            raise OAuthFlowError("handoff_invalid")
        record = json.loads(raw_record)
        if not hmac.compare_digest(record.get("browser_hash", ""), hash_browser_token(browser_token)):
            raise OAuthFlowError("handoff_invalid")
        user = await crud.user.get(db_session, UUID(record["user_id"]), include_deleted=True)
        self._assert_active(user)
        return await auth_service.issue_tokens(user, redis_client)

    def _parse_provider(self, name: str) -> OAuthProviderEnum:
        try:
            return OAuthProviderEnum(name)
        except ValueError as exc:
            raise OAuthFlowError("provider_disabled", status_code=404) from exc

    def _redirect_uri(self, provider: OAuthProviderEnum) -> str:
        base = settings.OAUTH_REDIRECT_BASE.rstrip("/")
        return f"{base}{settings.API_V1_STR}/auth/oauth/{provider.value}/callback"

    def _client_id(self, provider: OAuthProviderEnum) -> str:
        if provider is OAuthProviderEnum.GOOGLE:
            return settings.GOOGLE_CLIENT_ID or ""
        return settings.GITHUB_CLIENT_ID or ""

    def _client_secret(self, provider: OAuthProviderEnum) -> str:
        if provider is OAuthProviderEnum.GOOGLE:
            return settings.GOOGLE_CLIENT_SECRET or ""
        return settings.GITHUB_CLIENT_SECRET or ""

    async def _exchange_code(
        self, provider: OAuthProviderEnum, code: str, verifier: str, redirect_uri: str
    ) -> dict:
        payload = {
            "client_id": self._client_id(provider),
            "client_secret": self._client_secret(provider),
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(transport=self._transport, timeout=REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(
                    _TOKEN_URLS[provider], data=payload, headers={"Accept": "application/json"}
                )
            except httpx.HTTPError as exc:
                logger.exception("OAuth token exchange failed")
                raise OAuthFlowError("provider_error") from exc
            if response.status_code != 200:
                logger.warning(
                    "OAuth token exchange rejected: provider=%s status=%s error=%s",
                    provider.value,
                    response.status_code,
                    _provider_error_code(response),
                )
                raise OAuthFlowError("provider_error")
            try:
                token = response.json().get("access_token")
            except ValueError as exc:
                raise OAuthFlowError("provider_error") from exc
            if not token:
                raise OAuthFlowError("provider_error")
            if provider is OAuthProviderEnum.GOOGLE:
                return await self._google_profile(client, token)
            return await self._github_profile(client, token)

    async def _google_profile(self, client: httpx.AsyncClient, access_token: str) -> dict:
        try:
            response = await client.get(
                _GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
        except httpx.HTTPError as exc:
            logger.exception("Google userinfo failed")
            raise OAuthFlowError("provider_error") from exc
        if response.status_code != 200:
            logger.warning(
                "Google userinfo rejected: status=%s error=%s",
                response.status_code,
                _provider_error_code(response),
            )
            raise OAuthFlowError("provider_error")
        data = response.json()
        if not data.get("sub"):
            raise OAuthFlowError("provider_error")
        if not data.get("email") or data.get("email_verified") is not True:
            raise OAuthFlowError("email_unverified")
        return {
            "provider_user_id": str(data["sub"]),
            "email": data["email"],
            "name": data.get("name"),
            "hd": data.get("hd"),
        }

    async def _github_profile(self, client: httpx.AsyncClient, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
        try:
            user_response = await client.get(_GITHUB_USER_URL, headers=headers)
            emails_response = await client.get(_GITHUB_EMAILS_URL, headers=headers)
        except httpx.HTTPError as exc:
            logger.exception("GitHub profile fetch failed")
            raise OAuthFlowError("provider_error") from exc
        if user_response.status_code != 200 or emails_response.status_code != 200:
            raise OAuthFlowError("provider_error")
        user = user_response.json()
        emails = emails_response.json()
        if not user.get("id"):
            raise OAuthFlowError("provider_error")
        chosen = next(
            (entry for entry in emails if entry.get("primary") and entry.get("verified")),
            next((entry for entry in emails if entry.get("verified")), None),
        )
        if chosen is None:
            raise OAuthFlowError("email_unverified")
        return {
            "provider_user_id": str(user["id"]),
            "email": chosen["email"],
            "login": user.get("login"),
        }

    async def _resolve_user(self, db_session: AsyncSession, provider: OAuthProviderEnum, profile: dict) -> User:
        for _attempt in range(2):
            link = await crud.oauth_account.get_by_provider_subject(
                db_session, provider.value, profile["provider_user_id"]
            )
            if link is not None:
                return self._assert_active(await crud.user.get(db_session, link.user_id, include_deleted=True))

            existing = await crud.user.get_by_email(db_session, email=profile["email"], include_deleted=True)
            if existing is None:
                break
            linked = await self._link_existing(db_session, provider, profile, existing)
            if linked is not None:
                return linked

        # New account: never mark a Google third-party mailbox as locally verified.
        if provider is OAuthProviderEnum.GOOGLE and not _google_email_is_authoritative(profile):
            raise OAuthFlowError("email_verification_required")
        if not settings.USERS_OPEN_REGISTRATION:
            raise OAuthFlowError("registration_closed")
        return await self._create_user(db_session, provider, profile)

    async def _link_existing(
        self, db_session: AsyncSession, provider: OAuthProviderEnum, profile: dict, existing: User
    ) -> User | None:
        """Revalidate under a row lock, then commit the link while still holding it.

        Returns ``None`` when the locked row no longer matches the provider email
        (concurrent email change), so the caller can re-resolve.
        """
        locked = await crud.user.get_for_update(db_session, existing.id)
        if locked is None or locked.is_deleted:
            raise OAuthFlowError("account_deleted")
        if locked.email != profile["email"]:
            return None
        if not locked.email_verified:
            raise OAuthFlowError("local_account_unverified")
        if provider is OAuthProviderEnum.GOOGLE and not _google_email_is_authoritative(profile):
            raise OAuthFlowError("account_exists_challenge")
        existing_link = await crud.oauth_account.get_for_user(db_session, locked.id, provider.value)
        if existing_link is not None:
            if existing_link.provider_user_id == profile["provider_user_id"]:
                return locked
            raise OAuthFlowError("provider_already_linked")
        self._assert_active(locked)
        await crud.oauth_account.link_to_user(
            db_session,
            user_id=locked.id,
            provider=provider.value,
            provider_user_id=profile["provider_user_id"],
        )
        return locked

    async def _create_user(self, db_session: AsyncSession, provider: OAuthProviderEnum, profile: dict) -> User:
        for username in _username_candidates(_username_base(profile)):
            try:
                user, _ = await crud.user.create_with_oauth_account(
                    db_session,
                    provider=provider.value,
                    provider_user_id=profile["provider_user_id"],
                    username=username,
                    email=profile["email"],
                )
            except ResourceConflictException:
                link = await crud.oauth_account.get_by_provider_subject(
                    db_session, provider.value, profile["provider_user_id"]
                )
                if link is not None:
                    return self._assert_active(await crud.user.get(db_session, link.user_id, include_deleted=True))
                existing = await crud.user.get_by_email(db_session, email=profile["email"], include_deleted=True)
                if existing is not None:
                    linked = await self._link_existing(db_session, provider, profile, existing)
                    if linked is not None:
                        return linked
                continue
            return user
        raise OAuthFlowError("oauth_failed")

    def _assert_active(self, user: User | None) -> User:
        if user is None or user.is_deleted:
            raise OAuthFlowError("account_deleted")
        if not user.is_active:
            raise OAuthFlowError("account_inactive")
        return user


oauth_service = OAuthService()
