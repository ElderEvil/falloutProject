"""Curated default portrait URLs for dwellers without a custom image.

Procedurally generated dwellers get a curated static portrait at insert time (the
``Dweller`` ``before_insert`` hook), and data migrations backfill existing rows,
so every read path sees ``image_url``/``thumbnail_url`` without per-schema
fallbacks. Human portraits additionally have skin-tone / hair-color variants
selected for the Barbershop. ``is_default_dweller_image`` distinguishes curated
URLs from custom/generated art so regeneration stays possible.

URLs are relative to the backend ``/static`` mount; the frontend's
``getStaticImageUrl`` resolves them against the API origin.
"""

from __future__ import annotations

from typing import Any

from app.options.races import RaceOption

IMAGE_DIR = "/static/dweller_images"
THUMBNAIL_DIR = "/static/dweller_thumbnails"
VARIANT_SUBDIR = "variants"

HUMAN_PORTRAIT_SKIN_TONES = ("Pale", "Tan", "Brown", "Ebony")
HUMAN_PORTRAIT_HAIR_COLORS = ("Blonde", "Brunette", "Black", "Brown", "Red", "Gray")

_GHOUL_STATES = frozenset({"sane", "wild", "feral"})
_SUPER_MUTANT_STATES = frozenset({"mild", "average", "behemoth"})

_ASSETS: dict[tuple[str, str | None, str | None], str] = {
    ("human", "male", None): "FOS_Dw_Default_Human_Male.webp",
    ("human", "female", None): "FOS_Dw_Default_Human_Female.webp",
    ("ghoul", "male", "sane"): "FOS_Dw_Default_Ghoul_Male_Sane.webp",
    ("ghoul", "male", "wild"): "FOS_Dw_Default_Ghoul_Male_Wild.webp",
    ("ghoul", "male", "feral"): "FOS_Dw_Default_Ghoul_Male_Feral.webp",
    ("ghoul", "female", "sane"): "FOS_Dw_Default_Ghoul_Female_Sane.webp",
    ("ghoul", "female", "wild"): "FOS_Dw_Default_Ghoul_Female_Wild.webp",
    ("ghoul", "female", "feral"): "FOS_Dw_Default_Ghoul_Female_Feral.webp",
    ("super_mutant", "male", "mild"): "FOS_Dw_Default_SuperMutant_Male_Mild.webp",
    ("super_mutant", "male", "average"): "FOS_Dw_Default_SuperMutant_Male_Average.webp",
    ("super_mutant", "male", "behemoth"): "FOS_Dw_Default_SuperMutant_Male_Behemoth.webp",
    ("super_mutant", "female", "mild"): "FOS_Dw_Default_SuperMutant_Female_Mild.webp",
    ("super_mutant", "female", "average"): "FOS_Dw_Default_SuperMutant_Female_Average.webp",
    ("super_mutant", "female", "behemoth"): "FOS_Dw_Default_SuperMutant_Female_Behemoth.webp",
    ("synth", None, "gen_1"): "FOS_Dw_Default_Synth_Gen1.webp",
    ("synth", "male", "gen_2"): "FOS_Dw_Default_Synth_Male_Gen2.webp",
    ("synth", "female", "gen_2"): "FOS_Dw_Default_Synth_Female_Gen2.webp",
    ("synth", "male", "gen_3"): "FOS_Dw_Default_Synth_Male_Gen3.webp",
    ("synth", "female", "gen_3"): "FOS_Dw_Default_Synth_Female_Gen3.webp",
}

_HUMAN_VARIANTS: dict[tuple[str, str, str], str] = {
    (gender, skin.casefold(), hair.casefold()): (f"FOS_Dw_Default_Human_{gender.title()}_Skin{skin}_Hair{hair}.webp")
    for gender in ("male", "female")
    for skin in HUMAN_PORTRAIT_SKIN_TONES
    for hair in HUMAN_PORTRAIT_HAIR_COLORS
}

