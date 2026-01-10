"""
Security middleware configuration using fastapi-guard.

Provides rate limiting, IP filtering, and security protection for the API.
"""

import logging

from guard.handlers.ipinfo_handler import IPInfoManager
from guard.models import SecurityConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


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
            logger.warning(f"Failed to initialize IPInfo handler: {e}")

    config = SecurityConfig(
        # Rate Limiting
        rate_limit=settings.RATE_LIMIT_REQUESTS,
        rate_limit_window=settings.RATE_LIMIT_WINDOW,
        # Auto-banning for suspicious activity
        auto_ban_threshold=settings.AUTO_BAN_THRESHOLD,
        auto_ban_duration=settings.AUTO_BAN_DURATION,
        # IP Whitelisting/Blacklisting
        whitelist=settings.SECURITY_WHITELIST_IPS,
        blacklist=settings.SECURITY_BLACKLIST_IPS,
        # Redis for distributed rate limiting (production)
        enable_redis=settings.ENVIRONMENT == "production",
        redis_url=settings.redis_url if settings.ENVIRONMENT == "production" else None,
        redis_prefix="fastapi_guard:",
        # Geolocation (optional)
        geo_ip_handler=geo_ip_handler,
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
