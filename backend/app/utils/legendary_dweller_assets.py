"""Legendary dweller image URL resolution."""

from pathlib import Path

from app.core.enums import AssetRole
from app.utils.asset_manifest import manifest_url

LEGENDARY_DWELLER_IMAGE_FILES = {
    "76 overseer": "FOS_Dw_76_Overseer.png",
    "abraham washington": "FOS_Dw_Abraham_Washington.png",
    "allistair tenpenny": "FOS_Dw_Allistair_Tenpenny.png",
    "amata": "FOS_Dw_Amata.png",
    "augustus autumn": "FOS_Dw_Augustus_Autumn.png",
    "betty": "FOS_Dw_Betty.png",
    "bittercup": "FOS_Dw_Bittercup.png",
    "butch": "FOS_Dw_Butch.png",
    "chet": "FOS_Dw_Chet.png",
    "colonel autumn": "FOS_Dw_Augustus_Autumn.png",
    "confessor cromwell": "FOS_Dw_Confessor_Cromwell.png",
    "conrad kellogg": "FOS_Dw_Conrad_Kellogg.png",
    "cooper howard": "FOS_Dw_Cooper_Howard.png",
    "desdemona": "FOS_Dw_Desdemona.png",
    "dr. henry": "FOS_Dw_Dr_Henry.png",
    "dr. li": "FOS_Dw_Madison_Li.png",
    "ed the ghoul": "FOS_Dw_Ed_the_Ghoul.png",
    "elder lyons": "FOS_Dw_Owyn_Lyons.png",
    "eulogy jones": "FOS_Dw_Eulogy_Jones.png",
    "hank": "FOS_Dw_Hank.png",
    "harkness": "FOS_Dw_Harkness.png",
    "james": "FOS_Dw_James.png",
    "jericho": "FOS_Dw_Jericho.png",
    "legate": "FOS_Dw_Legate.png",
    "luc the human": "FOS_Dw_Luc_the_Human.png",
    "lucas simms": "FOS_Dw_Lucas_Simms.png",
    "lucy maclean": "FOS_Dw_Lucy_MacLean.png",
    "ma june": "FOS_Dw_Ma_June.png",
    "madison li": "FOS_Dw_Madison_Li.png",
    "maximus": "FOS_Dw_Maximus.png",
    "moira brown": "FOS_Dw_Moira_Brown.png",
    "moldaver": "FOS_Dw_Moldaver.png",
    "mr. burke": "FOS_Dw_Mr_Burke.png",
    "mr. house": "FOS_Dw_Mr_House.png",
    "nick valentine": "FOS_Dw_Nick_Valentine.png",
    "norm": "FOS_Dw_Norm.png",
    "old longfellow": "FOS_Dw_Old_Longfellow.png",
    "owyn lyons": "FOS_Dw_Owyn_Lyons.png",
    "paladin": "FOS_Dw_Paladin.png",
    "paladin danse": "FOS_Dw_Paladin_Danse.png",
    "piper": "FOS_Dw_Piper.png",
    "preston garvey": "FOS_Dw_Preston_Garvey.png",
    "regs": "FOS_Dw_Regs.png",
    "sarah lyons": "FOS_Dw_Sarah_Lyons.png",
    "scribe rothchild": "FOS_Dw_Scribe_Rothchild.png",
    "scribe valdez": "FOS_Dw_Scribe_Valdez.png",
    "snake oil salesman": "FOS_Dw_Snake_Oil_Salesman.png",
    "snip snip": "FOS_Dw_Snip_Snip.png",
    "star paladin cross": "FOS_Dw_Star_Paladin_Cross.png",
    "stephanie": "FOS_Dw_Stephanie.png",
    "the ghoul": "FOS_Dw_The_Ghoul.png",
    "three dog": "FOS_Dw_Three_Dog.png",
    "wilzig": "FOS_Dw_Wilzig.png",
}

_IMAGE_DIR = Path(__file__).parent.parent / "static" / "legendary_dweller_images"
_FALLBACK_IMAGE_FILE = "FOS_Dw_Legendary_Red.png"


def get_legendary_dweller_image_url(name: str | None) -> str | None:
    """Return a legendary dweller portrait, with a generic legendary fallback."""
    if name and (url := manifest_url(AssetRole.DWELLER_PORTRAIT, name)):
        return url

    filename = LEGENDARY_DWELLER_IMAGE_FILES.get(name.strip().casefold()) if name else None
    filename = filename or _FALLBACK_IMAGE_FILE
    return f"/static/legendary_dweller_images/{filename}" if (_IMAGE_DIR / filename).exists() else None
