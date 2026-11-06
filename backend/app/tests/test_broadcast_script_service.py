"""Tests for broadcast script renderer — pure function, no I/O."""

from datetime import datetime

from app.utils.broadcast_script import build_daily_script


class TestScriptWordCount:
    """Ensure the script stays in the 120-180 word target range."""

    def _baseline_data(self):
        return {
            "population": 25,
            "population_max": 50,
            "caps": 5000,
            "happiness": 72,
            "power": (80, 100),
            "food": (200, 300),
            "water": (150, 200),
            "recent_notifications": [],
            "vault_number": 13,
        }

    def test_default_script_word_count(self):
        title, script = build_daily_script(**self._baseline_data())
        words = len(script.split())
        assert 100 <= words <= 220, f"Script word count {words} outside expected range"

    def test_empty_notifications(self):
        data = self._baseline_data()
        data["recent_notifications"] = []
        title, script = build_daily_script(**data)
        words = len(script.split())
        assert words > 0

    def test_title_contains_date(self):
        now = datetime(2026, 6, 15, 12, 0)
        data = self._baseline_data()
        data["recent_notifications"] = []
        title, script = build_daily_script(**data, _now=now)
        assert "June 15, 2026" in title


class TestGenderSplit:
    """Gender split renders from the stored population counts."""

    def test_gender_split_from_counts(self):
        data = {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 60,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": [],
            "gender_counts": [("male", 2), ("female", 1)],
            "vault_number": 7,
        }
        _, script = build_daily_script(**data)
        assert "male" in script.lower()
        assert "female" in script.lower()


class TestResourceReporting:
    """Resource percentages appear in the correct format."""

    def test_resource_percentages(self):
        data = {
            "population": 5,
            "population_max": 10,
            "caps": 500,
            "happiness": 80,
            "power": (10, 20),
            "food": (0, 50),
            "water": (50, 50),
            "recent_notifications": [],
            "vault_number": 3,
        }
        _, script = build_daily_script(**data)
        assert "50%" in script
        assert "0%" in script
        assert "100%" in script
        # Percentages only - the raw "current of maximum" numbers are noise.
        assert "of 50" not in script
        assert "of 20" not in script


class TestNotificationBatching:
    """Level-up and other notifications are batched into one line."""

    def test_level_up_notification(self):
        data = {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 70,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": [
                {"notification_type": "dweller_level_up", "name": "Max"},
            ],
            "vault_number": 1,
        }
        _, script = build_daily_script(**data)
        assert "level" in script.lower()

    def test_unnamed_level_up_keeps_fallback(self):
        data = {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 70,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": [
                {"notification_type": "level_up", "message": "A dweller reached level 6."},
            ],
            "vault_number": 1,
        }
        _, script = build_daily_script(**data)
        assert "level" in script.lower()

    def test_level_ups_use_each_dwellers_name_once(self):
        data = {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 70,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": [
                {
                    "notification_type": "level_up",
                    "title": "Alice Leveled Up!",
                    "message": "Alice reached level 6!",
                },
                {
                    "notification_type": "level_up",
                    "title": "Bob Leveled Up!",
                    "message": "Bob reached level 7!",
                },
            ],
            "vault_number": 1,
        }
        _, script = build_daily_script(**data)
        assert "Alice" in script
        assert "Bob" in script
        assert script.count("Alice") == 1
        assert script.count("Bob") == 1

    def test_vault_prefix_stripped_from_headlines(self):
        """The "[Vault N]" notification prefix never reaches the broadcast."""
        data = {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 70,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": [
                {
                    "notification_type": "level_up",
                    "title": "[Vault 666] Alice Leveled Up!",
                    "message": "[Vault 666] Alice reached level 6!",
                },
                {
                    "notification_type": "dweller_training_complete",
                    "dweller_name": "[Vault 666] Bob",
                    "message": "[Vault 666] Bob finished training Strength!",
                },
            ],
            "vault_number": 666,
        }
        _, script = build_daily_script(**data)
        assert "[Vault" not in script
        assert "Alice" in script
        assert "Bob" in script

    def test_active_combat_alert_is_not_a_headline(self):
        data = {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 70,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": [
                {
                    "notification_type": "combat_started",
                    "message": "[Vault 666] 🐀 Mole Rat Attack in Power Generator! Send dwellers to defend.",
                },
                {
                    "notification_type": "combat_victory",
                    "message": "[Vault 666] Your dwellers defeated the attackers, recovered 52 caps.",
                },
            ],
            "vault_number": 666,
        }
        _, script = build_daily_script(**data)
        assert "defeated the attackers" in script
        assert "Send dwellers to defend" not in script

    def test_multiple_notifications_batched(self):
        data = {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 70,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": [
                {"message": "A radroach was spotted in the kitchen."},
                {"message": "A dweller found some caps."},
                {"message": "Power generator needs repair."},
                {"message": "Extra notification should be truncated."},
            ],
            "vault_number": 1,
        }
        _, script = build_daily_script(**data)
        # All 4 notifications but truncated to ~3 notable lines
        assert "radroach" in script.lower() or "kitchen" in script.lower()


