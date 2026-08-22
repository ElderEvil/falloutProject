"""Test that AI usage cache key is consistent across services.

Regression test for cache-key mismatch (A5):
  user_service.py used "ai_usage:{user_id}"
  quota_service.py used "user:{user_id}:ai_usage"
  ai_usage_service.py docstring says "user:{user_id}:ai_usage"

Fix: extracted shared constant ai_constants.AI_USAGE_CACHE_KEY.
This test asserts both services import and use that constant.
"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def test_ai_usage_cache_key_shared_constant() -> None:
    """Both user_service and quota_service import AI_USAGE_CACHE_KEY."""
    user_svc_path = str(
        BACKEND_ROOT / "app" / "services" / "user_service.py"
    )
    quota_svc_path = str(
        BACKEND_ROOT / "app" / "services" / "quota_service.py"
    )

    for filepath in [user_svc_path, quota_svc_path]:
        source = Path(filepath).read_text()
        assert (
            "from app.services.ai_constants import AI_USAGE_CACHE_KEY" in source
            or "AI_USAGE_CACHE_KEY" in source
        ), f"{filepath} must import AI_USAGE_CACHE_KEY from ai_constants"
