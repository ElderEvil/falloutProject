"""Unit tests for the experimental Jev room suggestion (Jev faked, no network)."""

from types import SimpleNamespace

from app.services import jev_service
from app.services.dweller_assignment_service import dweller_assignment_service


def make_dweller(**overrides):
    stats = {
        "strength": 8,
        "perception": 3,
        "endurance": 4,
        "charisma": 2,
        "intelligence": 3,
        "agility": 3,
        "luck": 3,
    }
    stats.update(overrides)
    return SimpleNamespace(first_name="Strong", level=5, **stats)


def make_room(name, ability=None):
    from app.core.enums import RoomTypeEnum

    return SimpleNamespace(name=name, ability=ability, category=RoomTypeEnum.PRODUCTION)


async def test_suggest_room_returns_confident_pick(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        assert "Strong" in state
        return {"answers": {"room": {"choice": "Power Plant", "confidence": 0.92}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    rooms = [make_room("Diner"), make_room("Power Plant")]
    picked = await dweller_assignment_service.suggest_room(make_dweller(), rooms)
    assert picked is not None
    assert picked.name == "Power Plant"


async def test_suggest_room_returns_none_on_low_confidence(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"room": {"choice": "Diner", "confidence": 0.4}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await dweller_assignment_service.suggest_room(make_dweller(), [make_room("Diner")]) is None


async def test_suggest_room_returns_none_on_unknown_choice(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"room": {"choice": "No Such Room", "confidence": 0.99}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await dweller_assignment_service.suggest_room(make_dweller(), [make_room("Diner")]) is None


async def test_suggest_room_returns_none_on_jev_error(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise RuntimeError("Zen is down")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    assert await dweller_assignment_service.suggest_room(make_dweller(), [make_room("Diner")]) is None


async def test_suggest_room_returns_none_without_candidates():
    assert await dweller_assignment_service.suggest_room(make_dweller(), []) is None
