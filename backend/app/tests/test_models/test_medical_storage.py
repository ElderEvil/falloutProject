"""Tests for medical supply field migration from Vault to Storage model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.storage import Storage, StorageBase
from app.models.vault import Vault, VaultBase
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


class TestStorageHasMedicalFields:
    """Storage model now owns stimpack/radaway fields."""

    def _check_ge(self, field, expected: int) -> None:
        """Check Ge constraint from Pydantic metadata."""
        for m in field.metadata:
            if hasattr(m, "ge"):
                assert m.ge == expected
                return
        pytest.fail(f"No Ge constraint found in {field.metadata}")

    def _check_le(self, field, expected: int) -> None:
        """Check Le constraint from Pydantic metadata."""
        for m in field.metadata:
            if hasattr(m, "le"):
                assert m.le == expected
                return
        pytest.fail(f"No Le constraint found in {field.metadata}")

    def test_storage_base_has_stimpack_field(self) -> None:
        """StorageBase should have stimpack field."""
        assert "stimpack" in StorageBase.model_fields, "StorageBase must have stimpack field"
        field = StorageBase.model_fields["stimpack"]
        assert field.default == 0
        self._check_ge(field, 0)
        self._check_le(field, 10_000)

    def test_storage_base_has_radaway_field(self) -> None:
        """StorageBase should have radaway field."""
        assert "radaway" in StorageBase.model_fields, "StorageBase must have radaway field"
        field = StorageBase.model_fields["radaway"]
        assert field.default == 0
        self._check_ge(field, 0)
        self._check_le(field, 10_000)


class TestVaultNoMedicalFields:
    """Vault model no longer has stimpack/radaway fields."""

    def test_vault_base_does_not_have_stimpack(self) -> None:
        """VaultBase must NOT have stimpack field (moved to Storage)."""
        assert "stimpack" not in VaultBase.model_fields, "stimpack must be removed from VaultBase"

    def test_vault_base_does_not_have_stimpack_max(self) -> None:
        """VaultBase must NOT have stimpack_max field (computed dynamically)."""
        assert "stimpack_max" not in VaultBase.model_fields, "stimpack_max must be removed from VaultBase"

    def test_vault_base_does_not_have_radaway(self) -> None:
        """VaultBase must NOT have radaway field (moved to Storage)."""
        assert "radaway" not in VaultBase.model_fields, "radaway must be removed from VaultBase"

    def test_vault_base_does_not_have_radaway_max(self) -> None:
        """VaultBase must NOT have radaway_max field (computed dynamically)."""
        assert "radaway_max" not in VaultBase.model_fields, "radaway_max must be removed from VaultBase"


def test_storage_model_defaults_medical_fields() -> None:
    """Storage model default values for stimpack/radaway should be 0."""
    field_s = StorageBase.model_fields["stimpack"]
    field_r = StorageBase.model_fields["radaway"]
    assert field_s.default == 0
    assert field_r.default == 0


def test_storage_instance_medical_fields() -> None:
    """Creating a Storage instance should accept stimpack/radaway."""
    storage = StorageBase(stimpack=5, radaway=3)
    assert storage.stimpack == 5
    assert storage.radaway == 3
