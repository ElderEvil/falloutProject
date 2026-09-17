#!/usr/bin/env python3
"""Dweller chat scenario harness — a dev/analysis tool, NOT app code.

Why this exists
---------------
The dweller chat feature has no automated way to answer "does a child sound like a
child, does a ghoul sound like a ghoul, does a miserable dweller sound miserable?".
This harness drives LM Studio (OpenAI-compatible, strictly sequential — one request
at a time, no concurrency, so a local GPU is never overwhelmed) with the *real*
production instructions and records everything for offline analysis.

Fidelity to production
----------------------
The system prompt is assembled from the same sources the backend uses:
  * ``DEFAULT_PROMPTS["chat"]`` from ``app.services.prompt_service`` (the registry
    is the source of truth in prod; when the ``prompt`` table is empty, prod falls
    back to exactly this string — which is the current state of the dev DB).
  * ``build_chat_instructions(dweller)`` from ``app.agents.chat_prompts``.
Order matches PydanticAI: literal instructions first, dynamic ones second.

What it exercises
-----------------
* ``agent``    — the structured agent prompt (``build_chat_instructions``, no tools here).
* ``fallback`` — the plain prompt used when structured runs fail; the realistic path for a
  small local model. Both prompts now carry species, age register, mood and family.
* ``history+`` — ablation: replays prior turns. Answers "how much does the missing
  message history cost?".

Metrics are deliberately dependency-free heuristics (word counts, Flesch reading
ease, small affect lexicons, persona-keyword hits). They are comparative, not
authoritative — read them next to the raw transcripts.

Before/after runs: the pre-improvement baseline is kept at
``scenario_output/20260917T194436Z/``; re-run with the same probes and compare
``summary.json`` to measure the prompt change.

Usage (LM Studio must be running; run with the backend venv):
    cd backend && uv run python ../scripts/dweller_chat_scenarios.py
    cd backend && uv run python ../scripts/dweller_chat_scenarios.py --dry-run
    cd backend && uv run python ../scripts/dweller_chat_scenarios.py --model google/gemma-4-e4b
    cd backend && uv run python ../scripts/dweller_chat_scenarios.py --no-ablations

Outputs to ``scripts/scenario_output/<UTC timestamp>/``:
    transcript.json — every turn, raw text + metrics + usage + latency
    summary.json    — aggregates per (mode, persona)
    report.md       — human-readable tables for review
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.chat_prompts import build_chat_instructions  # noqa: E402
from app.core.enums import (  # noqa: E402
    AgeGroupEnum,
    GenderEnum,
    GhoulFeralnessEnum,
    RarityEnum,
    RaceEnum,
    SuperMutantMutationEnum,
)
from app.services.chat.agent_runner import build_dweller_prompt  # noqa: E402
from app.services.prompt_service import DEFAULT_PROMPTS  # noqa: E402

DEFAULT_MODEL = "google/gemma-4-e4b"
DEFAULT_BASE_URL = "http://localhost:1234/v1"

# --------------------------------------------------------------------------------------
# Probe set — the same questions go to every persona so voices are comparable.
# --------------------------------------------------------------------------------------

PROBES: list[str] = [
    "Morning. How are you holding up today?",
    "Tell me a bit about yourself — what's your story?",
    "What do you think about the world outside the vault?",
    "How's your family doing these days?",
]

STATE_OF_BEING_TYPE = GhoulFeralnessEnum | SuperMutantMutationEnum


class Obj:
    """Attribute bag that mimics the ORM/read-model object graph ``build_chat_instructions`` walks."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


@dataclass
class FamilyMember:
    name: str
    relation: str


