"""Preset archetypes for quick character generation.

Each entry carries ``appearance_pools`` (optional per-trait constraint dicts),
``personality_lines`` (3-4 first-person lore-flavoured sentences), and
``weight`` (relative probability when randomising over all entries for a race).

Existing keys, values, and positional structure are preserved so that consumers
such as the AI-visual tests keep working unmodified.
"""

from app.options.factions import FactionOption
from app.options.races import RaceOption

# ---------------------------------------------------------------------------
# Helper to build an appearance_pools dict
# ---------------------------------------------------------------------------


def _pool(*, skin_tone=None, hair_color=None, hair_style=None, build=None, expression=None):
    """Build a appearance_pools dict from keyword arguments."""
    result = {}
    if skin_tone is not None:
        result["skin_tone"] = skin_tone
    if hair_color is not None:
        result["hair_color"] = hair_color
    if hair_style is not None:
        result["hair_style"] = hair_style
    if build is not None:
        result["build"] = build
    if expression is not None:
        result["expression"] = expression
    return result


# ---------------------------------------------------------------------------
# Canonical subsets used for pool definitions
# ---------------------------------------------------------------------------

_HUMAN_SKINS = ["Pale", "Light", "Tan", "Brown", "Dark Brown", "Ebony"]
_HUMAN_BUILD = ["Slim", "Athletic", "Muscular", "Stocky", "Average", "Overweight"]
_GHOUl_SKINS = ["Pale Grey", "Ashen", "Mottled", "Necrotic", "Glowing"]
_GHOUl_BUILD = ["Skeletal", "Withered", "Twisted"]
_MUTANT_SKINS = ["Light Green", "Green", "Dark Green", "Olive Green"]
_MUTANT_BUILD = ["Muscular", "Brutish", "Towering"]
_SYNTH_SKINS = ["Synthetic Fair", "Synthetic Dark", "Metallic Silver", "Exposed Component"]
_SYNTH_BUILD = ["Slender", "Muscular", "Armored"]

_HUMAN_HAIR = [
    "Short Hair",
    "Long Hair",
    "Ponytail",
    "Mohawk",
    "Buzz Cut",
    "Curly Hair",
    "Bun",
    "Braided Hair",
    "Wavy Hair",
    "Dreadlocks",
]
_GHOUl_HAIR = [
    "Patchy Hair",
    "Stringy Hair",
    "Messy Hair",
    "Mohawk",
    "Burned Scalp",
    "Radiation-Scarred",
    "Thinning Hair",
    "Wispy Remains",
]
_MUTANT_HAIR = ["Bald", "Scalp Ridges", "Patchy Tufts", "Mohawk", "Thick Stubble", "War Paint Scalp"]
_SYNTH_HAIR = [
    "Clean Cut",
    "Slicked Back",
    "Military Precision Cut",
    "Exposed Circuits",
    "Synthetic Fiber Weave",
    "Metallic Sheen Hair",
]

_NATURAL_HAIR = ["blonde", "brunette", "black", "brown", "red", "gray"]

# ---------------------------------------------------------------------------
# Archetype presets with default values for quick character creation
# ---------------------------------------------------------------------------

