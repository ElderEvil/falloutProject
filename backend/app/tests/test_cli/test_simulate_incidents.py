"""Incident balance simulator CLI: determinism, responder-cap regression, and smoke."""

import random
from unittest.mock import patch

from app.cli import simulate_incidents as sim_cli
from app.cli.simulate_incidents import IncidentConfig, IncidentSimulator
from app.models.incident import IncidentType
from app.services.combat.incident_sim import DefenderProfile, IncidentOutcome, SimDefender
from app.utils.damage_reductions import DamageReductions


def _profile(label: str, power: float) -> DefenderProfile:
    return DefenderProfile(
        label=label,
        power=power,
        max_health=100,
        reductions_physical=DamageReductions(),
        reductions_fire=DamageReductions(),
    )


def test_simulator_is_deterministic_with_seed():
    cfg = IncidentConfig(spawn_chance_per_hour=0.8)
    sim = IncidentSimulator(cfg)
    first = sim.run(48, seed=42)
    second = sim.run(48, seed=42)
    assert first.total_incidents == second.total_incidents
    assert first.total_deaths == second.total_deaths
    assert first.incidents_resolved == second.incidents_resolved
    assert first.population_by_hour == second.population_by_hour


def test_simulator_differs_with_different_seed():
    cfg = IncidentConfig(spawn_chance_per_hour=0.8)
    sim = IncidentSimulator(cfg)
    first = sim.run(48, seed=1)
    second = sim.run(48, seed=2)
    assert (first.total_incidents, first.total_deaths) != (second.total_incidents, second.total_deaths)


def test_defenders_per_incident_caps_responders():
    """A bigger vault is not invincible: only defenders_per_incident responders fight."""
    cfg = IncidentConfig(spawn_chance_per_hour=1.0, defenders_per_incident=6)
    sim = IncidentSimulator(cfg)
    roster = [SimDefender(profile=_profile(f"d{i}", 10.0), health=100) for i in range(100)]
    vault = sim_cli.VaultState(population=100, adults=100, roster=roster)
    vault.incidents.append(sim_cli.Incident(start_time=0, incident_type=IncidentType.RAIDER_ATTACK, difficulty=2))

    with patch(
        "app.cli.simulate_incidents.resolve_incident",
        return_value=IncidentOutcome(resolved=True, failed=False, ticks=1, progress=1.0, damage_taken=0, deaths=0),
    ) as mock_resolve:
        sim._resolve_incidents(vault, [], random.Random(0))

    assert mock_resolve.call_count == 1
    responders = mock_resolve.call_args.args[2]
    assert len(responders) == 6


def test_cli_runs_and_prints_report():
    from typer.testing import CliRunner

    from app.cli.main import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["simulate-incidents", "--days", "1", "--runs", "2"])
    assert result.exit_code == 0, result.output
    assert "Incident Simulation" in result.output
    assert "Balance assessment" in result.output


def test_empty_real_roster_stays_empty():
    result = IncidentSimulator(IncidentConfig(spawn_chance_per_hour=0)).run(1, seed=7, base_roster=[])
    assert result.population_by_hour == [0]


def test_population_sweep_changes_actual_starting_population():
    results = sim_cli.run_parameter_sweep("starting_dwellers", IncidentConfig(spawn_chance_per_hour=0), 1, 1)
    assert [result["pop_curve"][0] for result in results] == sim_cli.SWEEP_RANGES["starting_dwellers"]