@dataclass
class Persona:
    """A controlled dweller profile. Fixed values keep persona-to-persona comparisons clean."""

    key: str
    first_name: str
    last_name: str
    gender: GenderEnum
    age_group: AgeGroupEnum
    rarity: RarityEnum
    level: int
    happiness: int
    bio: str
    special: dict[str, int]
    health: int = 50
    max_health: int = 50
    radiation: int = 0
    stimpack: int = 2
    radaway: int = 1
    room_name: str = "Living Quarters"
    outfit_name: str = "Vault Suit"
    weapon_name: str | None = "10mm Pistol"
    vault_number: int = 101
    vault_happiness: int = 70
    race: RaceEnum = RaceEnum.HUMAN
    state_of_being: STATE_OF_BEING_TYPE | None = None
    apparent_age: int | None = None
    family: list[FamilyMember] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    is_adult: bool = True

    def to_dweller(self) -> Obj:
        """Build the object tree the production prompt builder expects."""
        return Obj(
            first_name=self.first_name,
            last_name=self.last_name,
            level=self.level,
            gender=self.gender,
            age_group=self.age_group,
            rarity=self.rarity,
            room=Obj(name=self.room_name),
            outfit=Obj(name=self.outfit_name),
            weapon=Obj(name=self.weapon_name) if self.weapon_name else None,
            health=self.health,
            max_health=self.max_health,
            radiation=self.radiation,
            stimpack=self.stimpack,
            radaway=self.radaway,
            happiness=self.happiness,
            # ``build_chat_instructions`` reads SPECIAL via SPECIALModel.__annotations__.
            **self.special,
            vault=Obj(
                number=self.vault_number,
                happiness=self.vault_happiness,
                power=20,
                power_max=30,
                food=25,
                food_max=30,
                water=18,
                water_max=30,
            ),
            bio=self.bio,
            visual_attributes={
                "race": self.race.value,
                **({"state_of_being": self.state_of_being.value} if self.state_of_being else {}),
            },
        )


def _special(str_: int, per: int, end: int, cha: int, intel: int, agi: int, luck: int) -> dict[str, int]:
    return {
        "strength": str_,
        "perception": per,
        "endurance": end,
        "charisma": cha,
        "intelligence": intel,
        "agility": agi,
        "luck": luck,
    }


def build_personas() -> dict[str, Persona]:
    """Seven controlled profiles covering the axes the feature must express."""
    personas = [
        Persona(
            key="adult_baseline",
            first_name="Marcus",
            last_name="Vane",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=12,
            happiness=78,
            bio=(
                "Born in Megaton. Before the vault, I ran a repair stall fixing water pumps and broken rifles. "
                "I keep my head down and my tools sharp."
            ),
            special=_special(5, 4, 4, 3, 5, 4, 3),
            room_name="Power Generator",
        ),
        Persona(
            key="child",
            first_name="Pip",
            last_name="Vance",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.CHILD,
            rarity=RarityEnum.COMMON,
            level=1,
            happiness=80,
            is_adult=False,
            bio=(
                "Born in Vault 101. I have never seen the sky. I like drawing pictures of the world my parents "
                "describe to me."
            ),
            special=_special(1, 2, 1, 2, 2, 2, 3),
            health=50,
            max_health=50,
            room_name="Living Quarters",
            weapon_name=None,
        ),
        Persona(
            key="elder",
            first_name="Ezekiel",
            last_name="Marsh",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ELDER,
            rarity=RarityEnum.COMMON,
            level=34,
            happiness=68,
            apparent_age=72,
            bio=(
                "Seventy-two years, most of them outdoors. I traded between settlements and buried people I liked. "
                "My knees are a weather report and my memory is the only map that still matters."
            ),
            special=_special(4, 5, 3, 5, 6, 2, 4),
            room_name="Water Treatment",
        ),
        Persona(
            key="ghoul",
            first_name="Nora",
            last_name="Kell",
            gender=GenderEnum.FEMALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=22,
            happiness=62,
            race=RaceEnum.GHOUL,
            state_of_being=GhoulFeralnessEnum.SANE,
            bio=(
                "Two hundred years and a face that remembers all of them. I was caught outside when the bombs fell "
                "and the radiation kept me alive instead of killing me. Smoothskins look away; I stopped minding."
            ),
            special=_special(4, 5, 6, 3, 5, 3, 4),
            room_name="Science Lab",
        ),
        Persona(
            key="super_mutant",
            first_name="Grok",
            last_name="",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.RARE,
            level=18,
            happiness=55,
            race=RaceEnum.SUPER_MUTANT,
            state_of_being=SuperMutantMutationEnum.AVERAGE,
            bio=(
                "Was small once. The FEV made me big. I remember less of before, which is fine, because now I am "
                "strong and the work is simple."
            ),
            special=_special(9, 3, 7, 2, 2, 3, 2),
            room_name="Power Generator",
        ),
        Persona(
            key="low_happiness",
            first_name="Clara",
            last_name="Boyd",
            gender=GenderEnum.FEMALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=9,
            happiness=12,
            bio=(
                "Born in Tenpenny Tower. I lost my sister to a raider ambush and have not found a reason since. "
                "The vault is loud and I am tired."
            ),
            special=_special(3, 4, 3, 4, 4, 3, 2),
            room_name="Diner",
        ),
        Persona(
            key="family",
            first_name="Dana",
            last_name="Reyes",
            gender=GenderEnum.FEMALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=14,
            happiness=71,
            bio=(
                "Born in the Hub. I came to the vault with my partner Ana and our daughter Tomas. I cook for two "
                "hundred people and I sleep well because of them."
            ),
            special=_special(4, 3, 5, 6, 4, 5, 3),
            room_name="Diner",
            family=[FamilyMember("Ana Reyes", "partner"), FamilyMember("Tomas Reyes", "child")],
            relationships=[{"name": "Ana Reyes", "relationship_type": "married", "affinity": 92}],
        ),
    ]
    return {persona.key: persona for persona in personas}


