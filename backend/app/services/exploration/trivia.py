"""Trivia room state: pinned questions, raider selection, and stable option order."""

import hashlib
import random

from app.models.exploration import ExpeditionRun
from app.schemas.expedition import SiteRoom, TriviaOption, TriviaQuestion, TriviaRaider
from app.services import catalog_service as data_loader


def question_weight(difficulty: int, target_difficulty: int) -> float:
    """Weight a question by how close its difficulty is to the site's level band."""
    return max(0.1, 1.0 - 0.35 * abs(difficulty - target_difficulty))


def pick_trivia_questions(rooms: list[SiteRoom], *, target_difficulty: int) -> dict[str, list[str]]:
    """Pin distinct question ids per trivia room at entry so a reconnect cannot reroll them."""
    pinned: dict[str, list[str]] = {}
    for room in rooms:
        if room.node.kind != "trivia":
            continue
        count = min(room.node.trivia_question_count, len(room.node.trivia_questions))
        pool = list(room.node.trivia_questions)
        chosen: list[str] = []
        while pool and len(chosen) < count:
            weights = [question_weight(question.difficulty, target_difficulty) for question in pool]
            question = random.choices(pool, weights=weights, k=1)[0]
            chosen.append(question.id)
            pool.remove(question)
        pinned[room.id] = chosen
    return pinned


def pick_trivia_raiders(rooms: list[SiteRoom]) -> dict[str, str]:
    """Pin one shared raider persona per trivia room at entry, alongside its questions."""
    raiders = data_loader.load_trivia_raiders()
    return {room.id: random.choice(raiders).id for room in rooms if room.node.kind == "trivia"}


def _pinned_ids(room: SiteRoom, run: ExpeditionRun) -> list[str]:
    pinned = run.flags.get("trivia_questions", {}).get(room.id)
    if pinned is None:
        return []
    return [pinned] if isinstance(pinned, str) else list(pinned)


def trivia_answered(room: SiteRoom, run: ExpeditionRun) -> int:
    """How many of the room's pinned questions have already been answered correctly."""
    return int(run.flags.get("trivia_answered", {}).get(room.id, 0))


def trivia_question_total(room: SiteRoom, run: ExpeditionRun) -> int:
    """Number of questions pinned for this room."""
    return len(_pinned_ids(room, run))


def trivia_question(room: SiteRoom, run: ExpeditionRun) -> TriviaQuestion | None:
    """The next unanswered question persisted for this room, if any."""
    ids = _pinned_ids(room, run)
    answered = trivia_answered(room, run)
    if not ids or answered >= len(ids):
        return None
    question_id = ids[answered]
    return next((question for question in room.node.trivia_questions if question.id == question_id), None)


def trivia_raider(room: SiteRoom, run: ExpeditionRun) -> TriviaRaider | None:
    """The shared raider persona persisted for this room, if any."""
    raider_id = run.flags.get("trivia_raiders", {}).get(room.id)
    return next((raider for raider in data_loader.load_trivia_raiders() if raider.id == raider_id), None)


def ordered_options(run: ExpeditionRun, question: TriviaQuestion) -> list[TriviaOption]:
    """Deterministic per-run option order, so the authored first slot is not the answer."""
    seed = f"{run.id}:{question.id}"

    def key(option: TriviaOption) -> bytes:
        return hashlib.sha256(f"{seed}:{option.id}".encode()).digest()

    return sorted(question.options, key=key)
