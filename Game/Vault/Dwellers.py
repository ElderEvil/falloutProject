import asyncio
import logging

import random
from typing import Optional

from Game.Items.Outfits import Outfit
from Game.Items.Weapons import Weapon
from Game.Vault.utilities.Person import Person, PersonRarity
from Game.Wasteland.Enemies.Enemy import Enemy
from Game.settings import DWELLER_GROW_UP_TIME

logger = logging.getLogger(__name__)
STORAGE = []


class Dweller(Person):
    def __init__(self, gender: str = None, first_name: str = None, last_name: str = None,
                 rarity: PersonRarity = PersonRarity.COMMON):
        super().__init__(gender, first_name, last_name, rarity)

        # Generic stats
        self.level = 1
        self.experience = 0
        self.max_health = self.calculate_max_health()
        self.health = self.max_health

        # Combat
        self.equipped_weapon: Optional[Weapon] = None
        self.equipped_outfit: Optional[Outfit] = None

        # Vault info
        self.happiness = 50
        self.is_adult = True
        self.current_room = None

        # Inventory
        self.inventory = {}

    @property
    def damage(self):
        if self.equipped_weapon:
            return random.randint(*self.equipped_weapon.damage_range) * getattr(self, self.equipped_weapon.stat)
        else:
            return self.strength + self.perception + (self.level - 1) * 2

    @property
    def defense(self):
        if self.equipped_outfit:
            return self.endurance + self.agility + self.equipped_outfit.defense
        else:
            return self.endurance + self.agility

    def calculate_max_health(self):
        return 50 + self.endurance * 5 + (self.level - 1) * 10

    def equip_outfit(self, outfit: Outfit):
        if not self.is_adult:
            raise ValueError("Children can not wear outfits")
        elif self.gender != outfit.gender:
            raise ValueError(f"{outfit} is not appropriate attire for {self.full_name}")

        if self.equipped_outfit:
            STORAGE.append(self.equipped_outfit)

        self.equipped_outfit = outfit
        self.update_attributes()

    def unequip_outfit(self):
        STORAGE.append(self.equipped_outfit)
        self.equipped_outfit = None
        self.update_attributes()

    def equip_weapon(self, weapon: Weapon):
        self.equipped_weapon = weapon
        self.update_attributes()

    def unequip_weapon(self):
        self.equipped_weapon = None
        self.update_attributes()

    def update_attributes(self):  # TODO make it usable
        ...

    def attack_target(self, target: Enemy):
        target.take_damage(self.damage)

    def take_damage(self, damage):
        self.health -= max(damage - self.defense, 0)
        if self.health <= 0:
            self.health = 0
            logger.info(f"{self.full_name} has been defeated!")

    def is_alive(self):
        return self.health > 0

    def reanimate(self):
        if self.is_alive:
            logger.info("Cannot reanimate alive dweller")
        else:
            self.health = self.max_health // 5

    def add_experience(self, amount: int):
        self.experience += amount
        experience_required = self.calculate_experience_required()
        if self.experience >= experience_required:
            self.level += 1
            self.experience -= experience_required
            logger.info(f"{self.full_name} has reached level {self.level}!")

    def calculate_experience_required(self):
        return int(100 * 1.5 ** self.level)

    def add_happiness(self, amount: int = 10):
        if self.happiness + amount > 100:
            self.happiness = 100
        else:
            self.happiness += amount

    def remove_happiness(self, amount: int = 10):
        if self.happiness - amount < 0:
            self.happiness = 0
        else:
            self.happiness -= amount

    def add_attribute(self, attribute: str, value: int):
        if getattr(self, attribute) + value > 10:
            setattr(self, attribute, 10)
        else:
            setattr(self, attribute, getattr(self, attribute) + value)

    def remove_attribute(self, attribute: str, value: int):
        if getattr(self, attribute) - value < 0:
            setattr(self, attribute, 0)
        else:
            setattr(self, attribute, getattr(self, attribute) - value)

    def reproduce(self, partner: 'Dweller') -> Optional['Dweller']:
        from Game.Vault.Rooms import LivingRoom
        if self.gender == partner.gender:
            logger.info("Same-gender reproduction is not possible!")
            return None

        if not self.is_adult or not partner.is_adult:
            logger.info("One or both dwellers are not adults yet!")
            return None

        if self.current_room != partner.current_room:
            logger.info("The dwellers are not in the same room!")
            return None

        if not isinstance(self.current_room, LivingRoom):
            logger.info("Reproduction is only possible in the living room!")
            return None

        # Roll a chance to succeed based on the dwellers' charisma and happiness
        success_chance = (self.charisma + partner.charisma) / 20 * (self.happiness / 100) * (partner.happiness / 100)
        if random.random() > success_chance:
            logger.info("The reproduction attempt failed.")
            return None

        # Create a new dweller with randomized gender and genetic traits
        child_rarity = random.choice([self.rarity, partner.rarity])
        child = Dweller(rarity=child_rarity)

        # Set the child's last name to be the same as the father's last name
        if self.gender == 'M':
            child.last_name = self.last_name
        else:
            child.last_name = partner.last_name

        # Add the child to the current room
        self.current_room.add_worker(child)

        # Start child grow up process
        self.grow_up()

        # Print a success message and return the new dweller object
        logger.info(
            f"{self.full_name} and {partner.full_name} have successfully reproduced! Welcome, {child.full_name}!")
        return child

    async def grow_up(self):
        await asyncio.sleep(DWELLER_GROW_UP_TIME)
        self.is_adult = True
        logger.info(f"{self.full_name} is now an adult!")

    def __str__(self):
        return f"[{self.level}]{self.full_name} (Health: {self.health}/{self.max_health})"
