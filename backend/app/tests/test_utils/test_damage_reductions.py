"""Unit tests for the pure damage-reduction resolver."""

from types import SimpleNamespace

import pytest

from app.core.enums import DamageChannel
from app.core.game_config import game_config
from app.models.pet import Pet
from app.options.pet_modifiers import MAX_RESIST_PCT
from app.utils.damage_reductions import DamageReductions, damage_reductions


@pytest.fixture(autouse=True)
def _identity_mechanics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Faction perks ship dark, so source-selection tests state both switches as a precondition."""
    monkeypatch.setattr(game_config.features, "race_mechanics", True)
    monkeypatch.setattr(game_config.features, "faction_mechanics", True)


def _dweller(race: str | None = None, faction: str | None = None, outfit=None) -> SimpleNamespace:
    attrs: dict[str, str] = {}
    if race is not None:
        attrs["race"] = race
    if faction is not None:
        attrs["faction"] = faction
    dweller = SimpleNamespace(visual_attributes=attrs)
    dweller.outfit = outfit
    return dweller


def _outfit(**fields) -> SimpleNamespace:
    return SimpleNamespace(**fields)


def _pet(name: str) -> Pet:
    return Pet(name=name, rarity="Legendary")


class TestChannelSourceSelection:
    def test_physical_reads_only_incident_response(self) -> None:
        minuteman = _dweller(faction="minutemen", outfit=_outfit(fire_resist=0.5, radiation_resist=1.0))
        reductions = damage_reductions(minuteman, DamageChannel.PHYSICAL)
        assert reductions.shares == (0.15,)
        assert reductions.immune is False

    def test_fire_combines_response_and_outfit(self) -> None:
        minuteman = _dweller(faction="minutemen", outfit=_outfit(fire_resist=0.5))
        reductions = damage_reductions(minuteman, DamageChannel.FIRE)
        assert reductions.shares == (0.15, 0.5)

    def test_fire_ignores_radiation_outfit(self) -> None:
        dweller = _dweller(outfit=_outfit(radiation_resist=1.0))
        reductions = damage_reductions(dweller, DamageChannel.FIRE)
        assert reductions.shares == ()

    def test_radiation_combines_identity_and_outfit(self) -> None:
        human = _dweller(
            race="human",
            faction="children_of_atom",
            outfit=_outfit(outfit_type="power_armor", name="T-51d power armor"),
        )
        reductions = damage_reductions(human, DamageChannel.RADIATION)
        assert reductions.shares == (0.5, 0.75)

    def test_radiation_ignores_fire_outfit(self) -> None:
        dweller = _dweller(outfit=_outfit(fire_resist=0.5))
        reductions = damage_reductions(dweller, DamageChannel.RADIATION)
        assert reductions.shares == ()

    def test_team_share_added_to_every_channel(self) -> None:
        dweller = _dweller()
        for channel in DamageChannel:
            reductions = damage_reductions(dweller, channel, team_share=0.2)
            assert reductions.shares == (0.2,)

    def test_physical_adds_pet_incident_response(self) -> None:
        minuteman = _dweller(faction="minutemen")
        minuteman.pet = _pet("pallas's cat")  # incident_response_pct 0.25
        reductions = damage_reductions(minuteman, DamageChannel.PHYSICAL)
        assert reductions.shares == (0.15, 0.25)

    def test_fire_adds_pet_incident_response(self) -> None:
        minuteman = _dweller(faction="minutemen", outfit=_outfit(fire_resist=0.5))
        minuteman.pet = _pet("pallas's cat")
        reductions = damage_reductions(minuteman, DamageChannel.FIRE)
        assert reductions.shares == (0.15, 0.25, 0.5)

    def test_radiation_adds_pet_radiation_resist(self) -> None:
        human = _dweller(race="human", faction="children_of_atom")
        human.pet = _pet("st. bernard")  # radiation_resist_pct 0.25
        reductions = damage_reductions(human, DamageChannel.RADIATION)
        assert reductions.shares == (0.5, 0.25)

    def test_pet_incident_response_ignored_for_radiation(self) -> None:
        dweller = _dweller()
        dweller.pet = _pet("pallas's cat")
        reductions = damage_reductions(dweller, DamageChannel.RADIATION)
        assert reductions.shares == ()

    def test_pet_radiation_resist_ignored_for_physical(self) -> None:
        dweller = _dweller()
        dweller.pet = _pet("st. bernard")
        reductions = damage_reductions(dweller, DamageChannel.PHYSICAL)
        assert reductions.shares == ()

    def test_plain_dweller_has_no_reductions(self) -> None:
        dweller = _dweller()
        for channel in DamageChannel:
            reductions = damage_reductions(dweller, channel)
            assert reductions.shares == ()
            assert reductions.immune is False


class TestCombinedShareMath:
    def test_combined_share_is_multiplicative_complement(self) -> None:
        reductions = DamageReductions(shares=(0.15, 0.2))
        assert reductions.combined_share == pytest.approx(1 - 0.85 * 0.8)

    def test_combined_share_is_order_independent(self) -> None:
        a = DamageReductions(shares=(0.15, 0.2, 0.5))
        b = DamageReductions(shares=(0.5, 0.15, 0.2))
        c = DamageReductions(shares=(0.2, 0.5, 0.15))
        assert a.combined_share == b.combined_share == c.combined_share

    def test_combined_share_is_capped_at_max_resist(self) -> None:
        reductions = DamageReductions(shares=(0.9, 0.9))
        assert reductions.combined_share == pytest.approx(MAX_RESIST_PCT)

    def test_pet_resist_is_capped_at_max_resist(self, monkeypatch) -> None:
        from app.options.pet_modifiers import PET_EFFECT_BY_NAME, PetEffect

        monkeypatch.setitem(PET_EFFECT_BY_NAME, "cap test pet", PetEffect(radiation_resist_pct=0.95))
        human = _dweller(race="human", faction="children_of_atom")
        human.pet = _pet("cap test pet")
        reductions = damage_reductions(human, DamageChannel.RADIATION)
        # 1 - 0.5 * 0.05 = 0.975 → capped at 0.95
        assert reductions.combined_share == pytest.approx(MAX_RESIST_PCT)

    def test_apply_single_share_matches_sequential(self) -> None:
        reductions = DamageReductions(shares=(0.15,))
        assert reductions.apply(20) == 17

    def test_apply_no_shares_is_identity(self) -> None:
        reductions = DamageReductions()
        assert reductions.apply(10) == 10

    def test_apply_truncates_once_not_per_share(self) -> None:
        """Sequential truncation would give int(int(3*0.85)*0.8) = 1; one combined truncation gives 2."""
        reductions = DamageReductions(shares=(0.15, 0.2))
        assert reductions.apply(3) == 2


class TestImmunity:
    @pytest.mark.parametrize("race", ["ghoul", "super_mutant", "synth"])
    def test_immune_returns_zero(self, race: str) -> None:
        dweller = _dweller(race=race)
        reductions = damage_reductions(dweller, DamageChannel.RADIATION)
        assert reductions.immune is True
        assert reductions.apply(100) == 0

    def test_immunity_is_radiation_only(self) -> None:
        ghoul = _dweller(race="ghoul")
        physical = damage_reductions(ghoul, DamageChannel.PHYSICAL)
        assert physical.immune is False
        assert physical.apply(100) == 100


class TestResistedByOutfit:
    def test_false_keeps_identity_resist(self) -> None:
        human = _dweller(
            race="human",
            faction="children_of_atom",
            outfit=_outfit(outfit_type="power_armor", name="T-51d power armor"),
        )
        reductions = damage_reductions(human, DamageChannel.RADIATION, resisted_by_outfit=False)
        assert reductions.shares == (0.5,)
        assert reductions.apply(10) == 5

    def test_true_adds_outfit_resist(self) -> None:
        human = _dweller(
            race="human",
            faction="children_of_atom",
            outfit=_outfit(outfit_type="power_armor", name="T-51d power armor"),
        )
        reductions = damage_reductions(human, DamageChannel.RADIATION, resisted_by_outfit=True)
        assert reductions.shares == (0.5, 0.75)
        assert reductions.apply(10) == 1  # int(10 * 0.5 * 0.25)
