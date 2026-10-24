import logging

import pytest
from sqlalchemy.exc import InterfaceError

from app.db import session as session_module


class _ClosingSession:
    def __init__(self, error: Exception | None = None) -> None:
        self.closed = False
        self.error = error

    async def close(self) -> None:
        self.closed = True
        if self.error is not None:
            raise self.error


@pytest.mark.asyncio
async def test_get_async_session_closes_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _ClosingSession()
    monkeypatch.setattr(session_module, "async_session_maker", lambda: fake)

    generator = session_module.get_async_session()
    assert await anext(generator) is fake

    await generator.aclose()

    assert fake.closed is True


@pytest.mark.asyncio
async def test_get_async_session_tolerates_closed_connection(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake = _ClosingSession(InterfaceError("ROLLBACK", {}, Exception("connection is closed")))
    monkeypatch.setattr(session_module, "async_session_maker", lambda: fake)

    generator = session_module.get_async_session()
    assert await anext(generator) is fake

    with caplog.at_level(logging.WARNING, logger=session_module.__name__):
        await generator.aclose()

    assert fake.closed is True
    assert "connection closed during teardown" in caplog.text
