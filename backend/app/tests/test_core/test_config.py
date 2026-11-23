import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_crafting_advance_every_n_ticks_defaults_to_five_and_rejects_below_one() -> None:
    assert Settings.model_fields["CRAFTING_ADVANCE_EVERY_N_TICKS"].default == 5
    for value in (0, -1):
        with pytest.raises(ValidationError):
            Settings(CRAFTING_ADVANCE_EVERY_N_TICKS=value)
