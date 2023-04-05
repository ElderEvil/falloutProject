from dataclasses import dataclass

from Game.Items.Items import Item, ItemRarity

PREFIXES = {"Rusty," "Enhanced," "Focused," "Hardened"}


@dataclass(frozen=True)
class Weapon(Item):
    weapon_type: str
    name: str
    stat: str
    damage_range: tuple[int, int]


@dataclass(frozen=True)
class MeleeWeapon(Weapon):
    weapon_type: str = 'Melee Weapon'
    stat: str = "strength"


@dataclass(frozen=True)
class BaseballBat(MeleeWeapon):
    name: str = "Baseball bat"
    damage_range: tuple[int, int] = (5, 15)


@dataclass(frozen=True)
class ButcherKnife(MeleeWeapon):
    name: str = "Butcher knife"
    damage_range: tuple[int, int] = (8, 18)


@dataclass(frozen=True)
class KitchenKnife(MeleeWeapon):
    name: str = "Kitchen knife"
    damage_range: tuple[int, int] = (3, 11)


@dataclass(frozen=True)
class Pickaxe(MeleeWeapon):
    name: str = "Pickaxe"
    damage_range: tuple[int, int] = (11, 21)


@dataclass(frozen=True)
class PoolCue(MeleeWeapon):
    name: str = "Pool cue"
    damage_range: tuple[int, int] = (0, 8)


@dataclass(frozen=True)
class FireHydrantBat(MeleeWeapon):
    name: str = "Fire hydrant bat"
    damage_range: tuple[int, int] = (19, 31)


@dataclass(frozen=True)
class RelentlessRaiderSword(MeleeWeapon):
    name: str = "Relentless raider sword"
    damage_range: tuple[int, int] = (16, 28)


@dataclass(frozen=True)
class Ripper(MeleeWeapon):
    name: str = "Ripper"
    damage_range: tuple[int, int] = (11, 16)


@dataclass(frozen=True)
class PowerFist(MeleeWeapon):
    name: str = "Power fist"
    damage_range: tuple[int, int] = (13, 18)


@dataclass(frozen=True)
class GrognaksAxe(MeleeWeapon):
    name: str = "Grognak's axe"
    damage_range: tuple[int, int] = (18, 26)


@dataclass(frozen=True)
class Gun(Weapon):
    weapon_type: str = "Gun"


@dataclass(frozen=True)
class Pistol(Gun):
    subtype: str = "Pistols"
    stat: str = "agility"


@dataclass(frozen=True)
class PipePistol(Pistol):
    name: str = "Pipe pistol"
    damage_range: tuple[int, int] = (1, 3)


@dataclass(frozen=True)
class Dot32Pistol(Pistol):
    name: str = ".32 pistol"
    damage_range: tuple[int, int] = (1, 2)


@dataclass(frozen=True)
class TenMMPistol(Pistol):
    name: str = "10mm pistol"
    damage_range: tuple[int, int] = (2, 3)


@dataclass(frozen=True)
class Scoped44(Pistol):
    name: str = "Scoped .44"
    damage_range: tuple[int, int] = (3, 4)


@dataclass(frozen=True)
class RustyGaussPistol(Pistol):
    name: str = "Rusty Gauss pistol"
    damage_range: tuple[int, int] = (12, 12)


@dataclass(frozen=True)
class Rifle(Gun):
    subtype: str = "Rifles"
    stat: str = "perception"


@dataclass(frozen=True)
class PipeRifle(Rifle):
    name: str = "Pipe rifle"
    damage_range: tuple[int, int] = (5, 7)


@dataclass(frozen=True)
class AssaultRifle(Rifle):
    name: str = "Assault rifle"
    damage_range: tuple[int, int] = (8, 9)


@dataclass(frozen=True)
class BBGun(Rifle):
    name: str = "BB gun"
    damage_range: tuple[int, int] = (0, 2)


@dataclass(frozen=True)
class GaussRifle(Rifle):
    name: str = "Gauss rifle"
    damage_range: tuple[int, int] = (16, 17)


@dataclass(frozen=True)
class Henrietta(Rifle):
    name: str = "Henrietta"
    damage_range: tuple[int, int] = (13, 16)


@dataclass(frozen=True)
class HuntingRifle(Rifle):
    name: str = "Hunting rifle"
    damage_range: tuple[int, int] = (5, 6)


@dataclass(frozen=True)
class LeverActionRifle(Rifle):
    name: str = "Lever-action rifle"
    damage_range: tuple[int, int] = (4, 5)


@dataclass(frozen=True)
class RailwayRifle(Rifle):
    name: str = "Railway rifle"
    damage_range: tuple[int, int] = (14, 15)


