"""Unit tests for the experimental exploration triage (Jev faked, no network)."""

from app.services import jev_service
from app.services.exploration.triage import TriageResult, parse_choice_answer, triage_description


def test_parse_choice_answer_live_shape():
    payload = {"type": "choice", "choice": "loot", "confidence": 0.97, "probabilities": {"loot": 0.97}}
    assert parse_choice_answer(payload) == ("loot", 0.97)


def test_parse_choice_answer_rejects_garbage():
    assert parse_choice_answer({}) == (None, 0.0)
    assert parse_choice_answer({"choice": 42}) == (None, 0.0)
    assert parse_choice_answer("loot") == (None, 0.0)
    assert parse_choice_answer({"choice": "loot", "confidence": "high"}) == (None, 0.0)
    assert parse_choice_answer({"choice": "loot", "confidence": 1.5}) == (None, 0.0)
    assert parse_choice_answer({"choice": "loot", "confidence": -0.2}) == (None, 0.0)


async def test_triage_returns_confident_category(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"event_kind": {"choice": "combat", "confidence": 0.95}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    result = await triage_description("A pack of feral ghouls ambushed your dweller!")
    assert isinstance(result, TriageResult)
    assert result.category == "combat"
    assert result.confidence == 0.95


async def test_triage_returns_empty_on_low_confidence(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"event_kind": {"choice": "rest", "confidence": 0.4}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    result = await triage_description("Something happened out there.")
    assert result.category is None


async def test_triage_returns_empty_on_jev_error(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise RuntimeError("Zen is down")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    result = await triage_description("A pack of feral ghouls ambushed your dweller!")
    assert result.category is None


async def test_triage_skips_blank_description(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise AssertionError("Jev must not be called for blank input")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    result = await triage_description("   ")
    assert result.category is None
