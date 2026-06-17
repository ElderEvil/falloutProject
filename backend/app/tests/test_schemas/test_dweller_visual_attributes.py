"""Tests for the unified DwellerVisualAttributes schema."""

from app.schemas.dweller import DwellerVisualAttributes, DwellerVisualAttributesInput


def test_unified_schema_has_all_fields() -> None:
    """Unified schema should contain both input and AI-generated fields."""
    fields = DwellerVisualAttributes.model_fields

    # Identity fields (from input side)
    assert "race" in fields
    assert "faction" in fields

    # AI-generated fields (from AI output side)
    assert "height" in fields
    assert "appearance" in fields
    assert "clothing_style" in fields
    assert "distinguishing_features" in fields

    # Canonical name fields (renamed from old input names)
    assert "build" in fields  # was body_type in input
    assert "hair_style" in fields  # was haircut in input

    # Common fields
    assert "skin_tone" in fields
    assert "eye_color" in fields
    assert "hair_color" in fields
    assert "facial_hair" in fields
    assert "makeup" in fields

    # Input-only fields
    assert "headgear" in fields
    assert "expression" in fields
    assert "accessory" in fields
    assert "object_held" in fields
    assert "pose" in fields
    assert "background" in fields
    assert "voice_line_text" in fields
    assert "age" in fields
    assert "state_of_being" in fields

    # Count total fields
    assert len(fields) == 22


def test_canonical_field_names() -> None:
    """Old names (haircut, body_type) should NOT be in the schema."""
    fields = DwellerVisualAttributes.model_fields
    assert "haircut" not in fields, "haircut should be renamed to hair_style"
    assert "body_type" not in fields, "body_type should be renamed to build"


def test_all_fields_optional() -> None:
    """All fields should be optional since JSONB stores sparse data."""
    va = DwellerVisualAttributes()
    assert va.model_dump(exclude_none=True) == {}


def test_partial_population() -> None:
    """Should allow partial data (e.g. only race+faction for defaults)."""
    va = DwellerVisualAttributes(race="human", faction="vault_dweller")
    assert va.race == "human"
    assert va.faction == "vault_dweller"
    assert va.height is None


def test_full_population() -> None:
    """All fields should accept values."""
    va = DwellerVisualAttributes(
        race="human",
        faction="brotherhood_of_steel",
        height="tall",
        build="athletic",
        skin_tone="tan",
        eye_color="brown",
        age=30,
        state_of_being=None,
        appearance="attractive",
        hair_style="short",
        hair_color="brown",
        facial_hair="clean-shaven",
        makeup=None,
        expression="determined",
        headgear="Combat Helmet",
        distinguishing_features=["scar"],
        clothing_style="military",
        accessory="Bandolier",
        object_held="Laser Rifle",
        pose="Weapon drawn",
        background="Wasteland Ruins",
        voice_line_text="For the Brotherhood!",
    )
    assert va.race == "human"
    assert va.build == "athletic"
    assert va.hair_style == "short"


def test_age_range() -> None:
    """Age should accept valid range."""
    va = DwellerVisualAttributes(age=30)
    assert va.age == 30

    va = DwellerVisualAttributes(age=None)
    assert va.age is None


def test_backward_compatibility_alias() -> None:
    """DwellerVisualAttributesInput should be an alias of DwellerVisualAttributes."""
    assert DwellerVisualAttributesInput is DwellerVisualAttributes


def test_enum_values_serialize() -> None:
    """Enum values should serialize to their string values."""
    va = DwellerVisualAttributes(race="human", faction="vault_dweller")
    dumped = va.model_dump()
    assert dumped["race"] == "human"
    assert dumped["faction"] == "vault_dweller"
