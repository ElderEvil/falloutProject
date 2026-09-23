"""Unit tests for experimental player-text moderation (Jev faked, no network)."""

import pytest

from app.services import jev_service
from app.services.content_moderation_service import moderate_player_text
from app.utils.exceptions import ValidationException


async def test_moderation_accepts_clean_name(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"toxicity": {"score": 0.02, "confidence": 0.97}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    await moderate_player_text("Sarah", field="name")


async def test_moderation_rejects_hateful_name(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"toxicity": {"score": 0.95, "confidence": 0.9}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    with pytest.raises(ValidationException, match="automated moderation"):
        await moderate_player_text("I hate all mutants, death to them", field="name")


async def test_moderation_ignores_low_confidence(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"toxicity": {"score": 0.9, "confidence": 0.4}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    await moderate_player_text("Questionable", field="name")


async def test_moderation_fails_open_on_jev_error(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise RuntimeError("Zen is down")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    await moderate_player_text("Anything goes when Zen is down", field="name")


async def test_moderation_skips_blank_text(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise AssertionError("Jev must not be called for blank input")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    await moderate_player_text("   ", field="name")