archetypes: dict[str, dict] = {
    "Vault Dweller": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.VAULT_DWELLER,
        "skin_tone": "Fair",
        "build": "Athletic",
        "hair_style": "Ponytail",
        "headgear": "None",
        "outfit": "Blue Vault Suit",
        "weapon": "10mm Pistol",
        "pose": "Standing confidently",
        "background": "Vault Interior",
        "weight": 4,
        "appearance_pools": _pool(
            skin_tone=_HUMAN_SKINS,
            hair_color=_NATURAL_HAIR,
            hair_style=("Short Hair", "Ponytail", "Bun", "Buzz Cut", "Curly Hair"),
            build=("Average", "Athletic", "Slim"),
            expression=("neutral", "smiling", "proud"),
        ),
        "personality_lines": (
            "I was born and raised behind a vault door, and I still flinch at open skies.",
            "I follow schedules, rations, and recycles — the vault way is the only way I know.",
            "I volunteered for the surface because somebody had to, and everyone else looked away.",
        ),
    },
    "Brotherhood Knight": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.BROTHERHOOD_OF_STEEL,
        "skin_tone": "Tan",
        "build": "Muscular",
        "hair_style": "Buzz Cut",
        "headgear": "Combat Helmet",
        "outfit": "Power Armor T-51",
        "weapon": "Laser Rifle",
        "pose": "Power armor stance",
        "background": "Brotherhood Airship",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=_HUMAN_SKINS,
            hair_color=_NATURAL_HAIR,
            hair_style=("Buzz Cut", "Short Hair", "Mohawk"),
            build=("Muscular", "Athletic", "Stocky"),
            expression=("determined", "stoic", "proud"),
        ),
        "personality_lines": (
            "I joined the Brotherhood when I had nothing, and I swore to earn every inch of that armor.",
            "I don't think faith is a weakness — it's the one thing a laser rifle can't replace.",
            "I have seen what happens when technology runs without discipline, and I won't let that happen here.",
        ),
    },
    "Enclave Soldier": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.ENCLAVE,
        "skin_tone": "Fair",
        "build": "Athletic",
        "hair_style": "Buzz Cut",
        "headgear": "Combat Helmet",
        "outfit": "Power Armor X-01",
        "weapon": "Plasma Rifle",
        "pose": "Weapon drawn",
        "background": "Pre-War Suburb",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=_HUMAN_SKINS,
            hair_color=_NATURAL_HAIR,
            hair_style=("Buzz Cut", "Short Hair"),
            build=("Athletic", "Muscular"),
            expression=("determined", "stoic", "proud"),
        ),
        "personality_lines": (
            "I grew up in the Enclave, and they taught me that order is worth any price.",
            "I was told it was purification, but I just followed orders and asked no questions.",
            "I still believe the old world can be rebuilt, even if the ground beneath me burned.",
        ),
    },
    "Raider Warlord": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.RAIDERS,
        "skin_tone": "Tan",
        "build": "Muscular",
        "hair_style": "Mohawk",
        "headgear": "Raider Cage Mask",
        "outfit": "Spike Armor",
        "weapon": "Flamer",
        "pose": "Alert and wary",
        "background": "Wasteland Ruins",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=_HUMAN_SKINS,
            hair_color=None,
            hair_style=("Mohawk", "Buzz Cut", "Short Hair", "Dreadlocks"),
            build=("Muscular", "Stocky"),
            expression=("angry", "mischievous", "determined"),
        ),
        "personality_lines": (
            "I built this gang from nothing, and the only thing I trust is the weight in my hand.",
            "I have learned the hard way that the weak feed the strong — that is the only law that ever stuck.",
            "I don't remember a time before the fire, and maybe that's for the best.",
        ),
    },
    "Super Mutant Brute": {
        "race": RaceOption.SUPER_MUTANT,
        "faction": FactionOption.SUPER_MUTANT_TRIBE,
        "skin_tone": "Green",
        "build": "Brutish",
        "hair_style": "Bald",
        "headgear": "None",
        "outfit": "Super Mutant Harness",
        "weapon": "Super Sledge",
        "pose": "Action shot",
        "background": "Super Mutant Camp",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=_MUTANT_SKINS,
            hair_style=("Bald", "Scalp Ridges", "Mohawk"),
            build=("Muscular", "Brutish", "Towering"),
            expression=("angry", "proud", "stoic"),
        ),
        "personality_lines": (
            "I was grown in a vat, big and strong, and they taught me to hate — hating was easy; forgetting is not.",
            "I let my fists do most of the thinking around here, and they do it well enough.",
            "I was built for war, and now I'm trying to figure out who I am without it.",
        ),
    },
    "Institute Courser": {
        "race": RaceOption.SYNTH,
        "faction": FactionOption.THE_INSTITUTE,
        "skin_tone": "Synthetic Fair",
        "build": "Muscular",
        "hair_style": "Clean Cut",
        "headgear": "None",
        "outfit": "Synth Uniform",
        "weapon": "Institute Laser Pistol",
        "pose": "Stealth crouch",
        "background": "The Institute",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=["Synthetic Fair", "Synthetic Dark"],
            hair_style=("Clean Cut", "Slicked Back", "Military Precision Cut"),
            build=("Slender", "Muscular"),
            expression=("suspicious", "determined", "stoic"),
        ),
        "personality_lines": (
            "I woke up one cycle and decided the Institute didn't own my mind anymore.",
            "I still dream in code, but I've learned to translate it before it wakes me.",
            "I found that freedom feels like a patch update — unexpected, but worth the reboot.",
        ),
    },
    "NCR Ranger": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.NCR,
        "skin_tone": "Brown",
        "build": "Athletic",
        "hair_style": "Short Hair",
        "headgear": "Combat Helmet",
        "outfit": "NCR Ranger Combat Armor",
        "weapon": "Ranger Sequoia",
        "pose": "Weapon drawn",
        "background": "New Vegas Strip",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=["Light", "Tan", "Brown", "Dark Brown"],
            hair_color=_NATURAL_HAIR,
            hair_style=("Short Hair", "Wavy Hair", "Long Hair"),
            build=("Athletic", "Average", "Slim"),
            expression=("determined", "smiling", "stoic"),
        ),
        "personality_lines": (
            "I got my NCR badge from a long road, and I haven't looked back since.",
            "I have seen enough of this land to know that civilization is just a promise you keep.",
            "I carry a rifle and a map, and they've taken me further than most people's prayers ever will.",
        ),
    },
    "Ghoul Mercenary": {
        "race": RaceOption.GHOUL,
        "faction": FactionOption.NONE,
        "skin_tone": "Mottled",
        "build": "Withered",
        "hair_style": "Patchy Hair",
        "headgear": "Scrapped Metal Helmet",
        "outfit": "Combat Armor",
        "weapon": "Hunting Rifle",
        "pose": "Alert and wary",
        "background": "Nuclear Crater",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=_GHOUl_SKINS,
            hair_color=("gray", "white"),
            hair_style=("Patchy Hair", "Stringy Hair", "Thinning Hair", "Wispy Remains"),
            build=("Withered", "Skeletal"),
            expression=("stoic", "suspicious", "determined"),
        ),
        "personality_lines": (
            "I was someone else, somewhere else, before the bombs fell, and the radiation took the rest.",
            "I do mercenary work because it's honest — you pay caps, I keep you breathing, simple.",
            "I found that being ugly has its advantages; people tend to let their guard down around me.",
        ),
    },
    "Children of Atom Zealot": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.CHILDREN_OF_ATOM,
        "skin_tone": "Pale",
        "build": "Slim",
        "hair_style": "Buzz Cut",
        "headgear": "Gas Mask",
        "outfit": "Rags of the Children of Atom",
        "weapon": "Gamma Gun",
        "pose": "Meditating/praying",
        "background": "Nuclear Crater",
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=["Pale", "Light"],
            hair_color=_NATURAL_HAIR,
            hair_style=("Buzz Cut", "Short Hair"),
            build=("Slim", "Average"),
            expression=("stoic", "proud", "determined"),
        ),
        "personality_lines": (
            "I found the Atom showed me the truth — destruction isn't an ending, it's a purification.",
            "I don't fear radiation, I bow to it, because it's the fire that cleanses the weak.",
            "I call my so-called madness the only sanity left in this broken world.",
        ),
    },
    # ------------------------------------------------------------------
    # New random-generation archetypes
    # ------------------------------------------------------------------
    "Wasteland Scavenger": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.NONE,
        "weight": 4,
        "appearance_pools": _pool(
            skin_tone=_HUMAN_SKINS,
            hair_color=None,
            hair_style=("Wavy Hair", "Dreadlocks", "Long Hair", "Buzz Cut"),
            build=("Average", "Stocky", "Overweight"),
            expression=("determined", "stoic", "skeptical"),
        ),
        "personality_lines": (
            "I have learned to read rust like other folk read books, the wastes teaching everything I know.",
            "I won't touch anything that isn't useful or sellable — survival doesn't allow waste.",
            "I once bartered a working Geiger counter for a pair of boots, and that's when I knew I'd truly lived.",
        ),
    },
    "Caravan Trader": {
        "race": RaceOption.HUMAN,
        "faction": FactionOption.NONE,
        "weight": 2,
        "appearance_pools": _pool(
            skin_tone=_HUMAN_SKINS,
            hair_color=None,
            hair_style=("Braided Hair", "Ponytail", "Wavy Hair"),
            build=("Average", "Overweight", "Slim"),
            expression=("smiling", "flirty", "confused"),
        ),
        "personality_lines": (
            "I have traded in everything from pre-war tea to working toasters, and I have never seen a buyer turn down a smile.",
            "I have found that the road taught me most problems come down to negotiation.",
            "I watch caps change hands so fast you almost don't notice — until they don't.",
        ),
    },
    "Old-World Survivor": {
        "race": RaceOption.GHOUL,
        "faction": FactionOption.NONE,
        "weight": 3,
        "appearance_pools": _pool(
            skin_tone=["Pale Grey", "Ashen"],
            hair_color=("gray", "white"),
            hair_style=("Thinning Hair", "Wispy Remains", "Stringy Hair"),
            build=("Withered", "Skeletal"),
            expression=("sad", "stoic", "neutral"),
        ),
        "personality_lines": (
            "I was old when the bombs fell — old enough to remember rain that didn't burn.",
            "I stopped counting years long ago, because time means nothing now.",
            "I have heard people call me a ghoul like it is an insult, but I call it surviving.",
        ),
    },
    "Feral-Scarred Wanderer": {
        "race": RaceOption.GHOUL,
        "faction": FactionOption.NONE,
        "weight": 2,
        "appearance_pools": _pool(
            skin_tone=["Mottled", "Necrotic", "Glowing"],
            hair_style=("Patchy Hair", "Burned Scalp", "Radiation-Scarred"),
            build=("Skeletal", "Twisted", "Withered"),
            expression=("determined", "suspicious", "angry"),
        ),
        "personality_lines": (
            "I carry ash and scars on my skin since the bombs, but I keep my wits sharp to stay what I am.",
            "I have watched the wasteland take my family and the radiation try to take my mind, but it failed so far.",
            "I fight every step of the way — with the land, the mutants, and the fog in my head.",
        ),
    },
    "Gentle Giant": {
        "race": RaceOption.SUPER_MUTANT,
        "faction": FactionOption.SUPER_MUTANT_TRIBE,
        "weight": 2,
        "appearance_pools": _pool(
            skin_tone=["Light Green", "Olive Green"],
            hair_style=("Patchy Tufts", "Thick Stubble", "Bald"),
            build=("Muscular", "Towering"),
            expression=("smiling", "confused", "awkward"),
        ),
        "personality_lines": (
            "I have learned they call me a brute because of my size, but they stop after I help them move a fridge.",
            "I read a lot in the vats, finding books about people like me — soft, kind ones.",
            "I have realized breaking things is easy, but fixing them is harder and worth more.",
        ),
    },
    "Amnesiac Unit": {
        "race": RaceOption.SYNTH,
        "faction": FactionOption.NONE,
        "weight": 2,
        "appearance_pools": _pool(
            skin_tone=["Metallic Silver", "Exposed Component"],
            hair_style=("Exposed Circuits", "Synthetic Fiber Weave", "Metallic Sheen Hair"),
            build=("Slender", "Armored"),
            expression=("confused", "shocked", "stoic"),
        ),
        "personality_lines": (
            "I don't remember who built me, and the Institute sure doesn't either — I've checked.",
            "I catch bits of memory surfacing, and some of them feel like they belong to someone else.",
            "I wake up every morning and decide who I want to be, and it's been working out.",
        ),
    },
}
