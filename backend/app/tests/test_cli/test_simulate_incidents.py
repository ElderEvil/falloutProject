"""Incident balance simulator CLI: determinism, responder-cap regression, and smoke."""

import random
from unittest.mock import patch

from typer.testing import CliRunner

from app.cli import simulate_incidents as sim_cli
from app.cli.main import cli
from app.cli.simulate_incidents import IncidentConfig, IncidentSimulator
from app.core.enums import HazardTeam
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


def test_regen_respects_radiation_ceiling():
    """Healing clamps to max(1, max_health - radiation), like the combat kernel."""
    cfg = IncidentConfig(heal_per_tick=5)
    sim = IncidentSimulator(cfg)
    defender = SimDefender(profile=_profile("rad", 10.0), health=30, radiation=70)
    vault = sim_cli.VaultState(population=1, adults=1, roster=[defender])
    sim._regen_defenders(vault)
    assert defender.health == 30


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
    result = CliRunner().invoke(cli, ["simulate-incidents", "--days", "1", "--runs", "2"])
    assert result.exit_code == 0, result.output
    assert "Incident Simulation" in result.output
    assert "Balance assessment" in result.output


def test_empty_real_roster_stays_empty():
    result = IncidentSimulator(IncidentConfig(spawn_chance_per_hour=0)).run(1, seed=7, base_roster=[])
    assert result.population_by_hour == [0]


def test_population_sweep_changes_actual_starting_population():
    results = sim_cli.run_parameter_sweep("starting_dwellers", IncidentConfig(spawn_chance_per_hour=0), 1, 1)
    assert [result["pop_curve"][0] for result in results] == sim_cli.SWEEP_RANGES["starting_dwellers"]


def test_matchup_is_deterministic_with_seed():
    first = sim_cli.run_matchup(IncidentConfig(), IncidentType.FIRE, 2, 50, seed=11)
    second = sim_cli.run_matchup(IncidentConfig(), IncidentType.FIRE, 2, 50, seed=11)
    assert [(o.resolved, o.ticks, o.damage_taken) for o in first["outcomes"]] == [
        (o.resolved, o.ticks, o.damage_taken) for o in second["outcomes"]
    ]


def test_matchup_fire_team_responds_stronger_than_unassigned_roster():
    plain = sim_cli.run_matchup(IncidentConfig(), IncidentType.FIRE, 4, 200, seed=3)
    team = sim_cli.run_matchup(
        IncidentConfig(hazard_team=HazardTeam.FIRE, team_size=3), IncidentType.FIRE, 4, 200, seed=3
    )
    assert sum(o.damage_taken for o in team["outcomes"]) < sum(o.damage_taken for o in plain["outcomes"])


def test_matchup_cli_prints_report():
    result = CliRunner().invoke(
        cli, ["simulate-incidents", "--matchup", "RADSCORPION_ATTACK:4", "--runs", "100", "--seed", "7"]
    )
    assert result.exit_code == 0, result.output
    assert "Matchup: RADSCORPION_ATTACK difficulty 4" in result.output


def test_matchup_cli_rejects_unknown_type():
    result = CliRunner().invoke(cli, ["simulate-incidents", "--matchup", "NOT_A_TYPE:2", "--runs", "1"])
    assert result.exit_code != 0


def test_matchup_zero_responders_reports_unopposed_instead_of_crashing():
    """defenders_per_incident=0 resolves every run as an unopposed (failed, bloodless) incident."""
    run = sim_cli.run_matchup(IncidentConfig(defenders_per_incident=0), IncidentType.RAIDER_ATTACK, 2, 10, seed=3)
    assert len(run["outcomes"]) == 10
    assert all(outcome.failed and not outcome.resolved for outcome in run["outcomes"])
    assert sum(outcome.damage_taken for outcome in run["outcomes"]) == 0
    assert sum(outcome.deaths for outcome in run["outcomes"]) == 0


def test_matchup_cli_rejects_vault_id_combination():
    """--matchup runs a synthetic roster, so combining it with --vault-id is a loud error."""
    result = CliRunner().invoke(
        cli,
        [
            "simulate-incidents",
            "--matchup",
            "FIRE:2",
            "--runs",
            "1",
            "--vault-id",
            "00000000-0000-0000-0000-000000000000",
        ],
    )
    assert result.exit_code == 2
    assert "--vault-id" in result.output


