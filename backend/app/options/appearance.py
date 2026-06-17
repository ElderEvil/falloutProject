"""Race-specific appearance options for character generation."""

from app.options.races import RaceOption

# Hair styles available per race
haircuts: dict[RaceOption, list[str]] = {
    RaceOption.HUMAN: [
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
    ],
    RaceOption.GHOUL: [
        "Patchy Hair",
        "Stringy Hair",
        "Messy Hair",
        "Mohawk",
        "Burned Scalp",
        "Radiation-Scarred",
        "Thinning Hair",
        "Wispy Remains",
    ],
    RaceOption.SUPER_MUTANT: [
        "Bald",
        "Scalp Ridges",
        "Patchy Tufts",
        "Mohawk",
        "Thick Stubble",
        "War Paint Scalp",
    ],
    RaceOption.SYNTH: [
        "Clean Cut",
        "Slicked Back",
        "Military Precision Cut",
        "Exposed Circuits",
        "Synthetic Fiber Weave",
        "Metallic Sheen Hair",
    ],
}

# Headgear options available per race
headgear_options: dict[RaceOption, list[str]] = {
    RaceOption.HUMAN: [
        "None",
        "Baseball Cap",
        "Bandana",
        "Combat Helmet",
        "Gas Mask",
        "Cowboy Hat",
        "Bowler Hat",
        "Fedora",
        "Ushanka",
        "Beanie",
        "Military Beret",
        "Newsboy Cap",
        "Vault-Tec Helmet",
        "Hooded Coat",
    ],
    RaceOption.GHOUL: [
        "None",
        "Tattered Bandana",
        "Raider Cage Mask",
        "Wrapped Head Bandages",
        "Radiation Suit Hood",
        "Scrapped Metal Helmet",
        "Faded Cap",
        "Glowing One Crown",
        "Leather Hood",
    ],
    RaceOption.SUPER_MUTANT: [
        "None",
        "Metal Helmet",
        "Spiked Helmet",
        "Chain Headdress",
        "Skull Trophy",
        "Heavy Plate Helmet",
        "Makeshift Face Guard",
        "Mutant Battle Helm",
    ],
    RaceOption.SYNTH: [
        "None",
        "Institute Hood",
        "Metallic Plating",
        "Stealth Field Generator",
        "Neural Interface Helmet",
        "Courser Hood",
        "Synth Component Display",
        "Reinforced Circuitry Cap",
    ],
}

# Which headgear fully covers the head (hides hair)
fully_covering_headgear: set[str] = {
    "Combat Helmet",
    "Gas Mask",
    "Hooded Coat",
    "Wrapped Head Bandages",
    "Radiation Suit Hood",
    "Scrapped Metal Helmet",
    "Metal Helmet",
    "Spiked Helmet",
    "Heavy Plate Helmet",
    "Institute Hood",
    "Metallic Plating",
    "Neural Interface Helmet",
    "Courser Hood",
}

# Facial hair options
beard_options: list[str] = [
    "None",
    "Light Stubble",
    "Goatee",
    "Moustache",
    "Full Beard",
]

# Skin tone options available per race
skin_tone_options: dict[RaceOption, list[str]] = {
    RaceOption.HUMAN: [
        "Pale",
        "Light",
        "Tan",
        "Brown",
        "Dark Brown",
        "Ebony",
    ],
    RaceOption.GHOUL: [
        "Pale Grey",
        "Ashen",
        "Mottled",
        "Necrotic",
        "Glowing",
    ],
    RaceOption.SUPER_MUTANT: [
        "Light Green",
        "Green",
        "Dark Green",
        "Olive Green",
    ],
    RaceOption.SYNTH: [
        "Synthetic Fair",
        "Synthetic Dark",
        "Metallic Silver",
        "Exposed Component",
    ],
}

# Body type options available per race
body_type_options: dict[RaceOption, list[str]] = {
    RaceOption.HUMAN: [
        "Slim",
        "Athletic",
        "Muscular",
        "Stocky",
        "Average",
        "Overweight",
    ],
    RaceOption.GHOUL: [
        "Skeletal",
        "Withered",
        "Twisted",
    ],
    RaceOption.SUPER_MUTANT: [
        "Muscular",
        "Brutish",
        "Towering",
    ],
    RaceOption.SYNTH: [
        "Slender",
        "Muscular",
        "Armored",
    ],
}

# Expression options with display labels
expression_options: dict[str, str] = {
    "neutral": "with a calm, neutral expression, showing no strong emotions",
    "smiling": "with a warm, friendly smile, radiating positivity",
    "laughing": "laughing heartily, eyes squinting with joy",
    "proud": "standing confidently, exuding self-assurance and pride",
    "sad": "with a melancholic expression, eyes slightly downcast",
    "angry": "with a furious glare, jaw clenched in anger",
    "frustrated": "visibly frustrated, brows furrowed and lips pressed tightly",
    "shocked": "with wide eyes and an open mouth, frozen in shock",
    "terrified": "trembling, eyes wide with fear and panic",
    "determined": "with a firm, resolute look, ready to face any challenge",
    "heroic": "standing tall, gaze sharp, radiating bravery and heroism",
    "stoic": "with a stone-cold, unreadable expression, unmoved by surroundings",
    "skeptical": "raising an eyebrow, lips pressed in skepticism",
    "suspicious": "narrowing eyes slightly, expression filled with doubt",
    "confused": "with a puzzled look, eyebrows raised in uncertainty",
    "awkward": "with a forced, uneasy smile, avoiding eye contact",
    "mischievous": "grinning slyly, eyes gleaming with playful intent",
    "flirty": "with a coy smile, eyes glimmering with playful charm",
}