@dataclass(frozen=True)
class SniperRifle(Rifle):
    name: str = "Sniper rifle"
    damage_range: tuple[int, int] = (10, 11)


@dataclass(frozen=True)
class Shotgun(Gun):
    subtype: str = "Shotguns"
    stat: str = "endurance"


@dataclass(frozen=True)
class CombatShotgun(Shotgun):
    name: str = "Combat shotgun"
    damage_range: tuple[int, int] = (13, 14)


@dataclass(frozen=True)
class SawedOffShotgun(Shotgun):
    name: str = "Sawed-off shotgun"
    damage_range: tuple[int, int] = (6, 7)


@dataclass(frozen=True)
class EnergyWeapon(Weapon):
    weapon_type = "Energy Weapon"


@dataclass(frozen=True)
class EnergyPistol(EnergyWeapon):
    subtype = "Pistols"
    stat: str = "agility"


@dataclass(frozen=True)
class AlienBlaster(EnergyPistol):
    name: str = "Alien blaster"
    damage_range: tuple[int, int] = (18, 19)


@dataclass(frozen=True)
class LaserPistol(EnergyPistol):
    name: str = "Laser pistol"
    damage_range: tuple[int, int] = (7, 8)


@dataclass(frozen=True)
class PlasmaPistol(EnergyPistol):
    name: str = "Plasma pistol"
    damage_range: tuple[int, int] = (11, 12)


@dataclass(frozen=True)
class AssaultronHead(EnergyPistol):
    name: str = "Assaultron head"
    damage_range: tuple[int, int] = (8, 12)


@dataclass(frozen=True)
class InstitutePistol(EnergyPistol):
    name: str = "Institute pistol"
    damage_range: tuple[int, int] = (9, 11)


@dataclass(frozen=True)
class EnergyRifle(EnergyWeapon):
    subtype = "Rifles"
    stat: str = "intelligence"


@dataclass(frozen=True)
class LaserMusket(EnergyRifle):
    name: str = "Laser musket"
    damage_range: tuple[int, int] = (10, 13)


@dataclass(frozen=True)
class AlienDisintegrator(EnergyRifle):
    name: str = "Alien disintegrator"
    damage_range: tuple[int, int] = (17, 17)


@dataclass(frozen=True)
class LaserRifle(EnergyRifle):
    name: str = "Laser rifle"
    damage_range: tuple[int, int] = (12, 13)


@dataclass(frozen=True)
class PlasmaRifle(EnergyRifle):
    name: str = "Plasma rifle"
    damage_range: tuple[int, int] = (17, 18)


@dataclass(frozen=True)
class PulseRifle(EnergyRifle):
    name: str = "Pulse rifle"
    damage_range: tuple[int, int] = (18, 19)


@dataclass(frozen=True)
class InstituteRifle(EnergyRifle):
    name: str = "Institute rifle"
    damage_range: tuple[int, int] = (14, 16)


@dataclass(frozen=True)
class HeavyWeapons(Weapon):
    weapon_type = "Heavy Weapon"
    stat: str = "strength"


@dataclass(frozen=True)
class ExplosiveWeapons(HeavyWeapons):
    subtype = "Explosive weapons"


@dataclass(frozen=True)
class FatMan(ExplosiveWeapons):
    name: str = "Fat Man"
    damage_range: tuple[int, int] = (22, 23)


@dataclass(frozen=True)
class MissileLauncher(ExplosiveWeapons):
    name: str = "Missile launcher"
    damage_range: tuple[int, int] = (20, 21)


@dataclass(frozen=True)
class JunkJet(ExplosiveWeapons):
    name: str = "Junk Jet"
    damage_range: tuple[int, int] = (13, 15)


@dataclass(frozen=True)
class Flamers(HeavyWeapons):
    subtype = "Flamers"


@dataclass(frozen=True)
class Flamer(Flamers):
    name: str = "Flamer"
    damage_range: tuple[int, int] = (15, 16)


@dataclass(frozen=True)
class PlasmaThrower(Flamers):
    name: str = "Plasma thrower"
    damage_range: tuple[int, int] = (17, 19)


@dataclass(frozen=True)
class AutomaticWeapons(HeavyWeapons):
    subtype = "Automatic weapons"


@dataclass(frozen=True)
class Minigun(AutomaticWeapons):
    name: str = "Minigun"
    damage_range: tuple[int, int] = (19, 20)


@dataclass(frozen=True)
class GatlingLaser(AutomaticWeapons):
    name: str = "Gatling laser"
    damage_range: tuple[int, int] = (21, 22)


@dataclass(frozen=True)
class PlasmaCaster(AutomaticWeapons):
    name: str = "Plasma caster"
    damage_range: tuple[int, int] = (17, 21)