_RACE_VALUES = frozenset(race.value for race in RaceOption)


def _as_str(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) and raw else None


def _attributes(entity: object) -> tuple[str | None, str | None, str | None, str | None]:
    attrs = getattr(entity, "visual_attributes", None)
    if isinstance(attrs, dict):
        return (
            _as_str(attrs.get("race")),
            _as_str(attrs.get("state_of_being")),
            _as_str(attrs.get("skin_tone")),
            _as_str(attrs.get("hair_color")),
        )
    if attrs is None:
        return None, None, None, None
    return (
        _as_str(getattr(attrs, "race", None)),
        _as_str(getattr(attrs, "state_of_being", None)),
        _as_str(getattr(attrs, "skin_tone", None)),
        _as_str(getattr(attrs, "hair_color", None)),
    )


def _normalize(race: Any, gender: Any, state_of_being: Any) -> tuple[str, str | None, str | None]:
    race_value = (_as_str(race) or "").lower()
    if race_value not in _RACE_VALUES:
        race_value = RaceOption.HUMAN.value

    gender_value = (_as_str(gender) or "").lower()
    if gender_value not in {"male", "female"}:
        gender_value = "male"

    state_value = (_as_str(state_of_being) or "").lower() or None
    if race_value == RaceOption.HUMAN.value:
        state_value = None
    elif race_value == RaceOption.GHOUL.value:
        state_value = state_value if state_value in _GHOUL_STATES else "sane"
    elif race_value == RaceOption.SUPER_MUTANT.value:
        state_value = state_value if state_value in _SUPER_MUTANT_STATES else "average"
    elif race_value == RaceOption.SYNTH.value:
        if state_value == "gen_1":
            gender_value = None
        elif state_value != "gen_2":
            state_value = "gen_3"

    return race_value, gender_value, state_value


def _human_variant(gender: str | None, skin_tone: Any, hair_color: Any) -> str | None:
    gender_value = (_as_str(gender) or "").lower()
    skin_value = (_as_str(skin_tone) or "").strip().casefold()
    hair_value = (_as_str(hair_color) or "").strip().casefold()
    return _HUMAN_VARIANTS.get((gender_value, skin_value, hair_value))


def default_dweller_image_urls(
    race: Any,
    gender: Any,
    state_of_being: Any,
    skin_tone: Any = None,
    hair_color: Any = None,
) -> tuple[str | None, str | None]:
    race_value, gender_value, state_value = _normalize(race, gender, state_of_being)
    if race_value == RaceOption.HUMAN.value:
        variant = _human_variant(gender_value, skin_tone, hair_color)
        if variant is not None:
            return (
                f"{IMAGE_DIR}/{VARIANT_SUBDIR}/{variant}",
                f"{THUMBNAIL_DIR}/{VARIANT_SUBDIR}/{variant}",
            )

    filename = _ASSETS.get((race_value, gender_value, state_value))
    if filename is None:
        return None, None
    return f"{IMAGE_DIR}/{filename}", f"{THUMBNAIL_DIR}/{filename}"


def is_default_dweller_image(url: str | None) -> bool:
    value = _as_str(url)
    return bool(value and value.startswith((f"{IMAGE_DIR}/", f"{THUMBNAIL_DIR}/")))


def resolve_dweller_image_urls(dweller: object) -> tuple[str | None, str | None]:
    image = _as_str(getattr(dweller, "image_url", None))
    thumbnail = _as_str(getattr(dweller, "thumbnail_url", None))
    if image and thumbnail:
        return image, thumbnail
    if image:
        return image, image
    if thumbnail:
        return thumbnail, thumbnail

    race, state_of_being, skin_tone, hair_color = _attributes(dweller)
    return default_dweller_image_urls(
        race,
        getattr(dweller, "gender", None),
        state_of_being,
        skin_tone,
        hair_color,
    )
