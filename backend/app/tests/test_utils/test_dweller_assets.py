from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.core.enums import GenderEnum, GhoulFeralnessEnum, RaceEnum, SuperMutantMutationEnum, SynthTypeEnum
from app.utils.dweller_assets import (
    HUMAN_PORTRAIT_HAIR_COLORS,
    HUMAN_PORTRAIT_SKIN_TONES,
    IMAGE_DIR,
    THUMBNAIL_DIR,
    default_dweller_image_urls,
    is_default_dweller_image,
    resolve_dweller_image_urls,
)

STATIC_ROOT = Path(__file__).resolve().parents[2] / "static"

MATRIX = [
    ("human", "male", None, "FOS_Dw_Default_Human_Male.webp"),
    ("human", "female", None, "FOS_Dw_Default_Human_Female.webp"),
    ("ghoul", "male", "sane", "FOS_Dw_Default_Ghoul_Male_Sane.webp"),
    ("ghoul", "male", "wild", "FOS_Dw_Default_Ghoul_Male_Wild.webp"),
    ("ghoul", "male", "feral", "FOS_Dw_Default_Ghoul_Male_Feral.webp"),
    ("ghoul", "female", "sane", "FOS_Dw_Default_Ghoul_Female_Sane.webp"),
    ("ghoul", "female", "wild", "FOS_Dw_Default_Ghoul_Female_Wild.webp"),
    ("ghoul", "female", "feral", "FOS_Dw_Default_Ghoul_Female_Feral.webp"),
    ("super_mutant", "male", "mild", "FOS_Dw_Default_SuperMutant_Male_Mild.webp"),
    ("super_mutant", "male", "average", "FOS_Dw_Default_SuperMutant_Male_Average.webp"),
    ("super_mutant", "male", "behemoth", "FOS_Dw_Default_SuperMutant_Male_Behemoth.webp"),
    ("super_mutant", "female", "mild", "FOS_Dw_Default_SuperMutant_Female_Mild.webp"),
    ("super_mutant", "female", "average", "FOS_Dw_Default_SuperMutant_Female_Average.webp"),
    ("super_mutant", "female", "behemoth", "FOS_Dw_Default_SuperMutant_Female_Behemoth.webp"),
    ("synth", None, "gen_1", "FOS_Dw_Default_Synth_Gen1.webp"),
    ("synth", "male", "gen_2", "FOS_Dw_Default_Synth_Male_Gen2.webp"),
    ("synth", "female", "gen_2", "FOS_Dw_Default_Synth_Female_Gen2.webp"),
    ("synth", "male", "gen_3", "FOS_Dw_Default_Synth_Male_Gen3.webp"),
    ("synth", "female", "gen_3", "FOS_Dw_Default_Synth_Female_Gen3.webp"),
]


@pytest.mark.parametrize(("race", "gender", "state", "filename"), MATRIX)
def test_default_matrix(race: str, gender: str | None, state: str | None, filename: str) -> None:
    image, thumbnail = default_dweller_image_urls(race, gender, state)

    assert image == f"{IMAGE_DIR}/base/{filename}"
    assert thumbnail == f"{THUMBNAIL_DIR}/base/{filename}"


@pytest.mark.parametrize(("race", "gender", "state", "filename"), MATRIX)
def test_default_assets_exist(race: str, gender: str | None, state: str | None, filename: str) -> None:
    image, thumbnail = default_dweller_image_urls(race, gender, state)

    assert (STATIC_ROOT / image.removeprefix("/static/")).is_file()
    assert (STATIC_ROOT / thumbnail.removeprefix("/static/")).is_file()


def test_gen1_synth_ignores_gender() -> None:
    male = default_dweller_image_urls("synth", "male", "gen_1")
    female = default_dweller_image_urls("synth", "female", "gen_1")

    assert male == female
    assert male[0] == f"{IMAGE_DIR}/base/FOS_Dw_Default_Synth_Gen1.webp"


