"""Unit tests for experimental Jev quest-text validation (Jev faked, no network)."""

import pytest

from app.services import jev_service
from app.services.progression.quests.service import quest_service
from app.utils.exceptions import ValidationException


async def test_validate_quest_text_accepts_good_text(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        assert "Title:" in state
        return {"answers": {"broken": {"noul": 0.03}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    await quest_service.validate_quest_text(
        "Clear the Raider Camp",
        "Drive raiders from the northern pass.",
        "Scouts report raiders massing near the northern pass. Take two dwellers and clear them out.",
    )


async def test_validate_quest_text_rejects_broken_text(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        return {"answers": {"broken": {"value": True, "confidence": 0.94}}}

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    with pytest.raises(ValidationException, match="quality review"):
        await quest_service.validate_quest_text("asdf", "TODO write this", "lorem ipsum dolor sit amet")


async def test_validate_quest_text_passes_through_jev_errors(monkeypatch):
    async def fake_decide(state, questions, model=None, timeout=10.0):
        raise RuntimeError("Zen is down")

    monkeypatch.setattr(jev_service, "decide", fake_decide)
    with pytest.raises(RuntimeError, match="Zen is down"):
        await quest_service.validate_quest_text("Title", "Short", "Long")
