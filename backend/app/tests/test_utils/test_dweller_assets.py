from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.core.enums import (
    AgeGroupEnum,
    GenderEnum,
    GhoulFeralnessEnum,
    RaceEnum,
    SuperMutantMutationEnum,
    SynthTypeEnum,
)
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
    (RaceEnum.GHOUL, GenderEnum.FEMALE, GhoulFeralnessEnum.WILD, "FOS_Dw_Default_Ghoul_Female_Wild.webp"),
    (
        RaceEnum.SUPER_MUTANT,
        GenderEnum.MALE,
        SuperMutantMutationEnum.BEHEMOTH,
        "FOS_Dw_Default_SuperMutant_Male_Behemoth.webp",
    ),
    (RaceEnum.SYNTH, GenderEnum.MALE, SynthTypeEnum.GEN_1, "FOS_Dw_Default_Synth_Gen1.webp"),
]
FALLBACKS = [
    (None, "female", None, "FOS_Dw_Default_Human_Female.webp"),
    ("vault_dweller", "male", None, "FOS_Dw_Default_Human_Male.webp"),
    ("ghoul", "male", None, "FOS_Dw_Default_Ghoul_Male_Sane.webp"),
    ("ghoul", "male", "not-a-state", "FOS_Dw_Default_Ghoul_Male_Sane.webp"),
    ("super_mutant", "female", None, "FOS_Dw_Default_SuperMutant_Female_Average.webp"),
    ("super_mutant", "female", "not-a-state", "FOS_Dw_Default_SuperMutant_Female_Average.webp"),
    ("synth", "male", None, "FOS_Dw_Default_Synth_Male_Gen3.webp"),
    ("synth", "female", "not-a-state", "FOS_Dw_Default_Synth_Female_Gen3.webp"),
    ("HUMAN", "FEMALE", None, "FOS_Dw_Default_Human_Female.webp"),
    ("GHOUL", "MALE", "WILD", "FOS_Dw_Default_Ghoul_Male_Wild.webp"),
    ("SUPER_MUTANT", "FEMALE", "BEHEMOTH", "FOS_Dw_Default_SuperMutant_Female_Behemoth.webp"),
]
DEFAULT_RESOLVES = [
    (
        GenderEnum.FEMALE,
        {"race": "super_mutant", "state_of_being": "mild"},
        None,
        None,
        "base",
        "FOS_Dw_Default_SuperMutant_Female_Mild.webp",
    ),
    (
        GenderEnum.MALE,
        SimpleNamespace(race=RaceEnum.SYNTH, state_of_being=SynthTypeEnum.GEN_1),
        None,
        None,
        "base",
        "FOS_Dw_Default_Synth_Gen1.webp",
    ),
    (
        GenderEnum.FEMALE,
        {"race": "human", "skin_tone": "Tan", "hair_color": "red"},
        None,
        None,
        "variants/adult",
        "FOS_Dw_Default_Human_Female_SkinTan_HairRed.webp",
    ),
    (
        GenderEnum.MALE,
        {"race": "human", "skin_tone": "Pale", "hair_color": "Blonde"},
        AgeGroupEnum.CHILD,
        None,
        "variants/child",
        "FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp",
    ),
    (
        GenderEnum.MALE,
        {"race": "ghoul", "state_of_being": "sane"},
        AgeGroupEnum.ADULT,
        UUID(int=6),
        "variants/non_human/ghoul",
        "FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp",
    ),
]


@pytest.mark.parametrize(("race", "gender", "state", "filename"), MATRIX)
def test_default_matrix(race, gender, state, filename: str) -> None:
    image, thumbnail = default_dweller_image_urls(race, gender, state)
    assert image == f"{IMAGE_DIR}/base/{filename}"
    assert thumbnail == f"{THUMBNAIL_DIR}/base/{filename}"
    assert (STATIC_ROOT / image.removeprefix("/static/")).is_file()
    assert (STATIC_ROOT / thumbnail.removeprefix("/static/")).is_file()
    male = default_dweller_image_urls("synth", "male", "gen_1")
    assert male == default_dweller_image_urls("synth", "female", "gen_1")
    assert male[0] == f"{IMAGE_DIR}/base/FOS_Dw_Default_Synth_Gen1.webp"


@pytest.mark.parametrize(("race", "gender", "state", "expected"), FALLBACKS)
def test_fallbacks_and_uppercase_values(race, gender: str, state, expected: str) -> None:
    assert default_dweller_image_urls(race, gender, state)[0] == f"{IMAGE_DIR}/base/{expected}"


@pytest.mark.parametrize(
    ("image_url", "thumbnail_url", "expected"),
    [
        (
            "https://example.test/custom.png",
            "https://example.test/custom-thumb.png",
            ("https://example.test/custom.png", "https://example.test/custom-thumb.png"),
        ),
        (
            "https://example.test/custom.png",
            None,
            ("https://example.test/custom.png", "https://example.test/custom.png"),
        ),
        (
            None,
            "https://example.test/custom-thumb.png",
            ("https://example.test/custom-thumb.png", "https://example.test/custom-thumb.png"),
        ),
    ],
)
def test_resolve_preserves_and_fills_custom_urls(image_url, thumbnail_url, expected: tuple) -> None:
    dweller = SimpleNamespace(
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        gender=GenderEnum.MALE,
        visual_attributes={"race": "ghoul", "state_of_being": "feral"},
    )
    assert resolve_dweller_image_urls(dweller) == expected


