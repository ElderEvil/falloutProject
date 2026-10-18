"""Lore-safe bio templates and rumors; rendering lives in app.utils.bios.

Origins and visited places remain world-map registrable. Race-specific templates
frame the shared origin pool as a birthplace, last-known site, or wake-site.
"""

from app.core.enums import RaceEnum

NEWBORN_BIO_TEMPLATES = (
    "Born during a {event}. {mother} and {father} couldn't be prouder.",
    "Arrived during {event}. The vault celebrates this new life.",
    "Entered the world during {event}. A blessing for {mother} and {father}.",
    "Born under {event}. {father} and {mother} welcome their bundle of joy.",
    "Came into existence during {event}. A new hope for the vault.",
    "Born during {event}. {mother} and {father} are overjoyed.",
    "First cry echoed through the vault during {event}. Precious to {mother} and {father}.",
    "Entered the shelter during {event}. {father} and {mother} celebrate.",
    "Born amidst {event}. A miracle for {mother} and {father}.",
    "Came from {mother} and {father} during {event}. The vault grows.",
)

NEWBORN_EVENTS = (
    "a quiet night",
    "a vault celebration",
    "a rad-storm",
    "an emergency drill",
    "a power outage",
    "the weekly ration distribution",
    "a radio broadcast",
    "the morning shift change",
    "a rare sunny day",
    "the lunch hour",
    "the night watch",
    "a calm afternoon",
    "the vault door sealing",
    "a happiness surge",
    "the quarterly inventory",
)

RACE_VISITED_TEMPLATES: dict[RaceEnum, tuple[str, ...]] = {
    RaceEnum.GHOUL: (
        "I was someone else, somewhere else, before the bombs fell. The vault found me near {origin} — I'd come through {visited}.",
    ),
    RaceEnum.SYNTH: ("I was not born. I woke up in a lab under {origin}, and I ran. {visited} saw me pass.",),
    RaceEnum.SUPER_MUTANT: (
        "I was human once. The vats took that, and most of my memories with it. Last I knew: {origin}. Before that, {visited}.",
    ),
}

RACE_BARE_TEMPLATES: dict[RaceEnum, str] = {
    RaceEnum.GHOUL: "I was someone else, somewhere else, before the bombs fell. The vault found me near {origin}. I'd stopped counting the years long before that.",
    RaceEnum.SYNTH: "I was not born. I woke up in a lab under {origin}, and I ran. I haven't stopped since.",
    RaceEnum.SUPER_MUTANT: "I was human once. The vats took that, and most of my memories with it. Last I knew: {origin}.",
}

ZONE_RUMORS: tuple[str, ...] = (
    (
        "I've heard the scavengers talk about the Quiet Zone, a fenced industrial site where the air "
        "supposedly bends after a radstorm. The engineers say the scavengers drink too much."
    ),
    "A surface volunteer showed me a sealed polishing cloth. He said opening it voided his exterior clearance; his sister said it was only a cleaning kit.",
    "I've heard the Department of Exterior Continuity keeps two current editions of its Compact. Each edition calls the other a forgery.",
    "A mechanic swears Department-Issue Heat Tape outlasted its cheaper replacement. Her supervisor says the old stock never met specification.",
    "I carry a pouch of rusty bolts for testing bad ground. I've never needed them, which proves nothing.",
    (
        "A scout I knew swore she saw a fireball hovering over the Quiet Zone. Her old caravan partner "
        "says it was a gas leak and three bottles of vodka."
    ),
    "I keep a map with one spot crossed out and rewritten: DON'T GO BACK. Nobody will tell me what's there.",
    (
        "They say some ruins near the old exclusion fence grow valuables the way forests grow mushrooms. "
        "I've only found scrap so far."
    ),
    (
        "A masked guide led me through a fence line once, then vanished before I could pay. The rest of "
        "the party says I imagined him."
    ),
    (
        "My detector clicks near radiation, loose wiring, and occasionally nothing at all. It's useless. "
        "I trust it anyway."
    ),
    (
        "My cousin sold a warm stone from past the perimeter for two hundred caps. His buyer argued about "
        "the price for three days."
    ),
)
