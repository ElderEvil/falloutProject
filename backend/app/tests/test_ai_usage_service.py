import pytest

from app.schemas.ai_usage import AIUsageResponse, AIUsageStats


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

    def test_ai_usage_response(self):
        all_time = AIUsageStats(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        current_month = AIUsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        response = AIUsageResponse(all_time=all_time, current_month=current_month, month="2026-02")

        assert response.month == "2026-02"
        assert response.all_time.total_tokens == 1500
        assert response.current_month.total_tokens == 150

    def test_ai_usage_response_model_validate(self):
        data = {
            "all_time": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "current_month": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "month": "2026-02",
        }

        response = AIUsageResponse.model_validate(data)
        assert response.all_time.prompt_tokens == 100
