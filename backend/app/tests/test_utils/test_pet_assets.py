from pathlib import Path

from app.utils.pet_assets import PET_NAME_TO_IMAGE_FILE, get_pet_image_url

PET_IMAGE_DIR = Path(__file__).parent.parent.parent / "static" / "pet_images"


def test_every_mapped_pet_file_exists_on_disk() -> None:
    missing = [f for f in set(PET_NAME_TO_IMAGE_FILE.values()) if not (PET_IMAGE_DIR / f).exists()]
    assert missing == []


def test_known_pets_resolve() -> None:
    assert get_pet_image_url("CX404") == "/static/pet_images/FOS CX404.png"
    assert get_pet_image_url("  German Shepherd ") == "/static/pet_images/FOS German Shepherd.png"
    assert get_pet_image_url("vault-tec parrot") == "/static/pet_images/FOS Vault-Tec parrot.png"


def test_unknown_or_missing_pet_has_no_url() -> None:
    assert get_pet_image_url("Deathclaw") is None
    assert get_pet_image_url(None) is None
    assert get_pet_image_url("  ") is None
