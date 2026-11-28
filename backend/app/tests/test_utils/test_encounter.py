import pytest

from app.core.enums import EncounterBand
from app.utils.encounter import band_damage, profile_for, reference_power


def test_reference_power_is_base_special_unarmed():
    assert reference_power(1) == pytest.approx(6.0)
    assert reference_power(5) == pytest.approx(14.0)


def test_profile_bands_are_inclusive_at_each_threshold():
    profile = profile_for(5)
    assert (profile.min_party, profile.ref_level) == (3, 9)
    assert profile.required_power == pytest.approx(66.0)
    assert profile.complete_power == pytest.approx(85.8)
    assert profile.band(65.9) is EncounterBand.REPELLED
    assert profile.band(66.0) is EncounterBand.COSTLY
    assert profile.band(85.7) is EncounterBand.COSTLY
    assert profile.band(85.8) is EncounterBand.CLEAN


def test_profile_clamps_difficulty_to_one_to_five():
    assert profile_for(0).danger == 1
    assert profile_for(99).danger == 5


def test_band_damage_is_each_members_own_share():
    assert band_damage(100, EncounterBand.CLEAN) == 0
    assert band_damage(100, EncounterBand.COSTLY) == 25
    assert band_damage(200, EncounterBand.COSTLY) == 50
    assert band_damage(100, EncounterBand.REPELLED) == 40


def test_dispatch_config_rejects_contract_breaking_band_tuning():
    from pydantic import ValidationError

    from app.core.game_config import DispatchConfig

    with pytest.raises(ValidationError):
        DispatchConfig(complete_mult=1.0)
    with pytest.raises(ValidationError):
        DispatchConfig(band_damage_pct={"clean": 0.0, "costly": 0.0, "repelled": 0.4})
    with pytest.raises(ValidationError):
        DispatchConfig(band_damage_pct={"costly": 0.25, "repelled": 0.4})


@pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
def test_each_profile_reaches_repelled_costly_and_clean(difficulty):
    profile = profile_for(difficulty)
    assert profile.band(profile.required_power - 0.01) is EncounterBand.REPELLED
    assert profile.band(profile.required_power) is EncounterBand.COSTLY
    assert profile.band(profile.complete_power) is EncounterBand.CLEAN