@pytest.mark.parametrize(
    ("race", "gender", "state", "expected"),
    [
        (None, "female", None, "FOS_Dw_Default_Human_Female.webp"),
        ("vault_dweller", "male", None, "FOS_Dw_Default_Human_Male.webp"),
        ("ghoul", "male", None, "FOS_Dw_Default_Ghoul_Male_Sane.webp"),
        ("ghoul", "male", "not-a-state", "FOS_Dw_Default_Ghoul_Male_Sane.webp"),
        ("super_mutant", "female", None, "FOS_Dw_Default_SuperMutant_Female_Average.webp"),
        ("super_mutant", "female", "not-a-state", "FOS_Dw_Default_SuperMutant_Female_Average.webp"),
        ("synth", "male", None, "FOS_Dw_Default_Synth_Male_Gen3.webp"),
        ("synth", "female", "not-a-state", "FOS_Dw_Default_Synth_Female_Gen3.webp"),
    ],
)
def test_fallbacks(race: str | None, gender: str, state: str | None, expected: str) -> None:
    image, _ = default_dweller_image_urls(race, gender, state)

    assert image == f"{IMAGE_DIR}/base/{expected}"


def test_accepts_enum_values() -> None:
    image, _ = default_dweller_image_urls(
        RaceEnum.GHOUL,
        GenderEnum.FEMALE,
        GhoulFeralnessEnum.WILD,
    )
    super_mutant, _ = default_dweller_image_urls(
        RaceEnum.SUPER_MUTANT,
        GenderEnum.MALE,
        SuperMutantMutationEnum.BEHEMOTH,
    )
    gen1, _ = default_dweller_image_urls(RaceEnum.SYNTH, GenderEnum.MALE, SynthTypeEnum.GEN_1)

    assert image == f"{IMAGE_DIR}/base/FOS_Dw_Default_Ghoul_Female_Wild.webp"
    assert super_mutant == f"{IMAGE_DIR}/base/FOS_Dw_Default_SuperMutant_Male_Behemoth.webp"
    assert gen1 == f"{IMAGE_DIR}/base/FOS_Dw_Default_Synth_Gen1.webp"


def test_resolve_preserves_existing_urls() -> None:
    dweller = SimpleNamespace(
        image_url="https://example.test/custom.png",
        thumbnail_url="https://example.test/custom-thumb.png",
        gender=GenderEnum.MALE,
        visual_attributes={"race": "ghoul", "state_of_being": "feral"},
    )

    assert resolve_dweller_image_urls(dweller) == (
        "https://example.test/custom.png",
        "https://example.test/custom-thumb.png",
    )


def test_resolve_fills_missing_thumbnail_from_image() -> None:
    dweller = SimpleNamespace(
        image_url="https://example.test/custom.png",
        thumbnail_url=None,
        gender=GenderEnum.MALE,
        visual_attributes=None,
    )

    assert resolve_dweller_image_urls(dweller) == (
        "https://example.test/custom.png",
        "https://example.test/custom.png",
    )


def test_resolve_fills_missing_image_from_thumbnail() -> None:
    dweller = SimpleNamespace(
        image_url=None,
        thumbnail_url="https://example.test/custom-thumb.png",
        gender=GenderEnum.FEMALE,
        visual_attributes=None,
    )

    assert resolve_dweller_image_urls(dweller) == (
        "https://example.test/custom-thumb.png",
        "https://example.test/custom-thumb.png",
    )


def test_resolve_uses_default_when_both_missing_dict_attrs() -> None:
    dweller = SimpleNamespace(
        image_url=None,
        thumbnail_url="",
        gender=GenderEnum.FEMALE,
        visual_attributes={"race": "super_mutant", "state_of_being": "mild"},
    )

    assert resolve_dweller_image_urls(dweller) == (
        f"{IMAGE_DIR}/base/FOS_Dw_Default_SuperMutant_Female_Mild.webp",
        f"{THUMBNAIL_DIR}/base/FOS_Dw_Default_SuperMutant_Female_Mild.webp",
    )


def test_resolve_uses_default_when_both_missing_typed_attrs() -> None:
    dweller = SimpleNamespace(
        image_url=None,
        thumbnail_url=None,
        gender=GenderEnum.MALE,
        visual_attributes=SimpleNamespace(race=RaceEnum.SYNTH, state_of_being=SynthTypeEnum.GEN_1),
    )

    assert resolve_dweller_image_urls(dweller) == (
        f"{IMAGE_DIR}/base/FOS_Dw_Default_Synth_Gen1.webp",
        f"{THUMBNAIL_DIR}/base/FOS_Dw_Default_Synth_Gen1.webp",
    )