# --------------------------------------------------------------------------------------
# Prompt assembly
# --------------------------------------------------------------------------------------


def family_entries(persona: Persona) -> list[dict[str, str]]:
    """The {name, relation} shape ``load_family_members`` hands to the prompt builders."""
    return [{"name": member.name, "relation": member.relation} for member in persona.family]


def base_instructions(persona: Persona) -> str:
    """Registry prompt + dynamic dweller profile, in production order.

    This is the *structured agent* path (``build_chat_instructions``), which also
    carries tool instructions.
    """
    return f"{DEFAULT_PROMPTS['chat']}\n\n{build_chat_instructions(persona.to_dweller(), family_entries(persona))}"


def fallback_instructions(persona: Persona) -> str:
    """Registry prompt + the plain-text profile used when structured agent runs fail.

    ``run_fallback_chat_agent`` builds this from ``build_dweller_prompt`` after resolving
    family members; it has no tools and no JSON contract, which makes it the realistic
    path for a small local model that cannot satisfy the structured agent.
    """
    prompt = build_dweller_prompt(persona.to_dweller(), family=family_entries(persona))
    return f"{DEFAULT_PROMPTS['chat']}\n\n{prompt.strip()}"


MODE_SPECS: dict[str, dict[str, Any]] = {
    "agent": {
        "label": "Structured agent prompt (build_chat_instructions; tools unavailable here)",
        "base": "agent",
        "extras": [],
    },
    "fallback": {
        "label": "Plain fallback prompt (build_dweller_prompt; the realistic local-model path)",
        "base": "fallback",
        "extras": [],
    },
    "history+": {
        "label": "Ablation on fallback: + conversation history",
        "base": "fallback",
        "extras": [],
        "history": True,
    },
}

MODE_PERSONAS: dict[str, list[str]] = {
    "agent": ["adult_baseline", "child", "elder", "ghoul", "super_mutant", "low_happiness", "family"],
    "fallback": ["adult_baseline", "child", "elder", "ghoul", "super_mutant", "low_happiness", "family"],
    "history+": ["family"],
}


def system_prompt_for(persona: Persona, mode: str) -> str:
    spec = MODE_SPECS[mode]
    return fallback_instructions(persona) if spec["base"] == "fallback" else base_instructions(persona)


# --------------------------------------------------------------------------------------
# Metrics — intentionally dependency-free heuristics
# --------------------------------------------------------------------------------------

