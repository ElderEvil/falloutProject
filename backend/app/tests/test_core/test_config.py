"""Core settings validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_crafting_advance_every_n_ticks_defaults_to_five() -> None:
    assert Settings.model_fields["CRAFTING_ADVANCE_EVERY_N_TICKS"].default == 5


@pytest.mark.parametrize("value", [0, -1])
def test_crafting_advance_every_n_ticks_rejects_values_below_one(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(CRAFTING_ADVANCE_EVERY_N_TICKS=value)
