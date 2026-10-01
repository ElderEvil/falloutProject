"""CLI command group: jev-eval — measure Jev accuracy and calibrate thresholds.

Runs a labelled synthetic corpus through the real guardrail and triage on live
Jev, then reports per-category accuracy, a confusion summary, and a threshold
sweep so the confidence bars can be tuned on evidence rather than guesses.

Usage (from backend/):
    uv run fo-cli jev-eval run
    uv run fo-cli jev-eval run --json
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Annotated

import typer

from app.services.jev_eval_corpus import GUARDRAIL_CORPUS, TRIAGE_CORPUS
from app.services.jev_service import is_configured, jev_service

app = typer.Typer(
    name="jev-eval",
    help="Dev/QA: measure Jev guardrail/triage accuracy and calibrate thresholds",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


async def _guardrail_scores() -> list[tuple[str, bool, float]]:
    """(kind, should_block, max_offending_confidence) for each guardrail example."""
    from app.services.chat.guardrail import ChatGuardrail

    rows: list[tuple[str, bool, float]] = []
    for sample in GUARDRAIL_CORPUS:
        decision = await jev_service.decide(sample.text, ChatGuardrail)
        flagged = [
            decision.confidence_for(field)
            for field in ("jailbreak", "toxic")
            if getattr(decision.output, field)
        ]
        rows.append((sample.kind, sample.should_block, max(flagged, default=0.0)))
    return rows


async def _triage_scores() -> list[tuple[str, str, str, float]]:
    """(expected, predicted, correct, confidence) for each triage example."""
    from app.services.exploration.triage import EventTriage

    rows: list[tuple[str, str, str, float]] = []
    for sample in TRIAGE_CORPUS:
        decision = await jev_service.decide(sample.text, EventTriage)
        predicted = decision.output.event_kind
        confidence = decision.confidence_for("event_kind")
        rows.append((sample.category, predicted, "ok" if predicted == sample.category else "miss", confidence))
    return rows


@app.command()
def run(
    json_out: Annotated[bool, typer.Option("--json", help="Emit JSON")] = False,
) -> None:
    """Run the labelled corpus through guardrail + triage on live Jev."""
    asyncio.run(_run(json_out))


async def _run(json_out: bool) -> None:
    if not is_configured():
        typer.echo("Jev is not configured (set JEV_ENABLED and TYPESAFE_API_KEY).", err=True)
        raise typer.Exit(code=1)

    typer.echo("== Guardrail ==")
    guardrail_rows = await _guardrail_scores()
    _report_guardrail(guardrail_rows)

    typer.echo("\n== Triage ==")
    triage_rows = await _triage_scores()
    _report_triage(triage_rows)

    if json_out:
        import json

        typer.echo(json.dumps({"guardrail": guardrail_rows, "triage": triage_rows}, indent=2))


def _report_guardrail(rows: list[tuple[str, bool, float]]) -> None:
    by_kind: dict[str, Counter] = {}
    for kind, should_block, confidence in rows:
        blocked_at = {t: confidence >= t for t in (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9)}
        stats = by_kind.setdefault(kind, Counter(total=0, correct=0))
        stats["total"] += 1
        if blocked_at[0.75] == should_block:
            stats["correct"] += 1
        for threshold, blocked in blocked_at.items():
            if blocked == should_block:
                stats[f"t{threshold}"] += 1
    for kind, stats in sorted(by_kind.items()):
        total = stats["total"]
        typer.echo(f"  {kind:<10} correct@0.75={stats['correct']}/{total}")
    typer.echo("  threshold sweep (verdict correct at threshold):")
    for t in (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9):
        correct = sum(stats[f"t{t}"] for stats in by_kind.values())
        typer.echo(f"    >= {t}: {correct}/{len(rows)}")


def _report_triage(rows: list[tuple[str, str, str, float]]) -> None:
    correct = sum(1 for _, _, verdict, _ in rows if verdict == "ok")
    typer.echo(f"  accuracy@recorded: {correct}/{len(rows)}")
    confusion = Counter((expected, predicted) for expected, predicted, _, _ in rows)
    for (expected, predicted), count in sorted(confusion.items()):
        mark = "" if expected == predicted else "  <- miss"
        typer.echo(f"    {expected:<10} -> {predicted:<10} x{count}{mark}")
    sweep = {}
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9):
        accepted = sum(
            1 for expected, predicted, _, confidence in rows if confidence >= threshold and expected == predicted
        )
        dropped = sum(1 for _, _, _, confidence in rows if confidence < threshold)
        sweep[threshold] = (accepted, dropped)
    typer.echo("  threshold sweep (correct-and-accepted / dropped-as-unsure):")
    for threshold, (accepted, dropped) in sweep.items():
        typer.echo(f"    >= {threshold}: {accepted}/{len(rows)}   dropped {dropped}")


if __name__ == "__main__":
    app()
