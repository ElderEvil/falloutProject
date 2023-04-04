from dataclasses import dataclass

from Game.Items.Items import Item, ItemRarity

PREFIXES = {"Rusty," "Enhanced," "Focused," "Hardened"}


@dataclass(frozen=True)
class Weapon(Item):
    type: str
    name: str
    stat: str
    damage_range: tuple[int, int]
    # variation: str

    # @property
    # def damage_modifier(self):
    #     match self.variation:
    #         case "Rusty":
    #             return -0.1
    #         case "Enhanced":
    #             return 0.05
    #         case "Focused":
    #             return 0.1
    #         case "Hardened":
    #             return 0.15
    #         case _:
    #             return 0
    #
    # @property
    # def rarity(self):
    #     match self.variation:
    #         case "Rusty":
    #             return ItemRarity.COMMON
    #         case "Enhanced", "Focused":
    #             return ItemRarity.RARE
    #         case "Hardened":
    #             return ItemRarity.LEGENDARY
    #         case _:
    #             return ItemRarity.COMMON


# @dataclass(frozen=True)
# class MeleeWeapon(Weapon):
#     type: str = 'Melee Weapon'
#     stat: str = "strength"
#
#
# @dataclass(frozen=True)
# class BaseballBat(MeleeWeapon):
#     name: str = "Baseball bat"
#     damage_range = (5, 15)
#
#
# @dataclass(frozen=True)
# class ButcherKnife(MeleeWeapon):
#     name = "Butcher knife"
#     damage_range = (8, 18)
#
#
# @dataclass(frozen=True)
# class KitchenKnife(MeleeWeapon):
#     name = "Kitchen knife"
#     damage_range = (3, 11)
#
#
# @dataclass(frozen=True)
# class Pickaxe(MeleeWeapon):
#     name = "Pickaxe"
#     damage_range = (11, 21)
#
#
# @dataclass(frozen=True)
# class PoolCue(MeleeWeapon):
#     name = "Pool cue"
#     damage_range = (0, 8)
#
#
# @dataclass(frozen=True)
# class FireHydrantBat(MeleeWeapon):
#     name = "Fire hydrant bat"
#     damage_range = (19, 31)
#
#
# @dataclass(frozen=True)
# class RelentlessRaiderSword(MeleeWeapon):
#     name = "Relentless raider sword"
#     damage_range = (16, 28)
#
#
# @dataclass(frozen=True)
# class Ripper(MeleeWeapon):
#     name = "Ripper"
#     damage_range = (11, 16)
#
#
# @dataclass(frozen=True)
# class PowerFist(MeleeWeapon):
#     name = "Power fist"
#     damage_range = (13, 18)
#
#
# @dataclass(frozen=True)
# class GrognaksAxe(MeleeWeapon):
#     name = "Grognak's axe"
#     damage_range = (18, 26)
#
#
# @dataclass(frozen=True)
# class Gun(Weapon):
#     type: str = "Gun"
#
#
# @dataclass(frozen=True)
# class Pistol(Gun):
#     subtype: str = "Pistols"
#     stat: str = "agility"
#
#
# @dataclass(frozen=True)
# class PipePistol(Pistol):
#     name: str = "Pipe pistol"
#     damage_range = (5, 10)
#
#
# @dataclass(frozen=True)
# class Dot32Pistol(Pistol):
#     name = ".32 pistol"
#     damage_range = (8, 15)
#
#
# @dataclass(frozen=True)
# class TenMMPistol(Pistol):
#     name = "10mm pistol"
#     damage_range = (10, 20)
#
#
# @dataclass(frozen=True)
# class Scoped44(Pistol):
#     name = "Scoped .44"
#     damage_range = (15, 30)
#
#
# @dataclass(frozen=True)
# class GaussPistol(Pistol):
#     name = "Gauss pistol"
#     damage_range = (20, 40)
#
#
# @dataclass(frozen=True)
# class Rifle(Gun):
#     subtype: str = "Rifles"
#     stat: str = "perception"
#
#
# @dataclass(frozen=True)
# class PipeRifle(Rifle):
#     name = "Pipe rifle"
#     damage_range = (8, 15)
#
#
# @dataclass(frozen=True)
# class AssaultRifle(Rifle):
#     name = "Assault rifle"
#     damage_range = (12, 22)
#
#
# @dataclass(frozen=True)
# class BBGun(Rifle):
#     name = "BB gun"
#     damage_range = (5, 10)
#
#
# @dataclass(frozen=True)
# class GaussRifle(Rifle):
#     name = "Gauss rifle"
#     damage_range = (25, 50)
#
#
# @dataclass(frozen=True)
# class Henrietta(Rifle):
#     name = "Henrietta"
#     damage_range = (18, 30)
#
#
# @dataclass(frozen=True)
# class HuntingRifle(Rifle):
#     name = "Hunting rifle"
#     damage_range = (15, 25)
#
#
# @dataclass(frozen=True)
# class LeverActionRifle(Rifle):
#     name = "Lever-action rifle"
#     damage_range = (12, 20)
#
#
# @dataclass(frozen=True)
# class RailwayRifle(Rifle):
#     name = "Railway rifle"
#     damage_range = (20, 35)
#
#
# @dataclass(frozen=True)
# class SniperRifle(Rifle):
#     name = "Sniper rifle"
#     damage_range = (20, 40)
#
#
# @dataclass(frozen=True)
# class Shotgun(Gun):
#     subtype: str = "Shotguns"
#     stat: str = "endurance"
#
#
# @dataclass(frozen=True)
# class CombatShotgun(Shotgun):
#     name = "Combat shotgun"
#     damage_range = (18, 30)
#
#
# @dataclass(frozen=True)
# class SawedOffShotgun(Shotgun):
#     name = "Sawed-off shotgun"
#     damage_range = (20, 30)
#
#
# @dataclass(frozen=True)
# class EnergyWeapon(Weapon):
#     type = "Energy Weapon"
#
#
# @dataclass(frozen=True)
# class EnergyPistol(EnergyWeapon):
#     subtype = "Pistols"
#     stat: str = "agility"
#
#
# @dataclass(frozen=True)
# class AlienBlaster(EnergyPistol):
#     name = "Alien blaster"
#     damage_range = (50, 70)
#
#
# @dataclass(frozen=True)
# class LaserPistol(EnergyPistol):
#     name = "Laser pistol"
#     damage_range = (10, 20)
#
#
# @dataclass(frozen=True)
# class PlasmaPistol(EnergyPistol):
#     name = "Plasma pistol"
#     damage_range = (20, 30)
#
#
# @dataclass(frozen=True)
# class AssaultronHead(EnergyPistol):
#     name = "Assaultron head"
#     damage_range = (40, 50)
#
#
# @dataclass(frozen=True)
# class InstitutePistol(EnergyPistol):
#     name = "Institute pistol"
#     damage_range = (15, 25)
#
#
# @dataclass(frozen=True)
# class EnergyRifle(EnergyWeapon):
#     subtype = "Rifles"
#     stat: str = "intelligence"
#
#
# @dataclass(frozen=True)
# class LaserMusket(EnergyRifle):
#     name = "Laser musket"
#     damage_range = (50, 80)
#
#
# @dataclass(frozen=True)
# class AlienDisintegrator(EnergyRifle):
#     name = "Alien disintegrator"
#     damage_range = (70, 90)
#
#
# @dataclass(frozen=True)
# class LaserRifle(EnergyRifle):
#     name = "Laser rifle"
#     damage_range = (15, 25)
#
#
# @dataclass(frozen=True)
# class PlasmaRifle(EnergyRifle):
#     name = "Plasma rifle"
#     damage_range = (30, 40)
#
#
# @dataclass(frozen=True)
# class PulseRifle(EnergyRifle):
#     name = "Pulse rifle"
#     damage_range = (40, 50)
#
#
# @dataclass(frozen=True)
# class InstituteRifle(EnergyRifle):
#     name = "Institute rifle"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class HeavyWeapons(Weapon):
#     type = "Heavy Weapon"
#     stat: str = "strength"
#
#
# @dataclass(frozen=True)
# class ExplosiveWeapons(HeavyWeapons):
#     subtype = "Explosive weapons"
#
#
# @dataclass(frozen=True)
# class FatMan(ExplosiveWeapons):
#     name = "Fat Man"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class MissileLauncher(ExplosiveWeapons):
#     name = "Missile launcher"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class JunkJet(ExplosiveWeapons):
#     name = "Junk Jet"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class Flamers(HeavyWeapons):
#     subtype = "Flamers"
#
#
# @dataclass(frozen=True)
# class Flamer(Flamers):
#     name = "Flamer"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class PlasmaThrower(Flamers):
#     name = "Plasma thrower"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class AutomaticWeapons(HeavyWeapons):
#     subtype = "Automatic weapons"
#
#
# @dataclass(frozen=True)
# class Minigun(AutomaticWeapons):
#     name = "Minigun"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class GatlingLaser(AutomaticWeapons):
#     name = "Gatling laser"
#     damage_range = (25, 35)
#
#
# @dataclass(frozen=True)
# class PlasmaCaster(AutomaticWeapons):
#     name = "Plasma caster"
#     damage_range = (25, 35)