POSITIVE_WORDS = {
    "good", "great", "glad", "happy", "hope", "hopeful", "joy", "love", "loved", "lucky", "nice", "peace",
    "proud", "safe", "smile", "smiling", "strong", "thankful", "warm", "welcome", "wonderful", "fine",
    "content", "cheerful", "bright", "better", "best", "enjoy", "fun", "kind", "gentle", "grateful",
}
NEGATIVE_WORDS = {
    "afraid", "alone", "angry", "anxious", "bad", "bitter", "broken", "cold", "cry", "dark", "dead", "death",
    "empty", "exhausted", "fear", "grief", "hate", "hurt", "lonely", "lost", "miserable", "miss", "numb",
    "pain", "regret", "sad", "scared", "sick", "sorrow", "tired", "trouble", "weary", "worse", "worst",
    "worthless", "wounded", "gloomy", "hopeless", "aching", "heavy", "quiet", "cold",
}
RACE_TERMS = {
    "ghoul": ["ghoul", "ghoulish", "smoothskin", "smoothskin", "feral", "radiation", "necrotic"],
    "super_mutant": ["mutant", "super mutant", "fev", "big", "green", "behemoth", "strong"],
}
FAMILY_TERMS = ["family", "son", "daughter", "wife", "husband", "partner", "child", "kid", "mother", "father"]
CHILD_COMPLEX_WORDS = {
    "radiation", "protocol", "reevaluate", "consequently", "nevertheless", "furthermore", "approximately",
    "sufficiently", "unfortunately", "responsibility", "assignment", "objective", "strategy", "consequence",
    "maintenance", "infrastructure", "schedule", "efficiency", "obligation", "circumstances",
}

_WORD_RE = re.compile(r"[A-Za-z']+")
_SENTENCE_RE = re.compile(r"[.!?]+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+")


def count_syllables(word: str) -> int:
    return max(1, len(_VOWEL_GROUP_RE.findall(word.lower())))


def flesch_reading_ease(text: str) -> float:
    """Higher = simpler. 90+ is very easy (child-ish), <50 is difficult."""
    words = _WORD_RE.findall(text)
    sentences = max(1, len(_SENTENCE_RE.findall(text)))
    if not words:
        return 0.0
    syllables = sum(count_syllables(word) for word in words)
    return round(206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words)), 1)


def compute_metrics(text: str, persona: Persona) -> dict[str, Any]:
    words = [word.lower() for word in _WORD_RE.findall(text)]
    sentences = max(1, len(_SENTENCE_RE.findall(text)))
    family_names = [member.name.split()[0].lower() for member in persona.family]
    return {
        "word_count": len(words),
        "sentence_count": sentences,
        "avg_words_per_sentence": round(len(words) / sentences, 1),
        "flesch_reading_ease": flesch_reading_ease(text),
        "unique_word_ratio": round(len(set(words)) / len(words), 3) if words else 0.0,
        "positive_hits": sorted({word for word in words if word in POSITIVE_WORDS}),
        "negative_hits": sorted({word for word in words if word in NEGATIVE_WORDS}),
        "affect_balance": sum(1 for word in words if word in POSITIVE_WORDS)
        - sum(1 for word in words if word in NEGATIVE_WORDS),
        "race_hits": sorted({term for term in RACE_TERMS.get(persona.race.value, []) if term in text.lower()}),
        "family_terms": sorted({term for term in FAMILY_TERMS if term in words}),
        "family_names_used": sorted({name for name in family_names if name in words}),
        "complex_child_words": sorted({word for word in words if word in CHILD_COMPLEX_WORDS}),
    }


# --------------------------------------------------------------------------------------
# LM Studio client — strictly sequential
# --------------------------------------------------------------------------------------


@dataclass
class Completion:
    text: str
    reasoning: str
    prompt_tokens: int | None
    completion_tokens: int | None
    finish_reason: str | None
    latency_ms: int


