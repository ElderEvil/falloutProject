"""Resolve a dweller's equipped pet into one set of mechanical modifiers.

The single reader for pet mechanics: combat, production, radiation, happiness,
caps, XP and training resolution all ask this module instead of branching on
pet names themselves. Pure and session-free, so game-loop actors and API paths
share the same rules. Effects are catalog-resolved by pet name — the ``Pet``
model carries no effect columns, so unlisted pets are neutral pending balance
tuning.
"""

from dataclasses import dataclass

from app.utils.equipped import equipped_pet

#: Damage bonus cap: ``1 + faction + pet`` must not exceed this (pets plan §5.3).
MAX_DAMAGE_PCT_BONUS = 2.0
#: Resist cap for multiplicative-complement resists (pets plan §5.3).
MAX_RESIST_PCT = 0.95
#: Cap for additive happiness/caps/XP/training percentage bonuses (pets plan §5.3).
MAX_PCT_BONUS = 0.5


@dataclass(frozen=True)
class PetEffect:
    """Mechanical bonuses granted by one pet.

    SPECIAL and ``max_health`` are additive integers; the percentage fields are
    additive fractions (``0.25`` = +25%) and are capped by the module constants
    at the application points.
    """

    strength: int = 0
    perception: int = 0
    endurance: int = 0
    charisma: int = 0
    intelligence: int = 0
    agility: int = 0
    luck: int = 0
    max_health: int = 0
    damage_pct: float = 0.0
    incident_response_pct: float = 0.0
    radiation_resist_pct: float = 0.0
    happiness: float = 0.0
    caps_pct: float = 0.0
    xp_pct: float = 0.0
    training_speed_pct: float = 0.0
    twin_chance_pct: float = 0.0


#: The no-bonus effect returned for unlisted pets.
NEUTRAL_EFFECT = PetEffect()

#: Name-keyed catalog, keyed by the same ``.strip().casefold()`` names as
#: ``PET_NAME_TO_IMAGE_FILE`` so art and effects stay aligned. Seeded so every
#: effect field is covered at least once; extend by adding a line per pet.
PET_EFFECT_BY_NAME: dict[str, PetEffect] = {
    "dogmeat (fallout 4)": PetEffect(strength=2, max_health=20, damage_pct=0.25),
    "baby deathclaw": PetEffect(damage_pct=0.35, incident_response_pct=0.25),
    "yao guai cub": PetEffect(damage_pct=0.25, max_health=25),
    "cx404": PetEffect(luck=2, caps_pct=0.25, xp_pct=0.25),
    "vault-tec parrot": PetEffect(intelligence=2, training_speed_pct=0.25),
    "mr. pebbles": PetEffect(charisma=2, happiness=0.25),
    "pallas's cat": PetEffect(perception=2, incident_response_pct=0.25),
    "st. bernard": PetEffect(endurance=2, max_health=30, radiation_resist_pct=0.25),
    "husky": PetEffect(agility=2, damage_pct=0.25),
    "abyssinian": PetEffect(intelligence=1, xp_pct=0.25),
    "genius": PetEffect(twin_chance_pct=0.25),
    "stubbs": PetEffect(twin_chance_pct=0.50),
    "shakespeare": PetEffect(twin_chance_pct=0.75),
    "lucky": PetEffect(twin_chance_pct=0.50),
    "pongo": PetEffect(twin_chance_pct=0.75),
}


def pet_effect_for_name(name: str | None) -> PetEffect:
    """The catalog effect for a pet name, or neutral for None/blank/unknown.

    Names are normalized with ``.strip().casefold()`` to match the art map's
    keys; anything not in the catalog resolves to ``NEUTRAL_EFFECT``.
    """
    if not name:
        return NEUTRAL_EFFECT
    return PET_EFFECT_BY_NAME.get(name.strip().casefold(), NEUTRAL_EFFECT)


