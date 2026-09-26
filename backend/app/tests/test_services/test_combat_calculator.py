"""Tests for the shared enemy-by-difficulty selector."""

from app.services.exploration import combat_calculator as combat_module
from app.services.exploration import data_loader
from app.services.exploration.combat_calculator import combat_calculator


def test_select_enemy_by_difficulty_prefers_exact():
    difficulties = {enemy["difficulty"] for enemy in data_loader.load_enemies()}
    exact = max(difficulties)
    assert combat_calculator.select_enemy_by_difficulty(exact).difficulty == exact


def test_select_enemy_by_difficulty_falls_back_to_nearest_below():
    difficulties = {enemy["difficulty"] for enemy in data_loader.load_enemies()}
    lowest = min(difficulties)
    assert combat_calculator.select_enemy_by_difficulty(lowest - 1).difficulty == lowest


def test_select_enemy_by_difficulty_empty_catalog(monkeypatch):
    monkeypatch.setattr(combat_module.data_loader, "load_enemies", list)
    enemy = combat_calculator.select_enemy_by_difficulty(3)
    assert enemy.name == "Wasteland Creature"
