from datetime import date, datetime, timedelta

import pytest

from app.utils.broadcast_script import build_daily_script

COMMON = {
    "population": 10,
    "population_max": 20,
    "caps": 1000,
    "happiness": 70,
    "power": (50, 100),
    "food": (50, 100),
    "water": (50, 100),
    "recent_notifications": [],
    "vault_number": 1,
}


def _data(**overrides) -> dict:
    return {**COMMON, **overrides}


def _script(**overrides) -> str:
    return build_daily_script(**_data(**overrides))[1]


def _n(kind: str, message: str = "", **extra: object) -> dict:
    return {"notification_type": kind, "message": message, **extra}


def _baseline(**overrides) -> dict:
    return (
        _data(population=25, population_max=50, caps=5000, happiness=72, vault_number=13)
        | {"power": (80, 100), "food": (200, 300), "water": (150, 200)}
        | overrides
    )


def _variety(**overrides) -> dict:
    base = _data(population=23, population_max=46, caps=1852, happiness=87, vault_number=666)
    return (
        base
        | {
            "power": (300, 300),
            "food": (300, 300),
            "water": (300, 300),
            "gender_counts": [("male", 13), ("female", 10)],
        }
        | overrides
    )


def test_baseline_script_shape() -> None:
    title, script = build_daily_script(**_baseline(recent_notifications=[]), _now=datetime(2026, 6, 15, 12, 0))
    assert 100 <= len(script.split()) <= 220, f"Script word count {len(script.split())} outside expected range"
    assert "June 15, 2026" in title


def test_every_day_of_2026_stays_in_bounds_and_deterministic() -> None:
    # Regression: on 2026-11-19 the phrase pools rendered only 95 words (soft ceiling, no floor).
    day = date(2026, 1, 1)
    while day.year == 2026:
        now = datetime(day.year, day.month, day.day, 12, 0)
        for vault in (13, 42, 101):
            for seed in (None, f"sweep-vault-{vault}"):
                data = _baseline(vault_number=vault) | ({"variant_seed": seed} if seed else {})
                label = f"{day.isoformat()} vault={vault} variant_seed={seed!r}"
                title, script = build_daily_script(**data, _now=now)
                words = len(script.split())
                assert 100 <= words <= 220, f"{label}: word count {words} outside 100-220"
                assert (title, script) == build_daily_script(**data, _now=now), (
                    f"{label}: repeated render is not byte-identical"
                )
        day += timedelta(days=1)


def test_gender_split_from_counts() -> None:
    script = _script(happiness=60, gender_counts=[("male", 2), ("female", 1)], vault_number=7)
    assert "male" in script.lower()
    assert "female" in script.lower()


def test_resource_percentages() -> None:
    script = _script(
        **_data(population=5, population_max=10, caps=500, happiness=80, vault_number=3)
        | {"power": (10, 20), "food": (0, 50), "water": (50, 50)}
    )
    assert "50%" in script
    assert "0%" in script
    assert "100%" in script
    # Percentages only - the raw "current of maximum" numbers are noise.
    assert "of 50" not in script
    assert "of 20" not in script


@pytest.mark.parametrize(
    "notification",
    [_n("dweller_level_up", name="Max"), _n("level_up", "A dweller reached level 6.")],
)
def test_level_up_notification_keeps_level_wording(notification: dict) -> None:
    assert "level" in _script(recent_notifications=[notification]).lower()


def test_level_ups_use_each_dwellers_name_once() -> None:
    script = _script(
        recent_notifications=[
            _n("level_up", "Alice reached level 6!", title="Alice Leveled Up!"),
            _n("level_up", "Bob reached level 7!", title="Bob Leveled Up!"),
        ]
    )
    assert ("Alice" in script, "Bob" in script, script.count("Alice"), script.count("Bob")) == (True, True, 1, 1)


def test_vault_prefix_stripped_from_headlines() -> None:
    script = _script(
        vault_number=666,
        recent_notifications=[
            _n("level_up", "[Vault 666] Alice reached level 6!", title="[Vault 666] Alice Leveled Up!"),
            _n(
                "dweller_training_complete",
                "[Vault 666] Bob finished training Strength!",
                dweller_name="[Vault 666] Bob",
            ),
        ],
    )
    assert "[Vault" not in script
    assert "Alice" in script
    assert "Bob" in script


def test_active_combat_alert_is_not_a_headline() -> None:
    script = _script(
        vault_number=666,
        recent_notifications=[
            _n("combat_started", "[Vault 666] 🐀 Mole Rat Attack in Power Generator! Send dwellers to defend."),
            _n("combat_victory", "[Vault 666] Your dwellers defeated the attackers, recovered 52 caps."),
        ],
    )
    assert "defeated the attackers" in script
    assert "Send dwellers to defend" not in script


def test_multiple_notifications_batched() -> None:
    script = _script(
        recent_notifications=[
            {"message": "A radroach was spotted in the kitchen."},
            {"message": "A dweller found some caps."},
            {"message": "Power generator needs repair."},
            {"message": "Extra notification should be truncated."},
        ]
    )
    assert "radroach" in script.lower() or "kitchen" in script.lower()


def test_seeded_phrase_variety_is_deterministic() -> None:
    assert build_daily_script(**_variety(), variant_seed="seed-1") == build_daily_script(
        **_variety(), variant_seed="seed-1"
    )
    openings = {build_daily_script(**_variety(), variant_seed=f"s{n}")[1].split(". ")[0] for n in range(12)}
    assert len(openings) > 1, "Greetings never rotate across seeds"
    endings = {build_daily_script(**_variety(), variant_seed=f"s{n}")[1].rsplit(". ", 2)[-2] for n in range(20)}
    assert len(endings) > 1, "Sign-offs never rotate across seeds"


