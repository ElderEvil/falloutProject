"""Spike tests for the experimental Jev client (no network, no key needed)."""

import pytest

from app.services import jev_service


def test_is_configured_false_without_key(monkeypatch):
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    assert jev_service.is_configured() is False


def test_is_configured_true_with_fallback_key(monkeypatch):
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    assert jev_service.is_configured() is True


def test_resolve_model_prefers_paid_with_key(monkeypatch):
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "test-key")
    assert jev_service.resolve_model(None) == jev_service.DEFAULT_MODEL
    assert jev_service.resolve_model(jev_service.FREE_MODEL) == jev_service.FREE_MODEL


def test_resolve_model_degrades_to_free_without_key(monkeypatch):
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    assert jev_service.resolve_model(None) == jev_service.FREE_MODEL


async def test_decide_rejects_paid_model_without_key(monkeypatch):
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="needs OPENCODE_ZEN_API_KEY"):
        await jev_service.decide("state", {"q": jev_service.make_noul("Is it?")}, model=jev_service.DEFAULT_MODEL)


def test_question_builders_shape():
    assert jev_service.make_noul("Urgent?") == {"type": "noul", "instructions": "Urgent?"}
    choice = jev_service.make_choice("Route?", {"a": "Team A", "b": "Team B"})
    assert choice["type"] == "choice"
    assert set(choice["criteria"]) == {"a", "b"}
    score = jev_service.make_score("How bad?", ["Calm", "Angry"])
    assert score["type"] == "score"
    assert score["criteria"] == ["Calm", "Angry"]


async def test_decide_posts_expected_payload(monkeypatch):
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "test-key")
    seen = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"is_urgent": {"value": True, "confidence": 0.97}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            seen["url"] = url
            seen["auth"] = headers["Authorization"]
            seen["json"] = json
            return FakeResponse()

    monkeypatch.setattr(jev_service.httpx, "AsyncClient", FakeClient)
    result = await jev_service.decide(
        "Payments failed for three days.",
        {"is_urgent": jev_service.make_noul("Does this need urgent attention?")},
        model=jev_service.FREE_MODEL,
    )
    assert seen["url"] == jev_service.ZEN_SYSTEMONE_URL
    assert seen["auth"] == "Bearer test-key"
    assert seen["json"]["model"] == jev_service.FREE_MODEL
    assert result["is_urgent"]["value"] is True


async def test_decide_goes_keyless_free_without_key(monkeypatch):
    monkeypatch.delenv("OPENCODE_ZEN_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    seen = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"q": {"noul": 0.1}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            seen["auth"] = headers.get("Authorization")
            seen["json"] = json
            return FakeResponse()

    monkeypatch.setattr(jev_service.httpx, "AsyncClient", FakeClient)
    result = await jev_service.decide("state", {"q": jev_service.make_noul("Is it?")})
    assert seen["auth"] is None
    assert seen["json"]["model"] == jev_service.FREE_MODEL
    assert result["q"]["noul"] == 0.1


def test_noul_probability_shapes():
    assert jev_service.noul_probability({"value": True, "confidence": 0.97}) == 0.97
    assert jev_service.noul_probability({"type": "noul", "noul": 0.96}) == 0.96
    assert jev_service.noul_probability({}) == 0.0
    assert jev_service.noul_probability("yes") == 0.0
    assert jev_service.noul_probability({"noul": "high"}) == 0.0
