"""Jev decision-service tests (no live API needed)."""

from typing import Annotated, Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, ConfigDict
from pydantic_ai import BoolCriteria

from app.services.jev_service import JevDecision, is_configured, jev_service
from app.utils.exceptions import FeatureDisabledException


class Triage(BaseModel):
    """Should the dweller keep exploring?"""

    model_config = ConfigDict(use_attribute_docstrings=True)

    continue_run: Annotated[
        bool,
        BoolCriteria(true="The dweller can keep going safely.", false="The dweller should return now."),
    ]
    """Should the dweller continue exploring?"""

    risk: Literal["low", "medium", "high"]
    """How risky is continuing?"""


def _fake_agent(result: object) -> MagicMock:
    agent = MagicMock()
    agent.run = AsyncMock(return_value=result)
    return agent


def _run_result(output: BaseModel, confidence: dict[str, float], model_name: str) -> MagicMock:
    result = MagicMock()
    result.output = output
    result.response.provider_details = {"confidence": confidence}
    result.response.model_name = model_name
    return result


@pytest.mark.asyncio
async def test_decide_returns_typed_output_and_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.jev_service.is_configured", lambda: True)
    expected = Triage(continue_run=False, risk="high")
    result = _run_result(expected, {"continue_run": 0.84, "risk": 0.98}, "jev-1.13.0")

    with patch.object(jev_service, "_build_agent", return_value=_fake_agent(result)):
        decision = await jev_service.decide("low health, no supplies", Triage)

    assert isinstance(decision, JevDecision)
    assert decision.output == expected
    assert decision.confidence_for("risk") == 0.98
    assert decision.model_name == "jev-1.13.0"


@pytest.mark.asyncio
async def test_decide_missing_confidence_field_reads_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.jev_service.is_configured", lambda: True)
    result = _run_result(Triage(continue_run=True, risk="low"), {}, "jev-1.13.0")

    with patch.object(jev_service, "_build_agent", return_value=_fake_agent(result)):
        decision = await jev_service.decide("all good", Triage)

    assert decision.confidence_for("continue_run") == 0.0


@pytest.mark.asyncio
async def test_decide_raises_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.jev_service.is_configured", lambda: False)

    with pytest.raises(FeatureDisabledException):
        await jev_service.decide("anything", Triage)


def test_is_configured_requires_both_flag_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.jev_service.settings.JEV_ENABLED", True)
    monkeypatch.setattr("app.services.jev_service.settings.TYPESAFE_API_KEY", "k")
    assert is_configured() is True

    monkeypatch.setattr("app.services.jev_service.settings.JEV_ENABLED", False)
    assert is_configured() is False


def test_built_agent_reads_the_key_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider must be built from settings.TYPESAFE_API_KEY, not the process env.

    The spent-by-name path Agent(typesafe:...) reads the OS environment; settings loads
    .env, so that path has no key and fails auth in-app. Assert the provider is
    constructed with the settings value while the env var is absent.
    """
    pytest.importorskip("typesafe_sdk", reason="requires the typesafe test dependency group")
    from pydantic_ai.providers.typesafe import TypeSafeProvider

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr("app.services.jev_service.settings.TYPESAFE_API_KEY", "settings-only-key")

    real_provider = TypeSafeProvider

    class SpyProvider(real_provider):  # type: ignore[misc, valid-type]
        seen_key: str | None = None

        def __init__(self, *, api_key: str | None = None, **kwargs) -> None:
            SpyProvider.seen_key = api_key
            super().__init__(api_key=api_key, **kwargs)

    monkeypatch.setattr("pydantic_ai.providers.typesafe.TypeSafeProvider", SpyProvider)

    jev_service._build_agent(Triage, instructions=None, model=None)

    assert SpyProvider.seen_key == "settings-only-key"


def test_agent_carries_the_decision_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """decide() bounds the call: a hanging provider must raise, not hold the caller's transaction."""
    import asyncio

    monkeypatch.setattr("app.services.jev_service.is_configured", lambda: True)
    monkeypatch.setattr("app.services.jev_service.settings.JEV_TIMEOUT_SECONDS", 0.01)

    class HangingAgent:
        async def run(self, *_args, **_kwargs):
            await asyncio.sleep(5)

    with patch.object(jev_service, "_build_agent", return_value=HangingAgent()), pytest.raises(TimeoutError):
        asyncio.run(jev_service.decide("anything", Triage))