@pytest.mark.parametrize(("gender", "attrs", "age", "uid", "folder", "filename"), DEFAULT_RESOLVES)
def test_resolve_falls_back_to_defaults(gender, attrs, age, uid, folder: str, filename: str) -> None:
    namespace = {"image_url": None, "thumbnail_url": None, "gender": gender, "visual_attributes": attrs}
    if age is not None:
        namespace["age_group"] = age
    if uid is not None:
        namespace["id"] = uid
    assert resolve_dweller_image_urls(SimpleNamespace(**namespace)) == (
        f"{IMAGE_DIR}/{folder}/{filename}",
        f"{THUMBNAIL_DIR}/{folder}/{filename}",
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
    ("race", "gender", "state", "skin", "hair", "base"),
    [
        ("human", "male", None, "Light", "blonde", "FOS_Dw_Default_Human_Male.webp"),
        ("human", "male", None, "Pale", "white", "FOS_Dw_Default_Human_Male.webp"),
        ("human", "male", None, "Dark Brown", "blue", "FOS_Dw_Default_Human_Male.webp"),
        ("ghoul", "male", "wild", "Ebony", "red", "FOS_Dw_Default_Ghoul_Male_Wild.webp"),
    ],
)
def test_unsupported_colors_fall_back_to_base(race, gender, state, skin, hair, base: str) -> None:
    assert default_dweller_image_urls(race, gender, state, skin, hair)[0] == f"{IMAGE_DIR}/base/{base}"


@pytest.mark.parametrize(
    ("gender", "skin", "hair", "age", "filename"),
    [
        ("male", "Ebony", "black", "child", "FOS_Dw_Default_Human_Child_Male_SkinEbony_HairBlack.webp"),
        ("female", "Pale", "red", "teen", "FOS_Dw_Default_Human_Teen_Female_SkinPale_HairRed.webp"),
        ("female", "Tan", "gray", "child", "FOS_Dw_Default_Human_Child_Female_SkinTan_HairBrown.webp"),
        ("male", "Brown", "gray", "teen", "FOS_Dw_Default_Human_Teen_Male_SkinBrown_HairBrown.webp"),
        ("female", "Ebony", "black", "teen", "FOS_Dw_Default_Human_Teen_Female_SkinEbony_HairBlack.webp"),
        ("female", "Ebony", "black", "elder", "FOS_Dw_Default_Human_Elder_Female_SkinEbony_HairGray.webp"),
        ("male", None, None, "child", "FOS_Dw_Default_Human_Child_Male_SkinPale_HairBrown.webp"),
        ("female", None, None, "elder", "FOS_Dw_Default_Human_Elder_Female_SkinPale_HairGray.webp"),
        ("male", "Light", "blonde", "child", "FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp"),
        ("female", "Dark Brown", "brunette", "teen", "FOS_Dw_Default_Human_Teen_Female_SkinBrown_HairBrunette.webp"),
    ],
)
def test_human_age_variants(gender: str, skin: str | None, hair: str | None, age: str, filename: str) -> None:
    image, thumbnail = default_dweller_image_urls("human", gender, None, skin, hair, age)
    assert image == f"{IMAGE_DIR}/variants/{age}/{filename}"
    assert thumbnail == f"{THUMBNAIL_DIR}/variants/{age}/{filename}"
    for url, expected in [
        (f"{IMAGE_DIR}/base/FOS_Dw_Default_Human_Male.webp", True),
        (f"{THUMBNAIL_DIR}/base/FOS_Dw_Default_Human_Male.webp", True),
        ("https://example.test/custom.png", False),
        ("/static/legendary_dweller_images/FOS_Dw_Butch.png", False),
        (None, False),
        ("", False),
    ]:
        assert is_default_dweller_image(url) is expected
    base, base_thumb = default_dweller_image_urls("ghoul", "male", "sane", variation_seed=UUID(int=1))
    alt, alt_thumb = default_dweller_image_urls("ghoul", "male", "sane", variation_seed=UUID(int=6))
    assert base == f"{IMAGE_DIR}/base/FOS_Dw_Default_Ghoul_Male_Sane.webp"
    assert base_thumb == f"{THUMBNAIL_DIR}/base/FOS_Dw_Default_Ghoul_Male_Sane.webp"
    assert alt == f"{IMAGE_DIR}/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp"
    assert alt_thumb == f"{THUMBNAIL_DIR}/variants/non_human/ghoul/FOS_Dw_Default_Ghoul_Male_Sane_Alt.webp"
    assert default_dweller_image_urls("ghoul", "male", "sane", variation_seed=UUID(int=6)) == (alt, alt_thumb)