class TestPhraseVariety:
    """Deterministic phrase pools: stable per day, varied across days/seeds."""

    def _data(self):
        return {
            "population": 23,
            "population_max": 46,
            "caps": 1852,
            "happiness": 87,
            "power": (300, 300),
            "food": (300, 300),
            "water": (300, 300),
            "recent_notifications": [],
            "gender_counts": [("male", 13), ("female", 10)],
            "vault_number": 666,
        }

    def test_same_seed_is_deterministic(self):
        first = build_daily_script(**self._data(), variant_seed="seed-1")
        second = build_daily_script(**self._data(), variant_seed="seed-1")
        assert first == second

    def test_seeds_produce_varied_greetings(self):
        openings = {build_daily_script(**self._data(), variant_seed=f"s{n}")[1].split(". ")[0] for n in range(12)}
        assert len(openings) > 1, "Greetings never rotate across seeds"

    def test_seeds_produce_varied_sign_offs(self):
        endings = {build_daily_script(**self._data(), variant_seed=f"s{n}")[1].rsplit(". ", 2)[-2] for n in range(20)}
        assert len(endings) > 1, "Sign-offs never rotate across seeds"

    def test_low_supplies_get_flavor(self):
        data = self._data()
        data["power"] = (5, 100)
        _, script = build_daily_script(**data)
        assert "Conserve those bulbs" in script
        assert "Power is at 5%." in script

    def test_morale_tiers_change_the_tone(self):
        cases = {
            95: ("splendid", "jukebox"),
            72: ("steady", "comfortable"),
            40: ("improvement", "dance"),
            20: ("troubling", "grim"),
        }
        for happiness, expected_words in cases.items():
            data = self._data()
            data["happiness"] = happiness
            _, script = build_daily_script(**data)
            assert any(word in script for word in expected_words), (
                f"happiness {happiness}: no tone marker from {expected_words}"
            )


class TestRotatingSegments:
    """One rotating segment per broadcast; different seeds, different segments."""

    def _data(self):
        return {
            "population": 23,
            "population_max": 46,
            "caps": 1852,
            "happiness": 87,
            "power": (300, 300),
            "food": (300, 300),
            "water": (300, 300),
            "recent_notifications": [],
            "vault_number": 666,
        }

    def test_housing_segment_reflects_occupancy(self):
        # s3 deterministically selects the housing segment (asserted in
        # test_segment_rotates_across_seeds), so these hit the housing branch.
        crowded = self._data() | {"population": 44, "population_max": 46}
        _, script = build_daily_script(**crowded, variant_seed="s3")
        assert "A note from housing: bunks are filling fast, 44 of 46 spoken for." in script
        sparse = self._data() | {"population": 5, "population_max": 46}
        _, script = build_daily_script(**sparse, variant_seed="s3")
        assert "Housing reports plenty of open bunks, 5 of 46 occupied." in script
        overflow = self._data() | {"population": 23, "population_max": 8}
        _, script = build_daily_script(**overflow, variant_seed="s3")
        assert "Housing reports 23 residents in a vault built for 8." in script

    def test_segment_rotates_across_seeds(self):
        _, script = build_daily_script(**self._data(), variant_seed="s3")
        assert "Housing reports steady occupancy: 23 of 46 bunks in use, no complaints on file." in script
        _, script = build_daily_script(**self._data(), variant_seed="s50")
        assert "The wasteland reports: blazing sun, irritable mole rats" in script

    def test_objectives_segment_counts_unclaimed_rewards(self):
        # s9 selects the objectives segment; the count is the only detail.
        _, script = build_daily_script(**self._data(), rewards_ready=2, variant_seed="s9")
        assert "The objectives ledger shows 2 rewards unclaimed." in script
        _, script = build_daily_script(**self._data(), rewards_ready=1, variant_seed="s9")
        assert "The objectives ledger shows 1 reward unclaimed." in script

    def test_objectives_segment_zero_state_has_no_count(self):
        # Nothing claimable: a filler line, never a "0 rewards" confession.
        _, script = build_daily_script(**self._data(), variant_seed="s9")
        assert "nothing pending" in script
        assert "reward" not in script

    def test_housing_dropped_by_budget_keeps_capacity_numbers(self, monkeypatch):
        """When the budget drops the housing segment, the population line keeps its numbers."""
        import app.utils.broadcast_script as bs

        monkeypatch.setattr(bs, "_SEGMENT_WORD_BUDGET", 30)
        crowded = self._data() | {"population": 44, "population_max": 46}
        _, script = build_daily_script(**crowded, variant_seed="s3")
        assert "A note from housing" not in script, "segment should be budget-dropped"
        assert "44" in script, "capacity must not disappear with the segment"
        assert "46" in script, "capacity must not disappear with the segment"

    def test_long_headlines_keep_the_script_in_budget(self):
        data = self._data()
        data["recent_notifications"] = [
            {
                "notification_type": "dweller_died",
                "dweller_name": f"Resident Number {n}",
                "message": (
                    f"Resident Number {n} lost their life in a catastrophic "
                    "accident in the water treatment facility during the night shift."
                ),
            }
            for n in range(4)
        ]
        _, script = build_daily_script(**data, variant_seed="busy-day")
        # Three somber headlines render; the script still respects the ceiling.
        assert script.count("With heavy hearts") == 3
        assert len(script.split()) <= 220


