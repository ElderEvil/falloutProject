"""Race- and faction-specific equipment options for character generation."""

from app.options.factions import FactionOption

# Common equipment available to all factions
common_equipment: dict[str, list[str]] = {
    "outfits": [
        "Casual Wastelander Clothes",
        "Scavenger Gear",
        "Tattered Field Jacket",
    ],
    "weapons": [
        "None",
        "10mm Pistol",
        "Pipe Pistol",
        "Hunting Rifle",
    ],
    "accessories": [
        "None",
        "Goggles (worn on forehead)",
        "Gloves (fingerless leather)",
        "Bandolier (slung across chest)",
    ],
    "objects": [
        "None",
        "Stimpak (ready to inject)",
        "Bottlecap Pouch (jingling softly)",
    ],
}

# Faction-specific equipment additions
faction_equipment: dict[FactionOption, dict[str, list[str]]] = {
    FactionOption.VAULT_DWELLER: {
        "outfits": [
            "Blue Vault Suit",
            "Vault Security Armor",
        ],
        "weapons": [
            "10mm Pistol",
            ".44 Magnum",
            "Security Baton",
        ],
        "accessories": [
            "Vault-Tec Badge (pinned on outfit)",
            "Pip-Boy (glowing screen)",
        ],
        "objects": [
            "Pip-Boy (glowing screen)",
            "Holotape (examining closely)",
        ],
    },
    FactionOption.BROTHERHOOD_OF_STEEL: {
        "outfits": [
            "Brotherhood Combat Armor",
            "Power Armor T-51",
            "Combat Armor",
        ],
        "weapons": [
            "Laser Rifle",
            "Gatling Laser",
            "Power Fist",
            "Gauss Rifle",
        ],
        "accessories": [
            "Faction Insignia (etched on armor)",
            "Shoulder Pads (metal salvaged)",
        ],
        "objects": [
            "Fusion Core (faint glow)",
            "Holotape (examining closely)",
        ],
    },
    FactionOption.ENCLAVE: {
        "outfits": [
            "Settler Outfit",
            "Casual Wastelander Clothes",
            "Power Armor X-01",
            "Combat Armor",
        ],
        "weapons": [
            "Plasma Rifle",
            "Baseball Bat",
            "Deathclaw Gauntlet",
            "Ripper",
        ],
        "accessories": [],
        "objects": [],
    },
    FactionOption.RAIDERS: {
        "outfits": [
            "Raider Leathers",
            "Spike Armor",
            "Metal Armor",
        ],
        "weapons": [
            "Pipe Rifle",
            "Board with Nails",
            "Pipe Pistol",
            "Flamer",
        ],
        "accessories": [
            "War Paint (tribal markings on face or arms)",
            "Scar (deep, battle-worn)",
        ],
        "objects": [
            "Nuka-Cola Bottle (condensation forming)",
        ],
    },
    FactionOption.SUPER_MUTANT_TRIBE: {
        "outfits": [
            "Super Mutant Harness",
            "Super Mutant Cages",
            "Super Mutant Armor",
        ],
        "weapons": [
            "Super Sledge",
            "Board with Nails",
            "Pipe Rifle",
            "Minigun",
        ],
        "accessories": [
            "Bone Necklace (tribal decoration)",
            "Scarred War Paint (intimidating design)",
        ],
        "objects": [
            "Meat Bag (intact and reeking)",
            "Fusion Core (loot from scavenging)",
        ],
    },
    FactionOption.CHILDREN_OF_ATOM: {
        "outfits": [
            "Rags of the Children of Atom",
            "Glowing robes",
        ],
        "weapons": [
            "Gamma Gun",
            "Wrench",
        ],
        "accessories": [
            "Radiation-Resistant Mask",
            "Glowing Tattoo",
        ],
        "objects": [
            "Glowing Mushroom",
        ],
    },
    FactionOption.THE_INSTITUTE: {
        "outfits": [
            "Synth Uniform",
            "Institute Lab Coat",
            "Clean Jumpsuit",
        ],
        "weapons": [
            "Institute Laser Pistol",
            "Plasma Rifle",
            "Synth Melee Weapon",
        ],
        "accessories": [
            "Cybernetic Implant (glowing eye, exposed wiring)",
            "Synth Component",
        ],
        "objects": [
            "Holotape (examining closely)",
            "Institute Schematic",
        ],
    },
    FactionOption.RAILROAD: {
        "outfits": [
            "Railroad Armored Coat",
            "Disguise (various)",
            "Wastelander Clothing",
        ],
        "weapons": [
            "Silenced Pistol",
            "Combat Knife",
            "Deliverer",
        ],
        "accessories": [
            "Railroad Symbol",
            "Concealed Radio",
        ],
        "objects": [
            "Encrypted Message",
        ],
    },
    FactionOption.NCR: {
        "outfits": [
            "NCR Ranger Combat Armor",
            "NCR Trooper Uniform",
            "NCR Officer Uniform",
        ],
        "weapons": [
            "Service Rifle",
            "Ranger Sequoia",
            "Anti-Material Rifle",
        ],
        "accessories": [
            "NCR Flag Patch",
            "NCR Dog Tags",
        ],
        "objects": [
            "NCR Veteran's Duster",
        ],
    },
    FactionOption.CAESARS_LEGION: {
        "outfits": [
            "Legionary Armor",
            "Centurion Armor",
            "Praetorian Armor",
        ],
        "weapons": [
            "Machete",
            "Throwing Spears",
            "Chainsaw",
        ],
        "accessories": [
            "Caesar's Legion Branding",
            "Bear Pelt",
        ],
        "objects": [
            "Legion Denarius",
        ],
    },
    FactionOption.NONE: {
        "outfits": [],
        "weapons": [],
        "accessories": [],
        "objects": [],
    },
}
