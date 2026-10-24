"""Incident math helpers used by the per-attack journal."""

from app.services.combat.incident_math import split_proportional


def test_split_proportional_attributes_the_whole_total():
    assert split_proportional(20, [1, 1]) == [10, 10]


def test_split_proportional_gives_remainders_to_the_largest_fractions():
    assert split_proportional(10, [1, 2]) == [3, 7]
    assert split_proportional(1, [1, 1, 1]) == [1, 0, 0]


def test_split_proportional_handles_zero_total_and_weights():
    assert split_proportional(0, [1, 2]) == [0, 0]
    assert split_proportional(5, [0, 0]) == [0, 0]
