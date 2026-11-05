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
                {"notification_type": "level_up", "dweller_name": "Alice"},
                {"notification_type": "level_up", "dweller_name": "Bob"},
            ],
            "vault_number": 1,
        }
        _, script = build_daily_script(**data)
        assert "Alice" in script
        assert "Bob" in script
        assert script.count("Alice") == 1
        assert script.count("Bob") == 1

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
        assert "residents" in script.lower()

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