def test_human_variant_matrix_is_complete_and_on_disk() -> None:
    for gender in ("male", "female"):
        for skin in HUMAN_PORTRAIT_SKIN_TONES:
            for hair in HUMAN_PORTRAIT_HAIR_COLORS:
                filename = f"FOS_Dw_Default_Human_{gender.title()}_Skin{skin}_Hair{hair}.webp"
                image, thumbnail = default_dweller_image_urls("human", gender, None, skin, hair)

                assert image == f"{IMAGE_DIR}/variants/adult/{filename}"
                assert thumbnail == f"{THUMBNAIL_DIR}/variants/adult/{filename}"
                assert (STATIC_ROOT / image.removeprefix("/static/")).is_file()
                assert (STATIC_ROOT / thumbnail.removeprefix("/static/")).is_file()


@pytest.mark.parametrize(
    ("skin", "hair"),
    [("Light", "blonde"), ("Pale", "white"), ("Dark Brown", "blue")],
)
def test_unsupported_human_colors_fall_back_to_base(skin: str, hair: str) -> None:
    image, _ = default_dweller_image_urls("human", "male", None, skin, hair)

    assert image == f"{IMAGE_DIR}/base/FOS_Dw_Default_Human_Male.webp"


def test_non_human_ignores_color_variants() -> None:
    image, _ = default_dweller_image_urls("ghoul", "male", "wild", "Ebony", "red")

    assert image == f"{IMAGE_DIR}/base/FOS_Dw_Default_Ghoul_Male_Wild.webp"


def test_resolve_uses_human_variant() -> None:
    dweller = SimpleNamespace(
        image_url=None,
        thumbnail_url=None,
        gender=GenderEnum.FEMALE,
        visual_attributes={"race": "human", "skin_tone": "Tan", "hair_color": "red"},
    )

    assert resolve_dweller_image_urls(dweller) == (
        f"{IMAGE_DIR}/variants/adult/FOS_Dw_Default_Human_Female_SkinTan_HairRed.webp",
        f"{THUMBNAIL_DIR}/variants/adult/FOS_Dw_Default_Human_Female_SkinTan_HairRed.webp",
    )


def test_accepts_uppercase_db_values() -> None:
    human, _ = default_dweller_image_urls("HUMAN", "FEMALE", None)
    ghoul, _ = default_dweller_image_urls("GHOUL", "MALE", "WILD")
    mutant, _ = default_dweller_image_urls("SUPER_MUTANT", "FEMALE", "BEHEMOTH")

    assert human == f"{IMAGE_DIR}/base/FOS_Dw_Default_Human_Female.webp"
    assert ghoul == f"{IMAGE_DIR}/base/FOS_Dw_Default_Ghoul_Male_Wild.webp"
    assert mutant == f"{IMAGE_DIR}/base/FOS_Dw_Default_SuperMutant_Female_Behemoth.webp"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (f"{IMAGE_DIR}/base/FOS_Dw_Default_Human_Male.webp", True),
        (f"{THUMBNAIL_DIR}/base/FOS_Dw_Default_Human_Male.webp", True),
        ("https://example.test/custom.png", False),
        ("/static/legendary_dweller_images/FOS_Dw_Butch.png", False),
        (None, False),
        ("", False),
    ],
)
def test_is_default_dweller_image(url: str | None, expected: bool) -> None:
    assert is_default_dweller_image(url) is expected


def test_child_and_teen_variants() -> None:
    child, child_thumb = default_dweller_image_urls("human", "male", None, "Ebony", "black", "child")
    teen, teen_thumb = default_dweller_image_urls("human", "female", None, "Pale", "red", "teen")

    assert child == f"{IMAGE_DIR}/variants/child/FOS_Dw_Default_Human_Child_Male_SkinEbony_HairBlack.webp"
    assert child_thumb == (f"{THUMBNAIL_DIR}/variants/child/FOS_Dw_Default_Human_Child_Male_SkinEbony_HairBlack.webp")
    assert teen == f"{IMAGE_DIR}/variants/teen/FOS_Dw_Default_Human_Teen_Female_SkinPale_HairRed.webp"
    assert teen_thumb == (f"{THUMBNAIL_DIR}/variants/teen/FOS_Dw_Default_Human_Teen_Female_SkinPale_HairRed.webp")


