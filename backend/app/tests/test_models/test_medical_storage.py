import pytest

from app.models.storage import StorageBase
from app.models.vault import VaultBase


def _bounds(field) -> tuple:
    ge = next((m.ge for m in field.metadata if hasattr(m, "ge")), None)
    le = next((m.le for m in field.metadata if hasattr(m, "le")), None)
    return ge, le


@pytest.mark.parametrize("name", ["stimpack", "radaway"])
def test_storage_base_has_medical_fields(name: str) -> None:
    assert name in StorageBase.model_fields, f"StorageBase must have {name} field"
    field = StorageBase.model_fields[name]
    assert (field.default, _bounds(field)) == (0, (0, 10_000))


@pytest.mark.parametrize("name", ["stimpack", "stimpack_max", "radaway", "radaway_max"])
def test_vault_base_has_no_medical_fields(name: str) -> None:
    # Medical stock moved to Storage; the *_max values are computed dynamically.
    assert name not in VaultBase.model_fields, f"{name} must be removed from VaultBase"


def test_storage_instance_medical_fields() -> None:
    storage = StorageBase(stimpack=5, radaway=3)
    assert (storage.stimpack, storage.radaway) == (5, 3)
