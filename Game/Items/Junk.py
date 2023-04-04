from dataclasses import dataclass, field

from Game.Items.Items import Item, ItemRarity


@dataclass(frozen=True)
class Junk(Item):
    type: str
    description: str
    rarity: ItemRarity
    value: 'int | None' = field(init=False)

    def __post_init__(self, ):
        object.__setattr__(self, 'value', self.rarity.value['value'] / 2)

    def __str__(self):
        return f"{self.name} (Type: {self.type}, Rarity: {self.rarity.value['name']})"


# Materials
@dataclass(frozen=True)
class Circuitry(Junk):
    type: str = 'Circuitry'


@dataclass(frozen=True)
class Leather(Junk):
    type: str = 'Leather'


@dataclass(frozen=True)
class Adhesive(Junk):
    type: str = 'Adhesive'


@dataclass(frozen=True)
class Cloth(Junk):
    type: str = 'Cloth'


@dataclass(frozen=True)
class Science(Junk):
    type: str = 'Science'


@dataclass(frozen=True)
class Steel(Junk):
    type: str = 'Steel'


@dataclass(frozen=True)
class Valuables(Junk):
    type: str = 'Valuables'


# Common
@dataclass(frozen=True)
class AlarmClock(Circuitry):
    name: str = "Alarm clock"
    rarity: ItemRarity = ItemRarity.COMMON
    description: str = "Because Dwellers that sleep in are sent to the Wasteland."


@dataclass(frozen=True)
class BaseballGlove(Leather):
    name: str = "Baseball glove"
    rarity: ItemRarity = ItemRarity.COMMON
    description: str = "Catch a baseball, rock or grenade and throw it right back."


@dataclass(frozen=True)
class DuctTape(Adhesive):
    name: str = "Duct tape"
    description: str = "Keep things in place with every handyman's secret weapon."


@dataclass(frozen=True)
class Yarn(Cloth):
    name: str = "Yarn"
    rarity: ItemRarity = ItemRarity.COMMON
    description: str = "Keep cats entertained and make fabulous outfits."


@dataclass(frozen=True)
class MagnifyingGlass(Science):
    name: str = "Magnifying glass"
    rarity: ItemRarity = ItemRarity.COMMON
    description: str = "This ant immolator might not work as well on Radroaches."


@dataclass(frozen=True)
class DeskFan(Steel):
    name: str = "Desk fan"
    rarity: ItemRarity = ItemRarity.COMMON
    description: str = "Great at keeping the Wasteland heat away. If it worked."


@dataclass(frozen=True)
class ToyCar(Valuables):
    name: str = "Toy car"
    rarity: ItemRarity = ItemRarity.COMMON
    description: str = "Brings you back to the care-free days of being a kid in the Vault."


# Rare
@dataclass(frozen=True)
class Camera(Circuitry):
    name: str = "Camera"
    rarity: ItemRarity = ItemRarity.RARE
    description: str = "Investigate hidden truths or take Vault family portraits."


@dataclass(frozen=True)
class BrahminHide(Leather):
    name: str = "Brahmin hide"
    rarity: ItemRarity = ItemRarity.RARE
    description: str = "Great for making a full-grain leather jacket. Two heads means two hoods!"


@dataclass(frozen=True)
class Wonderglue(Adhesive):
    name: str = "Wonderglue"
    rarity: ItemRarity = ItemRarity.RARE
    description: str = "Be careful not to glue your hands together or your eyelids shut."


@dataclass(frozen=True)
class TeddyBear(Cloth):
    name: str = "Teddy bear"
    rarity: ItemRarity = ItemRarity.RARE
    description: str = "Wasteland life is no picnic, so he's always ready for a warm hug."


@dataclass(frozen=True)
class Microscope(Science):
    name: str = "Microscope"
    rarity: ItemRarity = ItemRarity.RARE
    description: str = "Probably more useful in the Wasteland as a blunt weapon."


@dataclass(frozen=True)
class Shovel(Steel):
    name: str = "Shovel"
    rarity: ItemRarity = ItemRarity.RARE
    description: str = "Versatile and reliable. No Dweller should be without one."


@dataclass(frozen=True)
class Globe(Valuables):
    name: str = "Globe"
    rarity: ItemRarity = ItemRarity.RARE
    description: str = "Look back at the world that was. Or just spin it when you're bored."


# Legendary
@dataclass(frozen=True)
class MilitaryCircuitBoard(Circuitry):
    name: str = "Military circuit board"
    rarity: ItemRarity = ItemRarity.LEGENDARY
    description: str = "Top-of-the-line circuitry to make top-of-the-line equipment."


@dataclass(frozen=True)
class YaoGuaiHide(Leather):
    name: str = "Yao guai hide"
    rarity: ItemRarity = ItemRarity.LEGENDARY
    description: str = "Don't mess with me, your hide-made outfits will say."


@dataclass(frozen=True)
class MilitaryDuctTape(Adhesive):
    name: str = "Military duct tape"
    rarity: ItemRarity = ItemRarity.LEGENDARY
    description: str = "You could hold an aircraft carrier together with this stuff." \
                       " Just ask the residents of Rivet City."


@dataclass(frozen=True)
class TriFoldFlag(Cloth):
    name: str = "Tri-fold flag"
    rarity: ItemRarity = ItemRarity.LEGENDARY
    description: str = "Never forget the good ol' red, white and blue."


@dataclass(frozen=True)
class ChemistryFlask(Science):
    name: str = "Chemistry flask"
    rarity: ItemRarity = ItemRarity.LEGENDARY
    description: str = "Lets everyone know you're serious about doing sciency things."


@dataclass(frozen=True)
class GiddyupButtercup(Steel):
    name: str = "Giddyup Buttercup"
    rarity: ItemRarity = ItemRarity.LEGENDARY
    description: str = "Go ahead, no one's watching. Get on and take a ride."


@dataclass(frozen=True)
class GoldWatch(Valuables):
    name: str = "Gold watch"
    rarity: ItemRarity = ItemRarity.LEGENDARY
    description: str = "For when a weapon or outfit needs just a touch of bling."
