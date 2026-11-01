"""
Security middleware configuration using fastapi-guard.

Provides rate limiting, IP filtering, and security protection for the API.
"""

import logging

from guard import IPInfoManager, SecurityConfig

from app.core.config import settings

logger = logging.getLogger(__name__)

# Credential and account-recovery endpoints need a much tighter budget than the
# normal roster/tick traffic. Paths are exact because fastapi-guard matches the
# request path verbatim for static endpoint limits.
# fastapi-guard overwrites, rather than setdefaults, the security headers on the
# response. The frontend and API are different origins, so the default
# ``Cross-Origin-Resource-Policy: same-origin`` makes Chrome reject public
# catalog images such as dweller portraits. Keep the other guard defaults and
# relax only CORP for this public API.
_SECURITY_HEADERS = {
    "enabled": True,
    "hsts": {"max_age": 31536000, "include_subdomains": True, "preload": False},
    "csp": None,
    "frame_options": "SAMEORIGIN",
    "content_type_options": "nosniff",
    "xss_protection": "1; mode=block",
    "referrer_policy": "strict-origin-when-cross-origin",
    "permissions_policy": "geolocation=(), microphone=(), camera=()",
    "custom": {"Cross-Origin-Resource-Policy": "cross-origin"},
}

_AUTH_ENDPOINT_RATE_LIMITS = {
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/refresh": (30, 60),
    "/api/v1/auth/forgot-password": (5, 60),
    "/api/v1/auth/reset-password": (5, 60),
    "/api/v1/auth/resend-verification": (3, 60),
    "/api/v1/users/open": (5, 60),
}


def create_security_config() -> SecurityConfig:
    """
    Create security configuration for fastapi-guard middleware.

    Returns:
        SecurityConfig: Configured security settings
    """
    # Optional: Initialize geolocation handler if token is provided
    geo_ip_handler = None
    if settings.IPINFO_TOKEN:
        try:
            geo_ip_handler = IPInfoManager(settings.IPINFO_TOKEN)
            logger.info("IPInfo geolocation enabled")
        except (ValueError, RuntimeError) as e:
            logger.warning("Failed to initialize IPInfo handler: %s", e)

    config = SecurityConfig(
        exclude_paths=[
            "/docs",
            "/redoc",
            "/openapi.json",
            "/openapi.yaml",
            "/favicon.ico",
            "/static",
            "/healthcheck",
            "/readiness",
            "/api/v1/system/changelog",
            "/api/v1/system/changelog/latest",
        ],
        # Rate Limiting
        rate_limit=settings.RATE_LIMIT_REQUESTS,
        rate_limit_window=settings.RATE_LIMIT_WINDOW,
        endpoint_rate_limits=_AUTH_ENDPOINT_RATE_LIMITS,
        # Regex penetration detection scans every header/body on every request.
        # In production it measured ~185ms/request in cProfile, while the local
        # guard benchmark dropped from 38ms to 0.4ms with it disabled. Auth,
        # rate limiting, CORS and security headers remain enabled.
        enable_penetration_detection=False,
        # Auto-banning for suspicious activity
        auto_ban_threshold=settings.AUTO_BAN_THRESHOLD,
        auto_ban_duration=settings.AUTO_BAN_DURATION,
        # IP Whitelisting/Blacklisting
        whitelist=settings.SECURITY_WHITELIST_IPS,
        blacklist=settings.SECURITY_BLACKLIST_IPS,
        # Resolve the client from Traefik's forwarded chain. The backend must only
        # trust the Kubernetes pod network, never arbitrary X-Forwarded-For input.
        trusted_proxies=tuple(settings.SECURITY_TRUSTED_PROXIES),
        trusted_proxy_depth=settings.SECURITY_TRUSTED_PROXY_DEPTH,
        # Redis for distributed rate limiting (production)
        enable_redis=settings.ENVIRONMENT == "production",
        redis_url=settings.redis_url if settings.ENVIRONMENT == "production" else None,
        redis_prefix="fastapi_guard:",
        redis_fail_open=settings.SECURITY_REDIS_FAIL_OPEN,
        geo_ip_handler=geo_ip_handler,
        security_headers=_SECURITY_HEADERS,
        # Block cloud providers (optional - can enable in production)
        block_cloud_providers=None,  # Set to {'AWS', 'GCP', 'Azure'} to block
        # Blocked user agents (optional)
        blocked_user_agents=[
            # Example: Block known scrapers
            # "curl",
            # "wget",
            # "BadBot/1.0",
            # "Scraper/2.0",
        ],
        # Traefik injects its private pod address here; it is trusted routing
        # metadata, not user-controlled request content to scan.
        excluded_detection_headers={"x-forwarded-for"},
    )

    logger.info(
        "Security middleware configured",
        extra={
            "rate_limit": settings.RATE_LIMIT_REQUESTS,
            "rate_limit_window": settings.RATE_LIMIT_WINDOW,
            "auto_ban_threshold": settings.AUTO_BAN_THRESHOLD,
            "redis_enabled": config.enable_redis,
            "environment": settings.ENVIRONMENT,
        },
    )

    return config
