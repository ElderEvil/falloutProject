"""Exploration triage tests: Jev advisory label, never authoritative."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.exploration.triage import EventTriage, triage_description
from app.services.jev_service import JevDecision


def _decision(kind: str, confidence: float) -> JevDecision[EventTriage]:
    return JevDecision(
        output=EventTriage(event_kind=kind),
        confidence={"event_kind": confidence},
        model_name="jev-1.13.0",
    )


@pytest.mark.asyncio
async def test_returns_category_above_threshold() -> None:
    with (
        patch("app.services.exploration.triage.is_configured", return_value=True),
        patch(
            "app.services.exploration.triage.jev_service.decide",
            new=AsyncMock(return_value=_decision("combat", 0.95)),
        ),
    ):
        result = await triage_description("Raiders ambush the dweller.")

    assert result.category == "combat"
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_drops_category_below_threshold() -> None:
    with (
        patch("app.services.exploration.triage.is_configured", return_value=True),
        patch(
            "app.services.exploration.triage.jev_service.decide",
            new=AsyncMock(return_value=_decision("loot", 0.5)),
        ),
    ):
        result = await triage_description("The dweller finds a crate.")

    assert result.category is None


@pytest.mark.asyncio
async def test_unconfigured_never_calls_jev() -> None:
    decide = AsyncMock()
    with (
        patch("app.services.exploration.triage.is_configured", return_value=False),
        patch("app.services.exploration.triage.jev_service.decide", new=decide),
    ):
        result = await triage_description("anything")

    assert result.category is None
    decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_jev_failure_is_swallowed() -> None:
    with (
        patch("app.services.exploration.triage.is_configured", return_value=True),
        patch(
            "app.services.exploration.triage.jev_service.decide",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result = await triage_description("something happened")

    assert result.category is None


@pytest.mark.asyncio
async def test_blank_description_is_skipped() -> None:
    decide = AsyncMock()
    with (
        patch("app.services.exploration.triage.is_configured", return_value=True),
        patch("app.services.exploration.triage.jev_service.decide", new=decide),
    ):
        result = await triage_description("   ")

    assert result.category is None
    decide.assert_not_awaited()
