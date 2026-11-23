import pytest

from app.schemas.ai_usage import AIOperationStats, AIUsageResponse, AIUsageStats, QuotaInfo

PAYLOAD = {
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


def test_ai_usage_stats_defaults_and_values():
    empty = AIUsageStats()
    assert (empty.prompt_tokens, empty.completion_tokens, empty.total_tokens) == (0, 0, 0)
    filled = AIUsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert (filled.prompt_tokens, filled.completion_tokens, filled.total_tokens) == (100, 50, 150)


def test_ai_operation_stats_defaults_and_operational():
    op = AIOperationStats(operation="chat_with_dweller")
    assert (op.operation, (op.prompt_tokens, op.completion_tokens, op.total_tokens, op.count, op.is_operational)) == (
        "chat_with_dweller",
        (0, 0, 0, 0, False),
    )
    live = AIOperationStats(operation="quota_tracking", total_tokens=5, count=1, is_operational=True)
    assert (live.is_operational, live.total_tokens) == (True, 5)


def test_quota_info_defaults_and_values():
    quota = QuotaInfo()
    assert (
        (quota.quota_limit, quota.quota_used, quota.quota_remaining, quota.quota_percentage),
        (quota.quota_warning, quota.quota_exceeded, quota.reset_date),
    ) == ((100000, 0, 0, 0.0), (False, False, ""))
    filled = QuotaInfo(
        quota_limit=50000,
        quota_used=45000,
        quota_remaining=5000,
        quota_percentage=90.0,
        quota_warning=True,
        quota_exceeded=False,
        reset_date="2026-04-01",
    )
    assert (filled.quota_limit, filled.quota_used, filled.quota_remaining, filled.quota_percentage) == (
        50000,
        45000,
        5000,
        90.0,
    )
    assert (filled.quota_warning, filled.quota_exceeded, filled.reset_date) == (True, False, "2026-04-01")


def test_ai_usage_response_defaults_are_backward_compatible():
    response = AIUsageResponse.model_validate(PAYLOAD)
    assert (
        (response.by_operation, response.chat_heavy),
        (response.all_time.prompt_tokens, response.quota.quota_warning),
    ) == (([], False), (100, False))


def test_ai_usage_response_with_by_operation():
    response = AIUsageResponse.model_validate(
        {
            "all_time": {"total_tokens": 150},
            "current_month": {"total_tokens": 100},
            "quota": {"quota_limit": 100000, "quota_used": 100, "quota_remaining": 99900},
            "month": "2026-08",
            "by_operation": [
                {"operation": "chat_with_dweller", "total_tokens": 90, "count": 9},
                {"operation": "quota_tracking", "total_tokens": 10, "count": 1, "is_operational": True},
            ],
            "chat_heavy": True,
        }
    )
    assert (
        (len(response.by_operation), response.chat_heavy),
        (response.by_operation[0].operation, response.by_operation[0].count),
    ) == ((2, True), ("chat_with_dweller", 9))
    assert response.by_operation[1].is_operational is True


def test_ai_usage_response():
    response = AIUsageResponse(
        all_time=AIUsageStats(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
        current_month=AIUsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        quota=QuotaInfo(quota_limit=100000, quota_used=150, quota_remaining=99850, quota_percentage=0.15),
        month="2026-02",
    )
    assert (response.month, response.all_time.total_tokens, response.current_month.total_tokens) == (
        "2026-02",
        1500,
        150,
    )
    assert response.quota.quota_limit == 100000
