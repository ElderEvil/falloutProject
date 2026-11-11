from unittest.mock import AsyncMock, Mock

import pytest

import main


async def test_lifespan_cleans_up_when_startup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main.HealthCheckService,
        "check_all_services",
        AsyncMock(side_effect=RuntimeError("health check failed")),
    )
    shutdown = Mock()
    stop_redis = AsyncMock()
    monkeypatch.setattr(main.evaluator_manager, "shutdown", shutdown)
    monkeypatch.setattr(main.manager, "stop_redis", stop_redis)

    with pytest.raises(RuntimeError, match="health check failed"):
        async with main.lifespan(main.app):
            pytest.fail("startup should fail before entering the lifespan")

    shutdown.assert_called_once_with()
    stop_redis.assert_awaited_once_with()
