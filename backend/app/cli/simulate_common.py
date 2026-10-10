"""Shared scaffolding for the Fallout Shelter balance simulators.

The Monte Carlo simulators (exploration, happiness, incidents) print the same
style of terminal report: a banner-wrapped title, stats rows, parameter-sweep
tables and hourly curves. This module holds that shared presentation plumbing,
the identical ``_Curves`` aggregation, the ``run_parameter_sweep`` control
flow and the ``simulate`` command body so each simulator stays focused on its
own model. No database or business logic lives here.
"""

from __future__ import annotations

import dataclasses
import random
import statistics
from collections.abc import Callable
from typing import Any, Self

import typer

TERMINAL_WIDTH = 72


def banner(text: str) -> str:
    pad = (TERMINAL_WIDTH - len(text) - 4) // 2
    return "=" * pad + f"  {text}  " + "=" * pad


def fmt_stats(st: dict[str, float]) -> str:
    return f"mean={st['mean']:.1f}  median={st['median']:.1f}  std={st['stdev']:.1f}  range=[{st['min']}, {st['max']}]"


def stats(values: list[int] | list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


@dataclasses.dataclass
class CurvesMixin:
    """Per-run hourly curve aggregation shared by each simulator's ``_Curves``."""

    @classmethod
    def zeroed(cls, hours: int) -> Self:
        return cls(**{k: [0.0] * hours for k in dataclasses.asdict(cls())})

    def divide(self, divisor: int) -> None:
        for k in dataclasses.asdict(self):
            arr = getattr(self, k)
            for i in range(len(arr)):
                arr[i] /= divisor


def run_parameter_sweep(
    param_name: str,
    baseline: Any,
    simulation_hours: int,
    runs: int,
    *,
    sweep_ranges: dict[str, list[Any]],
    run_monte_carlo: Callable[..., dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    values = sweep_ranges.get(param_name, [])
    if not values:
        print(f"Unknown parameter '{param_name}'. Available: {list(sweep_ranges.keys())}")
        return results

    for value in values:
        cfg = dataclasses.replace(baseline, **{param_name: value})
        result = run_monte_carlo(cfg, simulation_hours, runs)
        results.append(result)
    return results


def print_sweep_report(
    results: list[dict[str, Any]],
    param_name: str,
    *,
    header: str,
    render_row: Callable[[str, dict[str, Any]], str],
) -> None:
    print()
    print(banner(f"Parameter sweep: {param_name}"))
    print()
    print(header)
    print("-" * TERMINAL_WIDTH)

    for r in results:
        cfg = r["config"]
        value = getattr(cfg, param_name)
        vstr = f"{value:.2f}" if isinstance(value, float) else str(value)
        print(render_row(vstr, r))
    print()


def print_hourly_curves(batch: dict[str, Any], hours: int, *, deaths_key: str, incidents_key: str) -> None:
    if hours > 24:
        return
    print("Hourly curves (average per run):")
    print("  hour | POP | DEATHS | INCIDENTS | POWER | FOOD | WATER | HAPPY")
    print("  " + "-" * 65)
    for h in range(hours):
        p = batch["pop_curve"][h]
        d = batch[deaths_key][h]
        i = batch[incidents_key][h]
        pw = batch["power_curve"][h]
        f = batch["food_curve"][h]
        w = batch["water_curve"][h]
        hp = batch["happiness_curve"][h]
        print(f"  {h:4} | {p:3.0f} | {d:6.1f} | {i:9.1f} | {pw:5.0f} | {f:4.0f} | {w:5.0f} | {hp:5.1f}")
    print()


def run_simulate_command(
    *,
    hours: int,
    runs: int,
    seed: int | None,
    sweep: str | None,
    detailed: bool,
    sweep_ranges: dict[str, list[Any]],
    baseline: Any,
    run_monte_carlo: Callable[..., dict[str, Any]],
    run_parameter_sweep: Callable[..., list[dict[str, Any]]],
    print_report: Callable[..., None],
    print_sweep_report: Callable[..., None],
) -> None:
    if sweep:
        if sweep not in sweep_ranges:
            typer.echo(f"Unknown parameter '{sweep}'. Available: {list(sweep_ranges.keys())}", err=True)
            raise typer.Exit(code=1)
        results = run_parameter_sweep(sweep, baseline, hours, runs)
        for r in results:
            print_report(r, detailed=detailed)
        print_sweep_report(results, sweep)
    else:
        if seed is not None:
            random.seed(seed)
        result = run_monte_carlo(baseline, hours, runs)
        print_report(result, detailed=detailed)
