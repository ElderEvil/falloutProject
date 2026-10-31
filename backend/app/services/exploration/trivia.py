"""Trivia room state: pinned question and raider selection plus lookup."""

import random

from app.models.exploration import ExpeditionRun
from app.schemas.expedition import SiteRoom, TriviaQuestion, TriviaRaider
from app.services import catalog_service as data_loader


def pick_trivia_questions(rooms: list[SiteRoom]) -> dict[str, str]:
    """Pin one question id per trivia room at entry so a reconnect cannot reroll it."""
    return {room.id: random.choice(room.node.trivia_questions).id for room in rooms if room.node.kind == "trivia"}


def pick_trivia_raiders(rooms: list[SiteRoom]) -> dict[str, str]:
    """Pin one shared raider persona per trivia room at entry, alongside its question."""
    raiders = data_loader.load_trivia_raiders()
    return {room.id: random.choice(raiders).id for room in rooms if room.node.kind == "trivia"}


def trivia_question(room: SiteRoom, run: ExpeditionRun) -> TriviaQuestion | None:
    """The question persisted for this room at entry, if any."""
    question_id = run.flags.get("trivia_questions", {}).get(room.id)
    return next((question for question in room.node.trivia_questions if question.id == question_id), None)


def trivia_raider(room: SiteRoom, run: ExpeditionRun) -> TriviaRaider | None:
    """The shared raider persona persisted for this room at entry, if any."""
    raider_id = run.flags.get("trivia_raiders", {}).get(room.id)
    return next((raider for raider in data_loader.load_trivia_raiders() if raider.id == raider_id), None)
