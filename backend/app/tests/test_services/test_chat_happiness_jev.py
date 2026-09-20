"""Unit tests for the experimental Jev distress signal (Jev faked, no network)."""

from app.services import jev_service
from app.services.chat_happiness_service import distress_adjustment


async def test_distress_high_scores_minus_two(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"distress": {"score": 0.95, "confidence": 0.9}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await distress_adjustment("Everyone is dying and there is no hope left.") == -2


async def test_distress_medium_scores_minus_one(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"distress": {"score": 0.6, "confidence": 0.85}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await distress_adjustment("Things have been rough lately.") == -1


async def test_distress_calm_scores_zero(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"distress": {"score": 0.1, "confidence": 0.95}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await distress_adjustment("What a wonderful day in the vault!") == 0


async def test_distress_low_confidence_scores_zero(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"distress": {"score": 0.99, "confidence": 0.3}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await distress_adjustment("Hmm.") == 0


async def test_distress_fails_open_on_jev_error(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise RuntimeError("Zen is down")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await distress_adjustment("Everyone is dying!") == 0


async def test_distress_skips_blank_input(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise AssertionError("Jev must not be called for blank input")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await distress_adjustment("   ") == 0
