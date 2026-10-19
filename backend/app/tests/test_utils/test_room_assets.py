"""Room style artwork lookup."""

from app.utils.room_assets import get_room_image_url


def test_party_style_overrides_supported_rooms() -> None:
    assert get_room_image_url("Diner", tier=1, size=3, style="party") == ("/static/room_images/FOS Diner Party.png")
    assert get_room_image_url("Living room", tier=2, size=6, style="party") == ("/static/room_images/FOS LQ Party.jpg")


def test_party_style_falls_back_to_standard_art_for_unsupported_rooms() -> None:
    assert get_room_image_url("Power Generator", tier=1, size=3, style="party") == get_room_image_url(
        "Power Generator", tier=1, size=3
    )