#: Name-keyed flavor text, keyed like ``PET_EFFECT_BY_NAME``. Covers every
#: art-mapped pet, sorted alphabetically by key.
PET_DESCRIPTION_BY_NAME: dict[str, str] = {
    "abyssinian": "A clever cat that learns as quickly as its keeper.",
    "akita": "A big, quiet guardian that takes its post at the vault door.",
    "alien drone": "A hovering scout that whirs softly and watches everything.",
    "american shorthair": "A steady, easygoing mouser that settles in anywhere.",
    "apolda": "A sleek, alert Doberman that never misses a stranger at the gate.",
    "ashes": "A calm, round-faced cat that naps through every alarm.",
    "australian shepherd": "A tireless herder that rounds up dwellers and loose gear alike.",
    "baby deathclaw": "A pint-size deathclaw with a fierce streak and a taste for incident alarms.",
    "bandit (dog)": "A shaggy opportunist that steals snacks and hearts in equal measure.",
    "bangor": "A giant fluffy cat that rules the room it walks into.",
    "barry": "A gentle giant bred to dig survivors out of the rubble.",
    "bastet": "A hairless charmer that radiates warmth from every sunbeam.",
    "belgian malinois": "A sharp working dog that lives for the next command.",
    "bigsby": "A faithful herding dog that keeps every dweller in line.",
    "black lab": "A friendly retriever that fetches whatever the wasteland drops.",
    "bloodhound": "A relentless tracker that follows a scent through a radstorm.",
    "bombay": "A sleek black cat with the soul of a tiny panther.",
    "boxer": "A playful bruiser that guards the vault with slobbery enthusiasm.",
    "british shorthair": "A plush, unflappable cat that weathers any crisis with a yawn.",
    "brittany": "A nimble spaniel that points at danger before anyone else.",
    "burmilla": "A silver-tipped cat that glides quietly through the shadows.",
    "butch": "A tough little parrot that repeats every order it hears.",
    "calypso": "A scruffy werewolf cat that howls along with the alarms.",
    "cattle dog": "A hard-driving herder that never lets the herd stray.",
    "cinder": "A grumpy little hunter that hisses at anything bigger than lunch.",
    "cindy": "A sunny retriever that greets every dweller like a long-lost friend.",
    "cloudy": "A soft gray cat that drifts from lap to lap all day.",
    "cocoa bean": "A brown-nosed pointer that freezes at the first sign of trouble.",
    "collie": "A loyal herder that watches the vault's young with tireless care.",
    "cx404": "A scruffy wanderer with a nose for loose caps and shortcuts.",
    "dalmatian": "A spotted firehouse dog that races to any alarm.",
    "diamond": "A pampered show cat that expects the finest rations.",
    "doberman": "A lean guard dog that looks the part and plays it too.",
    "dogmeat (fallout 4)": "A loyal Shepherd who tracks trouble and dropped gear by scent.",
    "duchess": "A regal white cat that surveys the vault like a kingdom.",
    "duke (far harbor)": "A weather-beaten hound that knows every trail on the island.",
    "english mastiff": "A mountain of a dog that guards the door by simply existing.",
    "four score": "A scrappy herder named for the finest measure of liberty.",
    "gaston": "A proud spaniel that hunts for praise as much as prey.",
    "genius": "A tailless cat that solves any puzzle for a treat.",
    "german pointer": "A keen-nosed hunter that flushes out trouble before you see it.",
    "german shepherd": "A disciplined working dog that guards its dwellers without fail.",
    "ginger": "A soft-eared cat that folds up small wherever it naps.",
    "goblet": "A talkative Siamese that argues with the radio all day.",
    "golden retriever": "A cheerful retriever that is happiest splashing through any puddle.",
    "goliath": "A massive mastiff whose bark rattles the whole vault.",
    "greyhound": "A lean sprinter that clears the corridors in a blur.",
    "havana brown": "A warm brown cat that prefers a lap to a ledge.",
    "hulk": "A muscular sweetheart that is all slobber and devotion.",
    "husky": "Fast, tireless, and always spoiling for a scrap.",
    "kabosu": "A cheerful Akita that greets every shift change with a bark.",
    "kato": "A tiger-striped cat that stalks the supply room with style.",
    "kuma": "A sturdy bear of a dog that walks the perimeter at night.",
    "laperm": "A curly-haired cat that sheds far less than the rest.",
    "little helper": "A swift greyhound that fetches tools before you ask.",
    "lord puffington": "A pampered poodle that demands the fluffiest pillow in the vault.",
    "lucky": "A lucky spotted dog that always digs up something useful.",
    "luna": "A moon-pale cat that prowls the quiet night shifts.",
    "lykoi": "A ragged werewolf cat that is sweeter than it looks.",
    "maine coon": "A gentle giant of a cat with a purr you can feel through the floor.",
    "maizie rai": "A powerful Rottweiler that guards the vault's stores fiercely.",
    "manx": "A tailless cat that patrols the vents with a bouncy hop.",
    "merlin": "A whiskered mystic cat that seems to sense trouble first.",
    "moose": "A big floppy hound that follows its nose into every corner.",
    "mr. pebbles": "A sociable little companion that keeps the whole vault smiling.",
    "mr. peepers": "A sharp-eyed pointer that never stops scanning the horizon.",
    "muttface": "A scruffy mixed mutt with the heart of a purebred hero.",
    "ocicat": "A wild-looking cat that is tame as they come when fed on time.",
    "pal": "A steady collie that is always first to greet you at the door.",
    "pallas's cat": "Sharp-eyed and always the first to spot trouble.",
    "persian": "A fluffy blueblood that expects to be brushed on schedule.",
    "pirate parrot": "A salty parrot with a peg leg and a taste for caps.",
    "pit bull terrier": "A stout, affectionate dog that is all muscle under the wiggles.",
    "polly": "A chatty parrot that calls the vault to order each morning.",
    "pongo": "A spotted pup with a parent's knack for counting things.",
    "poodle": "A clever, curly-coated dog that is as sharp as its trim.",
    "pouncer": "A curly cat that pounces on radroaches for sport.",
    "pugsley": "A flat-faced lap cat that snores like a dormant reactor.",
    "pumpkin": "An orange-and-white cat that loves nothing more than water.",
    "ranger": "A loyal pit bull that patrols the wasteland at your heel.",
    "rollerbrain": "A rolling sentry-bot that patrols the corridors and never sleeps.",
    "rottweiler": "A solid guard dog that looks out for the whole vault.",
    "saffron": "A golden fox-faced cat that is forever up on the shelves.",
    "scavver": "A goofy boxer that will raid any crate you leave open.",
    "scottish fold": "A round-eared cat that perches like a small owl.",
    "shadow": "A black cat that appears silently wherever it is needed.",
    "shakespeare": "A dramatic tailless cat that soliloquizes at dawn.",
    "siamese": "A vocal Siamese that comments on everything you do.",
    "somali": "A fluffy fox-like cat that trots around like a tiny lion.",
    "speckle": "A spotted cat with the sleek build of a small wildcat.",
    "sphynx": "A warm, hairless cat that insists on sharing your blanket.",
    "st. bernard": "A sturdy rescue dog that shrugs off the wasteland's hazards.",
    "static": "A curly cat whose fur crackles with an odd dry charge.",
    "sterling": "A silver-gray mouser that keeps the storerooms vermin-free.",
    "stubbs": "A veteran tailless cat that has ruled a homestead or two.",
    "titan": "A hulking pit bull with the patience of a saint.",
    "toyger": "A miniature tiger of a cat that stalks like a big one.",
    "trained parrot": "A disciplined parrot that runs every drill right on cue.",
    "trench": "A snow-loving husky that thrives in the coldest corridors.",
    "turkish van": "A water-loving cat that paddles in the wash basins.",
    "vault-tec parrot": "Repeats every training drill it hears, word for word.",
    "vinnie": "A loyal parrot that recites Vault-Tec jingles on command.",
    "wanderer": "A restless parrot with a shanty for every long haul.",
    "yao guai cub": "A mangy bear cub that is all patchy fur, sharp claws and stubborn grit.",
    "zula": "A restless Abyssinian that races through the corridors.",
}


def pet_description_for_name(name: str | None) -> str | None:
    """The catalog description for a pet name, or None for None/blank/unknown."""
    if not name:
        return None
    return PET_DESCRIPTION_BY_NAME.get(name.strip().casefold())


def pet_modifiers_for(entity: object) -> PetEffect:
    """The equipped pet's effect for an entity, or neutral when none is equipped.

    Reads the pet via ``equipped_pet`` (``__dict__``, no lazy IO) and resolves
    its name through the catalog.
    """
    pet = equipped_pet(entity)
    if pet is None:
        return NEUTRAL_EFFECT
    return pet_effect_for_name(pet.name)
