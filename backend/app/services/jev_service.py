"""Experimental Jev (System One) client via OpenCode Zen — SPIKE, do not promote as-is.

Jev is TypeSafe AI's decision model, served through Zen at a dedicated
endpoint (NOT the chat/completions API)::

    POST https://opencode.ai/zen/v1/systemone
    Authorization: Bearer $OPENCODE_ZEN_API_KEY   # or $OPENCODE_API_KEY
    {"model": "jev-1.13", "state": "...", "questions": {...}}

Question types: ``noul`` (yes/no), ``choice`` (pick one of ``criteria``),
``score`` (rate against ``criteria`` scale). Multiple questions per request
are evaluated in parallel. Use ``jev-1.13-free`` for the free tier.
Pricing: $0.042 / 1M input tokens, output tokens free, 70-500 ms.

Auth: the paid model needs ``OPENCODE_ZEN_API_KEY`` (or ``OPENCODE_API_KEY``).
The free model works keyless - when no key is configured, ``decide`` degrades
to the free model without an Authorization header instead of failing.

Source: https://opencode.ai/docs/zen (Jev section), https://typesafe.ai
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

ZEN_SYSTEMONE_URL = "https://opencode.ai/zen/v1/systemone"
DEFAULT_MODEL = "jev-1.13"
FREE_MODEL = "jev-1.13-free"


def get_api_key() -> str | None:
    """Return the Zen key without ever logging it."""
    return os.getenv("OPENCODE_ZEN_API_KEY") or os.getenv("OPENCODE_API_KEY")


def is_configured() -> bool:
    """True when a Zen API key is present (paid models available)."""
    return bool(get_api_key())


def resolve_model(model: str | None) -> str:
    """Pick the model to call: explicit choice wins, otherwise paid with a key, free without."""
    if model is not None:
        return model
    return DEFAULT_MODEL if get_api_key() else FREE_MODEL


def make_noul(instructions: str) -> dict:
    """Build a yes/no question."""
    return {"type": "noul", "instructions": instructions}


def make_choice(instructions: str, criteria: dict) -> dict:
    """Build a multiple-choice question; criteria maps option -> description."""
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def make_score(instructions: str, criteria: list) -> dict:
    """Build a rubric-scored question; criteria is the ordered scale."""
    return {"type": "score", "instructions": instructions, "criteria": criteria}


def noul_probability(answer: dict) -> float:
    """Return P(yes) for a noul answer in either known Zen shape; 0.0 for anything else."""
    if not isinstance(answer, dict):
        return 0.0
    if "value" in answer:
        try:
            confidence = float(answer.get("confidence", 1.0))
        except (TypeError, ValueError):
            return 0.0
        return confidence if answer["value"] else 1.0 - confidence
    try:
        return float(answer.get("noul", 0.0))
    except (TypeError, ValueError):
        return 0.0


async def decide(
    state: str,
    questions: dict,
    model: str | None = None,
    timeout: float = 10.0,
) -> dict:
    """Evaluate ``state`` against ``questions`` via Zen; return raw Jev payload.

    Keyless callers degrade to the free model; an explicitly requested paid
    model without a key fails fast instead of silently downgrading.

    Raises:
        RuntimeError: Paid model requested without an API key, or Zen returned an HTTP error.
    """
    model = resolve_model(model)
    api_key = get_api_key()
    if api_key is None and model != FREE_MODEL:
        raise RuntimeError(f"Jev model {model} needs OPENCODE_ZEN_API_KEY (or OPENCODE_API_KEY).")
    headers = {"Content-Type": "application/json"}
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "state": state, "questions": questions}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(ZEN_SYSTEMONE_URL, headers=headers, json=payload)
        if response.status_code == 401:
            raise RuntimeError("Jev request rejected (401): check your Zen API key.")
        response.raise_for_status()
        return response.json()
