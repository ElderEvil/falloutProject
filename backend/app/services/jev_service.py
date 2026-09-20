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
    """True when a Zen API key is present."""
    return bool(get_api_key())


def make_noul(instructions: str) -> dict:
    """Build a yes/no question."""
    return {"type": "noul", "instructions": instructions}


def make_choice(instructions: str, criteria: dict) -> dict:
    """Build a multiple-choice question; criteria maps option -> description."""
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def make_score(instructions: str, criteria: list) -> dict:
    """Build a rubric-scored question; criteria is the ordered scale."""
    return {"type": "score", "instructions": instructions, "criteria": criteria}


async def decide(
    state: str,
    questions: dict,
    model: str | None = None,
    timeout: float = 10.0,
) -> dict:
    """Evaluate ``state`` against ``questions`` via Zen; return raw Jev payload.

    Raises:
        RuntimeError: No API key configured, or Zen returned an HTTP error.
    """
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Jev not configured: set OPENCODE_ZEN_API_KEY (or OPENCODE_API_KEY).")
    payload = {"model": model or DEFAULT_MODEL, "state": state, "questions": questions}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            ZEN_SYSTEMONE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        if response.status_code == 401:
            raise RuntimeError("Jev request rejected (401): check your Zen API key.")
        response.raise_for_status()
        return response.json()
