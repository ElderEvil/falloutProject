import pytest

from app.schemas.ai_usage import AIUsageResponse, AIUsageStats, QuotaInfo


class TestAIUsageSchemas:
    def test_ai_usage_stats_defaults(self):
        stats = AIUsageStats()
        assert stats.prompt_tokens == 0
        assert stats.completion_tokens == 0
        assert stats.total_tokens == 0

    def test_ai_usage_stats_with_values(self):
        stats = AIUsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert stats.prompt_tokens == 100
        assert stats.completion_tokens == 50
        assert stats.total_tokens == 150

    def test_quota_info_defaults(self):
        quota = QuotaInfo()
        assert quota.quota_limit == 100000
        assert quota.quota_used == 0
        assert quota.quota_remaining == 0
        assert quota.quota_percentage == 0.0
        assert quota.quota_warning is False
        assert quota.quota_exceeded is False
        assert quota.reset_date == ""

    def test_quota_info_with_values(self):
        quota = QuotaInfo(
            quota_limit=50000,
            quota_used=45000,
            quota_remaining=5000,
            quota_percentage=90.0,
            quota_warning=True,
            quota_exceeded=False,
            reset_date="2026-04-01",
        )
        assert quota.quota_limit == 50000
        assert quota.quota_used == 45000
        assert quota.quota_remaining == 5000
        assert quota.quota_percentage == 90.0
        assert quota.quota_warning is True
        assert quota.quota_exceeded is False
        assert quota.reset_date == "2026-04-01"

    def test_ai_usage_response(self):
        all_time = AIUsageStats(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        current_month = AIUsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        quota = QuotaInfo(quota_limit=100000, quota_used=150, quota_remaining=99850, quota_percentage=0.15)

        response = AIUsageResponse(all_time=all_time, current_month=current_month, quota=quota, month="2026-02")

        assert response.month == "2026-02"
        assert response.all_time.total_tokens == 1500
        assert response.current_month.total_tokens == 150
        assert response.quota.quota_limit == 100000

    def test_ai_usage_response_model_validate(self):
        data = {
            "all_time": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "current_month": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "quota": {
                "quota_limit": 100000,
                "quota_used": 15,
                "quota_remaining": 99985,
                "quota_percentage": 0.015,
                "quota_warning": False,
                "quota_exceeded": False,
                "reset_date": "2026-04-01",
            },
            "month": "2026-02",
        }

        response = AIUsageResponse.model_validate(data)
        assert response.all_time.prompt_tokens == 100
        assert response.quota.quota_warning is False
