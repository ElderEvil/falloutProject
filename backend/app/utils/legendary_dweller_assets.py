"""Legendary dweller image URL resolution."""

from pathlib import Path

LEGENDARY_DWELLER_IMAGE_FILES = {
    "abraham washington": "FOS_Dw_Abraham_Washington.png",
    "allistair tenpenny": "FOS_Dw_Allistair_Tenpenny.png",
    "amata": "FOS_Dw_Amata.png",
    "augustus autumn": "FOS_Dw_Augustus_Autumn.png",
    "bittercup": "FOS_Dw_Bittercup.png",
    "butch": "FOS_Dw_Butch.png",
    "confessor cromwell": "FOS_Dw_Confessor_Cromwell.png",
    "eulogy jones": "FOS_Dw_Eulogy_Jones.png",
    "harkness": "FOS_Dw_Harkness.png",
    "james": "FOS_Dw_James.png",
    "jericho": "FOS_Dw_Jericho.png",
    "lucas simms": "FOS_Dw_Lucas_Simms.png",
    "madison li": "FOS_Dw_Madison_Li.png",
    "owyn lyons": "FOS_Dw_Owyn_Lyons.png",
    "preston garvey": "FOS_Dw_Preston_Garvey.png",
    "scribe rothchild": "FOS_Dw_Scribe_Rothchild.png",
    "three dog": "FOS_Dw_Three_Dog.png",
}

_IMAGE_DIR = Path(__file__).parent.parent / "static" / "legendary_dweller_images"
_FALLBACK_IMAGE_FILE = "FOS_Dw_Legendary_Red.png"


def get_legendary_dweller_image_url(name: str | None) -> str | None:
    """Return a legendary dweller portrait, with a generic legendary fallback."""
    filename = LEGENDARY_DWELLER_IMAGE_FILES.get(name.strip().casefold()) if name else None
    filename = filename or _FALLBACK_IMAGE_FILE
    return f"/static/legendary_dweller_images/{filename}" if (_IMAGE_DIR / filename).exists() else None