def test_low_supplies_and_morale_tiers_change_the_tone() -> None:
    script = build_daily_script(**_variety(power=(5, 100)))[1]
    assert "Conserve those bulbs" in script
    assert "Power is at 5%." in script
    cases = {
        95: ("splendid", "jukebox"),
        72: ("steady", "comfortable"),
        40: ("improvement", "dance"),
        20: ("troubling", "grim"),
    }
    for happiness, expected_words in cases.items():
        script = build_daily_script(**_variety(happiness=happiness))[1]
        assert any(word in script for word in expected_words), (
            f"happiness {happiness}: no tone marker from {expected_words}"
        )


def test_segments_reflect_occupancy_and_rotate() -> None:
    # s3 deterministically selects the housing segment; s50 selects the wasteland one.
    assert "Housing reports steady occupancy: 23 of 46 bunks in use, no complaints on file." in _seg()
    assert (
        "The wasteland reports: blazing sun, irritable mole rats"
        in build_daily_script(**_variety(), variant_seed="s50")[1]
    )
    crowded = build_daily_script(**_variety(population=44), variant_seed="s3")[1]
    assert "A note from housing: bunks are filling fast, 44 of 46 spoken for." in crowded
    sparse = build_daily_script(**_variety(population=5), variant_seed="s3")[1]
    assert "Housing reports plenty of open bunks, 5 of 46 occupied." in sparse
    overflow = build_daily_script(**_variety(population_max=8), variant_seed="s3")[1]
    assert "Housing reports 23 residents in a vault built for 8." in overflow


def test_objectives_segment_counts_unclaimed_rewards() -> None:
    assert (
        "The objectives ledger shows 2 rewards unclaimed."
        in build_daily_script(**_variety(rewards_ready=2), variant_seed="s9")[1]
    )
    assert (
        "The objectives ledger shows 1 reward unclaimed."
        in build_daily_script(**_variety(rewards_ready=1), variant_seed="s9")[1]
    )

    # Nothing claimable: a filler line, never a "0 rewards" confession.
    script = build_daily_script(**_variety(), variant_seed="s9")[1]
    assert "nothing pending" in script
    assert "reward" not in script


def test_housing_dropped_by_budget_keeps_capacity_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.utils.broadcast_script as bs

    monkeypatch.setattr(bs, "_SEGMENT_WORD_BUDGET", 30)
    script = build_daily_script(**_variety(population=44), variant_seed="s3")[1]
    assert "A note from housing" not in script, "segment should be budget-dropped"
    assert "44" in script, "capacity must not disappear with the segment"
    assert "46" in script, "capacity must not disappear with the segment"


def _seg(seed: str = "s3") -> str:
    return build_daily_script(**_variety(), variant_seed=seed)[1]


def test_long_headlines_keep_the_script_in_budget() -> None:
    notifications = [
        _n(
            "dweller_died",
            f"Resident Number {n} lost their life in a catastrophic "
            "accident in the water treatment facility during the night shift.",
            dweller_name=f"Resident Number {n}",
        )
        for n in range(4)
    ]
    script = build_daily_script(**_variety(recent_notifications=notifications), variant_seed="busy-day")[1]
    assert script.count("With heavy hearts") == 3
    assert len(script.split()) <= 220


@pytest.mark.parametrize(
    ("notification", "expected"),
    [
        (
            _n(
                "dweller_died",
                "Gerald Moon died in a fire in the Power Generator.",
                dweller_name="Gerald Moon",
            ),
            ["With heavy hearts", "Gerald Moon"],
        ),
        (
            _n("combat_victory", "Your dwellers defeated the attackers, recovered 52 caps."),
            ["A round of applause", "defeated the attackers"],
        ),
        (_n("baby_born", "A healthy baby was born in the living quarters!"), ["A new dweller among us"]),
    ],
)
def test_headline_tone_matches_the_event(notification: dict, expected: list[str]) -> None:
    script = _script(recent_notifications=[notification], vault_number=666)
    for phrase in expected:
        assert phrase in script


def test_untreated_types_stay_untouched() -> None:
    message = "A radroach was spotted in the kitchen."
    script = _script(recent_notifications=[_n("pest_spotted", message)], vault_number=666)
    assert message.rstrip(".") + "." in script or message in script


def test_signoff_present() -> None:
    script = _script(
        **_data(population=5, population_max=10, caps=500, happiness=50)
        | {"power": (10, 10), "food": (10, 10), "water": (10, 10), "vault_number": 99}
    )
    assert "Vault 099" in script or "Vault 99" in script
    assert "peace" in script.lower() or "vault" in script.lower()


def test_no_max_population() -> None:
    title, script = build_daily_script(
        **_data(population=5, population_max=0, caps=500, happiness=50)
        | {"power": (10, 0), "food": (10, 0), "water": (10, 0)}
    )
    assert title  # still returns valid output
    assert "dwellers" in script.lower()
    # Zero-maximum resources report unavailability, never raw quantities.
    assert "readings are unavailable" in script
    assert "stands at 10" not in script


def test_no_vault_number() -> None:
    title, _ = build_daily_script(
        **_data(population=5, population_max=10, caps=500, happiness=50)
        | {"power": (10, 10), "food": (10, 10), "water": (10, 10), "vault_number": None}
    )
    assert title  # still returns valid output