def test_grey_child_and_teen_fall_back_to_brown() -> None:
    child, _ = default_dweller_image_urls("human", "female", None, "Tan", "gray", "child")
    teen, _ = default_dweller_image_urls("human", "male", None, "Brown", "gray", "teen")

    assert child == f"{IMAGE_DIR}/variants/child/FOS_Dw_Default_Human_Child_Female_SkinTan_HairBrown.webp"
    assert teen == f"{IMAGE_DIR}/variants/teen/FOS_Dw_Default_Human_Teen_Male_SkinBrown_HairBrown.webp"


def test_teen_female_ebony_variant() -> None:
    image, _ = default_dweller_image_urls("human", "female", None, "Ebony", "black", "teen")

    assert image == f"{IMAGE_DIR}/variants/teen/FOS_Dw_Default_Human_Teen_Female_SkinEbony_HairBlack.webp"


def test_resolve_uses_age_group() -> None:
    from app.core.enums import AgeGroupEnum

    dweller = SimpleNamespace(
        image_url=None,
        thumbnail_url=None,
        gender=GenderEnum.MALE,
        age_group=AgeGroupEnum.CHILD,
        visual_attributes={"race": "human", "skin_tone": "Pale", "hair_color": "Blonde"},
    )

    assert resolve_dweller_image_urls(dweller) == (
        f"{IMAGE_DIR}/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp",
        f"{THUMBNAIL_DIR}/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp",
    )


def test_elder_variant_locks_grey_hair() -> None:
    image, thumbnail = default_dweller_image_urls("human", "female", None, "Ebony", "black", "elder")

    assert image == f"{IMAGE_DIR}/variants/elder/FOS_Dw_Default_Human_Elder_Female_SkinEbony_HairGray.webp"
    assert thumbnail == (f"{THUMBNAIL_DIR}/variants/elder/FOS_Dw_Default_Human_Elder_Female_SkinEbony_HairGray.webp")


def test_non_human_alt_selection_is_stable() -> None:
    base, base_thumb = default_dweller_image_urls("ghoul", "male", "sane", variation_seed=UUID(int=1))
    alt, alt_thumb = default_dweller_image_urls("ghoul", "male", "sane", variation_seed=UUID(int=6))

    assert base == f"{IMAGE_DIR}/base/FOS_Dw_Default_Ghoul_Male_Sane.webp"
    assert base_thumb == f"{THUMBNAIL_DIR}/base/FOS_Dw_Default_Ghoul_Male_Sane.webp"
    assert alt == f"{IMAGE_DIR}/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp"
    assert alt_thumb == f"{THUMBNAIL_DIR}/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp"
    assert default_dweller_image_urls("ghoul", "male", "sane", variation_seed=UUID(int=6)) == (alt, alt_thumb)


def test_resolve_uses_non_human_alt() -> None:
    from app.core.enums import AgeGroupEnum

    dweller = SimpleNamespace(
        id=UUID(int=6),
        image_url=None,
        thumbnail_url=None,
        gender=GenderEnum.MALE,
        age_group=AgeGroupEnum.ADULT,
        visual_attributes={"race": "ghoul", "state_of_being": "sane"},
    )

    assert resolve_dweller_image_urls(dweller) == (
        f"{IMAGE_DIR}/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp",
        f"{THUMBNAIL_DIR}/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp",
    )


def test_age_defaults_when_skin_and_hair_are_missing() -> None:
    child, _ = default_dweller_image_urls("human", "male", None, None, None, "child")
    elder, _ = default_dweller_image_urls("human", "female", None, None, None, "elder")

    assert child == f"{IMAGE_DIR}/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBrown.webp"
    assert elder == f"{IMAGE_DIR}/variants/elder/FOS_Dw_Default_Human_Elder_Female_SkinPale_HairGray.webp"


def test_age_skin_aliases() -> None:
    child, _ = default_dweller_image_urls("human", "male", None, "Light", "blonde", "child")
    teen, _ = default_dweller_image_urls("human", "female", None, "Dark Brown", "brunette", "teen")

    assert child == f"{IMAGE_DIR}/variants/child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp"
    assert teen == f"{IMAGE_DIR}/variants/teen/FOS_Dw_Default_Human_Teen_Female_SkinBrown_HairBrunette.webp"