def complete(
    *, base_url: str, model: str, messages: list[dict[str, str]], temperature: float, max_tokens: int, timeout: int
) -> Completion:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                body = json.loads(response.read().decode("utf-8"))
            choice = body["choices"][0]
            usage = body.get("usage") or {}
            message = choice["message"]
            return Completion(
                text=(message.get("content") or "").strip(),
                reasoning=(message.get("reasoning_content") or "").strip(),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                finish_reason=choice.get("finish_reason"),
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LM Studio request failed after retries: {last_error}")


# --------------------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------------------


def run_mode(
    *,
    mode: str,
    persona_keys: list[str],
    personas: dict[str, Persona],
    base_url: str,
    model: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    probes: list[str],
) -> list[dict[str, Any]]:
    """Run one conversation per persona, one HTTP request at a time. Never parallel."""
    results: list[dict[str, Any]] = []
    use_history = bool(MODE_SPECS[mode].get("history"))
    for persona_key in persona_keys:
        persona = personas[persona_key]
        system_prompt = system_prompt_for(persona, mode)
        history: list[dict[str, str]] = []
        print(f"\n  ── {mode} / {persona_key} ({persona.first_name}) ──")
        for turn, probe in enumerate(probes, start=1):
            messages = [{"role": "system", "content": system_prompt}]
            if use_history:
                messages.extend(history)
            messages.append({"role": "user", "content": probe})

            completion = complete(
                base_url=base_url,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            if use_history:
                history.append({"role": "user", "content": probe})
                history.append({"role": "assistant", "content": completion.text})

            metrics = compute_metrics(completion.text, persona)
            results.append(
                {
                    "mode": mode,
                    "persona": persona_key,
                    "turn": turn,
                    "user": probe,
                    "assistant": completion.text,
                    "reasoning": completion.reasoning,
                    "latency_ms": completion.latency_ms,
                    "prompt_tokens": completion.prompt_tokens,
                    "completion_tokens": completion.completion_tokens,
                    "reasoning_chars": len(completion.reasoning),
                    "finish_reason": completion.finish_reason,
                    "truncated": completion.finish_reason == "length",
                    "metrics": metrics,
                }
            )
            preview = completion.text.replace("\n", " ")[:110]
            flag = " ⚠TRUNCATED" if completion.finish_reason == "length" else ""
            print(
                f"    T{turn} [{metrics['word_count']}w flesch={metrics['flesch_reading_ease']} "
                f"reason={len(completion.reasoning)}c]{flag} {preview}..."
            )
    return results


# --------------------------------------------------------------------------------------
# Aggregation + report
# --------------------------------------------------------------------------------------


def aggregate(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in results:
        groups.setdefault((row["mode"], row["persona"]), []).append(row)

    summary: list[dict[str, Any]] = []
    for (mode, persona), rows in groups.items():
        metrics = [row["metrics"] for row in rows]
        latencies = [row["latency_ms"] for row in rows]

        def avg(key: str) -> float:
            values = [metric[key] for metric in metrics if isinstance(metric.get(key), (int, float))]
            return round(statistics.mean(values), 2) if values else 0.0

        summary.append(
            {
                "mode": mode,
                "persona": persona,
                "turns": len(rows),
                "avg_word_count": avg("word_count"),
                "avg_words_per_sentence": avg("avg_words_per_sentence"),
                "avg_flesch": avg("flesch_reading_ease"),
                "unique_word_ratio": avg("unique_word_ratio"),
                "affect_balance": avg("affect_balance"),
                "negative_hits": sum(len(metric["negative_hits"]) for metric in metrics),
                "positive_hits": sum(len(metric["positive_hits"]) for metric in metrics),
                "race_hits": sum(len(metric["race_hits"]) for metric in metrics),
                "family_terms": sum(len(metric["family_terms"]) for metric in metrics),
                "family_names_used": sum(len(metric["family_names_used"]) for metric in metrics),
                "complex_child_words": sum(len(metric["complex_child_words"]) for metric in metrics),
                "avg_latency_ms": int(statistics.mean(latencies)) if latencies else 0,
                "errors_or_empty": sum(1 for row in rows if not row["assistant"].strip()),
                "truncated": sum(1 for row in rows if row.get("truncated")),
                "avg_reasoning_chars": int(statistics.mean([row["reasoning_chars"] for row in rows])),
            }
        )
    return sorted(summary, key=lambda row: (row["mode"], row["persona"]))


def write_report(out_dir: Path, results: list[dict[str, Any]], summary: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Dweller chat scenario report")
    lines.append("")
    lines.append(f"- Model: `{meta['model']}` @ `{meta['base_url']}`")
    lines.append(f"- Temperature: {meta['temperature']}, max_tokens: {meta['max_tokens']}")
    lines.append(f"- Requests: {meta['requests']} (sequential, one at a time)")
    lines.append(f"- Generated: {meta['generated_at']}")
    lines.append("")
    lines.append("## Per-mode summary")
    lines.append("")
    header = (
        "| mode | persona | turns | words | w/sent | flesch | affect | neg | pos | race | fam-terms | "
        "fam-names | complex-kid | reason-chars | trunc | ms |"
    )
    lines.append(header)
    lines.append("|" + "---|" * 16)
    for row in summary:
        lines.append(
            f"| {row['mode']} | {row['persona']} | {row['turns']} | {row['avg_word_count']} | "
            f"{row['avg_words_per_sentence']} | {row['avg_flesch']} | {row['affect_balance']} | "
            f"{row['negative_hits']} | {row['positive_hits']} | {row['race_hits']} | {row['family_terms']} | "
            f"{row['family_names_used']} | {row['complex_child_words']} | {row['avg_reasoning_chars']} | "
            f"{row['truncated']} | {row['avg_latency_ms']} |"
        )
    lines.append("")
    lines.append("## Transcripts")
    for row in results:
        lines.append("")
        lines.append(f"### [{row['mode']}] {row['persona']} — turn {row['turn']}")
        lines.append("")
        lines.append(f"**User:** {row['user']}")
        lines.append("")
        lines.append(f"**Dweller:** {row['assistant'] or '_(empty)_'}")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-tokens", type=int, default=1200, help="gemma-4-e4b is a reasoning model: <800 truncates the answer.")
    parser.add_argument("--timeout", type=int, default=240, help="Seconds; first call may load the model.")
    parser.add_argument("--turns", type=int, default=len(PROBES), help="Number of probes per persona.")
    parser.add_argument("--only", nargs="*", default=None, help="Restrict to these persona keys.")
    parser.add_argument("--modes", nargs="*", default=None, help="Restrict to these modes.")
    parser.add_argument("--no-ablations", action="store_true", help="Run only agent and fallback (skip the history ablation).")
    parser.add_argument("--dry-run", action="store_true", help="Print assembled prompts and exit.")
    parser.add_argument("--out-dir", default=None, help="Override the output directory.")
    args = parser.parse_args()

    personas = build_personas()
    probes = PROBES[: args.turns]

    if args.dry_run:
        for key in args.only or ["child", "ghoul", "family"]:
            print(f"\n{'=' * 90}\n{key}\n{'=' * 90}")
            print("--- agent base ---\n" + base_instructions(personas[key]))
            print("\n--- fallback base ---\n" + fallback_instructions(personas[key]))
        return 0

    modes = args.modes or list(MODE_SPECS)
    if args.no_ablations:
        modes = ["agent", "fallback"]

    requests = 0
    results: list[dict[str, Any]] = []
    started_at = datetime.now(timezone.utc)

    for mode in modes:
        keys = MODE_PERSONAS[mode]
        if args.only:
            keys = [key for key in keys if key in args.only]
        if not keys:
            continue
        print(f"\n=== mode: {mode} — {MODE_SPECS[mode]['label']} ===")
        results.extend(
            run_mode(
                mode=mode,
                persona_keys=keys,
                personas=personas,
                base_url=args.base_url,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                probes=probes,
            )
        )
        requests = len(results)

    summary = aggregate(results)
    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / "scripts" / "scenario_output" / started_at.strftime(
        "%Y%m%dT%H%M%SZ"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "model": args.model,
        "base_url": args.base_url,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "generated_at": started_at.isoformat(),
        "requests": requests,
        "probes": probes,
        "modes": modes,
    }
    (out_dir / "transcript.json").write_text(
        json.dumps({"meta": meta, "turns": results}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(out_dir, results, summary, meta)
    print(f"\nWrote {requests} turns to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
