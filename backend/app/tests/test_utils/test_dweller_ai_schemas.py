"""Test DwellerBackstory / ExtendedBio item-level max_length on visited_places."""

import pydantic
import pytest

from app.schemas.dweller_ai import DwellerBackstory, ExtendedBio


def test_dweller_backstory_visited_places_65_chars_rejected():
    """visited_places item > 64 chars raises pydantic.ValidationError."""
    with pytest.raises(pydantic.ValidationError):
        DwellerBackstory(
            bio="A test bio for backstory validation.",
            origin_place="Megaton",
            visited_places=["x" * 65],
        )


def test_dweller_backstory_visited_places_64_chars_valid():
    """visited_places item == 64 chars is valid (edge case)."""
    result = DwellerBackstory(
        bio="A test bio for backstory validation.",
        origin_place="Megaton",
        visited_places=["x" * 64],
    )
    assert result.visited_places == ["x" * 64]


def test_extended_bio_visited_places_65_chars_rejected():
    """visited_places item > 64 chars raises pydantic.ValidationError on ExtendedBio."""
    with pytest.raises(pydantic.ValidationError):
        ExtendedBio(
            extended_bio="More details about the dweller.",
            visited_places=["y" * 65],
        )
