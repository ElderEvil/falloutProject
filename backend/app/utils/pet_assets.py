"""Pet name to companion image mapping.

Starter plus full FOS breed roster (cats, dogs, parrots): breed names and
legendary unique names resolve to their breed art. Pets are inventory items,
not dwellers: quest and lunchbox rewards carry them as generic ``Item`` rows
with ``item_type="pet"``. Unmapped pets fall back to the generic icon in the UI.
"""

from pathlib import Path

# Maps canonical lower-cased pet names to the actual filename in
# backend/app/static/pet_images/. Keep this sorted alphabetically by key.
PET_NAME_TO_IMAGE_FILE: dict[str, str] = {
    "[[rollerbrain]]": "FOS [[Rollerbrain]].png",
    "abyssinian": "FOS Abyssinian.png",
    "akita": "FOS Akita.png",
    "alien drone": "FOS Alien Drone.png",
    "american shorthair": "FOS American Shorthair.png",
    "apolda": "FOS Doberman.png",
    "ashes": "FOS British Shorthair.png",
    "australian shepherd": "FOS Australian Shepherd.png",
    "bandit (dog)": "FOS Australian Shepherd.png",
    "bangor": "FOS Maine Coon.png",
    "barry": "FOS St. Bernard.png",
    "bastet": "FOS Sphynx.png",
    "belgian malinois": "FOS Belgian Malinois.png",
    "bigsby": "FOS Collie.png",
    "black lab": "FOS Black Lab.png",
    "bloodhound": "FOS Bloodhound.png",
    "bombay": "FOS Bombay.png",
    "boxer": "FOS Boxer.png",
    "british shorthair": "FOS British Shorthair.png",
    "brittany": "FOS Brittany.png",
    "burmilla": "FOS Burmilla.png",
    "butch": "FOS Trained parrot.png",
    "calypso": "FOS Lykoi.png",
    "cattle dog": "FOS Cattle Dog.png",
    "cinder": "FOS Pallas's Cat.png",
    "cindy": "FOS Golden Retriever.png",
    "cloudy": "FOS Burmilla.png",
    "cocoa bean": "FOS German Pointer.png",
    "collie": "FOS Collie.png",
    "cx404": "FOS CX404.png",
    "dalmatian": "FOS Dalmatian.png",
    "diamond": "FOS Burmilla.png",
    "doberman": "FOS Doberman.png",
    "dogmeat (fallout 4)": "FOS German Shepherd.png",
    "duchess": "FOS Turkish Van.png",
    "duke (far harbor)": "FOS Bloodhound.png",
    "english mastiff": "FOS English Mastiff.png",
    "four score": "FOS Cattle Dog.png",
    "gaston": "FOS Brittany.png",
    "genius": "FOS Manx.png",
    "german pointer": "FOS German Pointer.png",
    "german shepherd": "FOS German Shepherd.png",
    "ginger": "FOS Scottish Fold.png",
    "goblet": "FOS Siamese.png",
    "golden retriever": "FOS Golden Retriever.png",
    "goliath": "FOS English Mastiff.png",
    "greyhound": "FOS Greyhound.png",
    "havana brown": "FOS Havana Brown.png",
    "hulk": "FOS Pit Bull Terrier.png",
    "husky": "FOS Husky.png",
    "kabosu": "FOS Akita.png",
    "kato": "FOS Toyger.png",
    "kuma": "FOS Akita.png",
    "laperm": "FOS LaPerm.png",
    "little helper": "FOS Greyhound.png",
    "lord puffington": "FOS Poodle.png",
    "lucky": "FOS Dalmatian.png",
    "luna": "FOS LaPerm.png",
    "lykoi": "FOS Lykoi.png",
    "maine coon": "FOS Maine Coon.png",
    "maizie rai": "FOS Rottweiler.png",
    "manx": "FOS Manx.png",
    "merlin": "FOS Havana Brown.png",
    "moose": "FOS Bloodhound.png",
    "mr. pebbles": "FOS Persian.png",
    "mr. peepers": "FOS German Pointer.png",
    "muttface": "FOS Black Lab.png",
    "ocicat": "FOS Ocicat.png",
    "pal": "FOS Collie.png",
    "pallas's cat": "FOS Pallas's Cat.png",
    "persian": "FOS Persian.png",
    "pirate parrot": "FOS Pirate parrot.png",
    "pit bull terrier": "FOS Pit Bull Terrier.png",
    "polly": "FOS Trained parrot.png",
    "pongo": "FOS Dalmatian.png",
    "poodle": "FOS Poodle.png",
    "pouncer": "FOS LaPerm.png",
    "pugsley": "FOS Persian.png",
    "pumpkin": "FOS Turkish Van.png",
    "ranger": "FOS Pit Bull Terrier.png",
    "rottweiler": "FOS Rottweiler.png",
    "saffron": "FOS Somali.png",
    "scavver": "FOS Boxer.png",
    "scottish fold": "FOS Scottish Fold.png",
    "shadow": "FOS Bombay.png",
    "shakespeare": "FOS Manx.png",
    "siamese": "FOS Siamese.png",
    "somali": "FOS Somali.png",
    "speckle": "FOS Ocicat.png",
    "sphynx": "FOS Sphynx.png",
    "st. bernard": "FOS St. Bernard.png",
    "static": "FOS LaPerm.png",
    "sterling": "FOS American Shorthair.png",
    "stubbs": "FOS Manx.png",
    "titan": "FOS Pit Bull Terrier.png",
    "toyger": "FOS Toyger.png",
    "trained parrot": "FOS Trained parrot.png",
    "trench": "FOS Husky.png",
    "turkish van": "FOS Turkish Van.png",
    "vault-tec parrot": "FOS Vault-Tec parrot.png",
    "vinnie": "FOS Vault-Tec parrot.png",
    "wanderer": "FOS Pirate parrot.png",
    "zula": "FOS Abyssinian.png",
    "{{linkable": "FOS Bloodhound.png",
}

_PET_IMAGE_DIR = Path(__file__).parent.parent / "static" / "pet_images"


def get_pet_image_url(pet_name: str | None) -> str | None:
    """Return the static image URL for a pet, if a mapped asset exists.

    The lookup is case-insensitive and ignores leading/trailing whitespace.
    Returns ``None`` when the pet is unmapped or the mapped file is missing
    on disk, so callers can fall back to a generic icon.
    """
    if not pet_name:
        return None

    key = pet_name.strip().casefold()
    filename = PET_NAME_TO_IMAGE_FILE.get(key)
    if not filename:
        return None

    if not (_PET_IMAGE_DIR / filename).exists():
        return None

    return f"/static/pet_images/{filename}"