class TestHeadlineTones:
    """Headlines get tone-tinted wrappers by notification type."""

    def _data(self, notifications):
        return {
            "population": 10,
            "population_max": 20,
            "caps": 1000,
            "happiness": 70,
            "power": (50, 100),
            "food": (50, 100),
            "water": (50, 100),
            "recent_notifications": notifications,
            "vault_number": 666,
        }

    def test_death_headline_is_somber(self):
        _, script = build_daily_script(
            **self._data(
                [
                    {
                        "notification_type": "dweller_died",
                        "dweller_name": "Gerald Moon",
                        "message": "Gerald Moon died in a fire in the Power Generator.",
                    }
                ]
            )
        )
        assert "With heavy hearts" in script
        assert "Gerald Moon" in script

    def test_victory_headline_celebrates(self):
        _, script = build_daily_script(
            **self._data(
                [
                    {
                        "notification_type": "combat_victory",
                        "message": "Your dwellers defeated the attackers, recovered 52 caps.",
                    }
                ]
            )
        )
        assert "A round of applause" in script
        assert "defeated the attackers" in script

    def test_birth_headline_celebrates_arrival(self):
        _, script = build_daily_script(
            **self._data(
                [
                    {
                        "notification_type": "baby_born",
                        "message": "A healthy baby was born in the living quarters!",
                    }
                ]
            )
        )
        assert "A new dweller among us" in script

    def test_untreated_types_stay_untouched(self):
        message = "A radroach was spotted in the kitchen."
        _, script = build_daily_script(**self._data([{"notification_type": "pest_spotted", "message": message}]))
        assert message.rstrip(".") + "." in script or message in script


class TestSignOff:
    """Every script ends with a 1950s-style sign-off."""

    def test_signoff_present(self):
        data = {
            "population": 5,
            "population_max": 10,
            "caps": 500,
            "happiness": 50,
            "power": (10, 10),
            "food": (10, 10),
            "water": (10, 10),
            "recent_notifications": [],
            "vault_number": 99,
        }
        _, script = build_daily_script(**data)
        assert "Vault 099" in script or "Vault 99" in script
        assert "peace" in script.lower() or "vault" in script.lower()


class TestEdgeCases:
    def test_no_max_population(self):
        data = {
            "population": 5,
            "population_max": 0,
            "caps": 500,
            "happiness": 50,
            "power": (10, 0),
            "food": (10, 0),
            "water": (10, 0),
            "recent_notifications": [],
            "vault_number": 1,
        }
        title, script = build_daily_script(**data)
        assert title  # still returns valid output
        assert "dwellers" in script.lower()
        # Zero-maximum resources report unavailability, never raw quantities.
        assert "readings are unavailable" in script
        assert "stands at 10" not in script

    def test_no_vault_number(self):
        data = {
            "population": 5,
            "population_max": 10,
            "caps": 500,
            "happiness": 50,
            "power": (10, 10),
            "food": (10, 10),
            "water": (10, 10),
            "recent_notifications": [],
            "vault_number": None,
        }
        title, script = build_daily_script(**data)
        assert title  # still returns valid output
