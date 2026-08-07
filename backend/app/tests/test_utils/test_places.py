"""Tests for deterministic world-map place utilities."""

from uuid import UUID

from app.utils.places import (
    GENERIC_ORIGIN_SKIP,
    collision_nudge,
    normalize_place_name,
    schematic_coords,
    seeded_vault_specs,
)


class TestNormalizePlaceName:
    """Tests for normalize_place_name."""

    def test_equivalence_class(self) -> None:
        assert normalize_place_name("Megaton") == "megaton"
        assert normalize_place_name(" megaton ") == "megaton"
        assert normalize_place_name("MEGATON") == "megaton"

    def test_internal_whitespace_collapsed(self) -> None:
        assert normalize_place_name("Megaton  City") == "megaton city"
        assert normalize_place_name("Megaton City") == "megaton city"
        assert normalize_place_name("New    Vegas") == "new vegas"

    def test_trailing_punctuation_stripped(self) -> None:
        assert normalize_place_name("Megaton!") == "megaton"
        assert normalize_place_name("Megaton,") == "megaton"
        assert normalize_place_name("Megaton.") == "megaton"
        assert normalize_place_name("Rivet City,") == "rivet city"

    def test_never_raises_on_weird_input(self) -> None:
        assert normalize_place_name("") == ""
        assert normalize_place_name("   ") == ""
        assert normalize_place_name("...") == ""
        assert normalize_place_name("!!!") == ""
        assert normalize_place_name(".,!") == ""

    def test_skip_list_membership(self) -> None:
        assert normalize_place_name("Wasteland") in GENERIC_ORIGIN_SKIP
        assert normalize_place_name("The Wasteland") in GENERIC_ORIGIN_SKIP
        assert normalize_place_name("UNKNOWN") in GENERIC_ORIGIN_SKIP
        assert normalize_place_name("") in GENERIC_ORIGIN_SKIP


class TestSchematicCoords:
    """Tests for schematic_coords."""

    def test_deterministic(self) -> None:
        assert schematic_coords("megaton") == schematic_coords("megaton")
        assert schematic_coords("megaton") == schematic_coords(normalize_place_name(" MEGATON "))

    def test_band_and_one_decimal_resolution(self) -> None:
        for i in range(50):
            x, y = schematic_coords(f"place-{i}")
            assert 10.0 <= x <= 89.9
            assert 10.0 <= y <= 89.9
            assert (x * 10).is_integer()
            assert (y * 10).is_integer()

    def test_distinct_names_give_distinct_coords(self) -> None:
        coords = {schematic_coords(name) for name in ("megaton", "rivet city", "goodsprings")}
        assert len(coords) == 3


class TestCollisionNudge:
    """Tests for collision_nudge."""

    def test_free_base_returned_unchanged(self) -> None:
        base = (50.0, 50.0)
        assert collision_nudge(base, set()) == base
        assert collision_nudge(base, {(10.0, 10.0)}) == base

    def test_occupied_base_moves_off(self) -> None:
        base = (50.0, 50.0)
        occupied = {base}
        result = collision_nudge(base, occupied)
        assert result != base
        assert result not in occupied

    def test_result_within_bounds(self) -> None:
        for base in ((0.0, 0.0), (100.0, 100.0), (50.0, 50.0)):
            result = collision_nudge(base, {base})
            assert result != base
            assert 0.0 <= result[0] <= 100.0
            assert 0.0 <= result[1] <= 100.0

    def test_deterministic(self) -> None:
        base = (50.0, 50.0)
        occupied = {base}
        assert collision_nudge(base, occupied) == collision_nudge(base, occupied)


class TestSeededVaultSpecs:
    """Tests for seeded_vault_specs."""

    VAULT_1 = UUID("00000000-0000-0000-0000-000000000001")

    def test_count_in_range(self) -> None:
        for i in range(20):
            specs = seeded_vault_specs(UUID(int=i + 1), home_number=1)
            assert 3 <= len(specs) <= 7

    def test_deterministic_across_calls(self) -> None:
        first = seeded_vault_specs(self.VAULT_1, home_number=1)
        second = seeded_vault_specs(self.VAULT_1, home_number=1)
        assert first == second

    def test_numbers_distinct_and_exclude_home(self) -> None:
        for i in range(10):
            home = i + 1
            specs = seeded_vault_specs(UUID(int=i + 100), home_number=home)
            numbers = [int(seed.name.split()[-1]) for seed in specs]
            assert len(numbers) == len(set(numbers))
            assert home not in numbers
            for number in numbers:
                assert 1 <= number <= 999

    def test_names_formatted(self) -> None:
        specs = seeded_vault_specs(self.VAULT_1, home_number=1)
        for seed in specs:
            assert seed.name == f"Vault {int(seed.name.split()[-1]):03}"

    def test_coords_within_bounds(self) -> None:
        specs = seeded_vault_specs(self.VAULT_1, home_number=1)
        for seed in specs:
            assert 0.0 <= seed.coord_x <= 100.0
            assert 0.0 <= seed.coord_y <= 100.0

    def test_coords_avoid_home_origin_and_each_other(self) -> None:
        specs = seeded_vault_specs(self.VAULT_1, home_number=1)
        coords = {(seed.coord_x, seed.coord_y) for seed in specs}
        assert len(coords) == len(specs)
        assert (50.0, 50.0) not in coords

    def test_different_vaults_differ(self) -> None:
        other = UUID("00000000-0000-0000-0000-000000000002")
        assert seeded_vault_specs(self.VAULT_1, home_number=1) != seeded_vault_specs(other, home_number=1)