def test_simulate_cli_rejects_zero_runs():
    """--runs 0 would divide by zero in the report; fail fast with a clear error."""
    result = CliRunner().invoke(cli, ["simulate-incidents", "--runs", "0"])
    assert result.exit_code == 2
    assert "--runs" in result.output


def test_matchup_cli_accepts_team_size_and_outfit_count():
    result = CliRunner().invoke(
        cli,
        [
            "simulate-incidents",
            "--matchup",
            "FIRE:4",
            "--runs",
            "5",
            "--seed",
            "1",
            "--hazard-team",
            "fire",
            "--team-size",
            "0",
            "--outfit-count",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output


def _total_damage(run: dict) -> int:
    return sum(outcome.damage_taken for outcome in run["outcomes"])


def _total_ticks(run: dict) -> int:
    return sum(outcome.ticks for outcome in run["outcomes"])


def test_four_defender_conditions_isolate_team_place_from_matching_gear():
    """The seeded four-condition comparison the playtest protocol is built on.

    Same seed and roster size across runs, so the responder sample is identical
    and the only variable is the condition: plain, matching gear without a place,
    a place without gear, and the trained team (place + gear).
    """
    seed = 20261012

    def run(incident_type: IncidentType, **config_overrides) -> dict:
        return sim_cli.run_matchup(IncidentConfig(**config_overrides), incident_type, 4, 200, seed=seed)

    plain = run(IncidentType.FIRE)
    gear_only = run(IncidentType.FIRE, hazard_team=HazardTeam.FIRE, team_size=0, outfit_count=3)
    team_only = run(IncidentType.FIRE, hazard_team=HazardTeam.FIRE, team_size=3, outfit_count=0)
    team_gear = run(IncidentType.FIRE, hazard_team=HazardTeam.FIRE, team_size=3, outfit_count=3)

    assert all(outcome.resolved for run_ in (plain, gear_only, team_only, team_gear) for outcome in run_["outcomes"])
    assert _total_damage(gear_only) < _total_damage(plain)
    assert _total_damage(team_only) < _total_damage(plain)
    assert _total_damage(team_gear) < _total_damage(plain)
    assert _total_damage(team_gear) <= _total_damage(gear_only)
    assert _total_damage(team_gear) <= _total_damage(team_only)
    assert _total_ticks(team_gear) <= _total_ticks(plain)


def test_benched_team_and_mismatched_team_earn_no_matching_bonus():
    """A team with nobody active and a team facing the wrong hazard both get no bonus."""
    seed = 20261012

    plain_fire = sim_cli.run_matchup(IncidentConfig(), IncidentType.FIRE, 4, 200, seed=seed)
    bench_fire = sim_cli.run_matchup(
        IncidentConfig(hazard_team=HazardTeam.FIRE, team_size=0, outfit_count=0), IncidentType.FIRE, 4, 200, seed=seed
    )
    assert (_total_damage(bench_fire), _total_ticks(bench_fire)) == (
        _total_damage(plain_fire),
        _total_ticks(plain_fire),
    )

    # A fire team in fire suits gains nothing against a radiation hazard: identical to
    # the same gear worn with no place, so the team tag itself is proven inert here.
    rad_gear = sim_cli.run_matchup(
        IncidentConfig(hazard_team=HazardTeam.FIRE, team_size=0, outfit_count=3),
        IncidentType.RADSCORPION_ATTACK,
        4,
        200,
        seed=seed,
    )
    rad_mismatched = sim_cli.run_matchup(
        IncidentConfig(hazard_team=HazardTeam.FIRE, team_size=3, outfit_count=3),
        IncidentType.RADSCORPION_ATTACK,
        4,
        200,
        seed=seed,
    )
    assert [(o.damage_taken, o.radiation_gained, o.ticks) for o in rad_mismatched["outcomes"]] == [
        (o.damage_taken, o.radiation_gained, o.ticks) for o in rad_gear["outcomes"]
    ]
