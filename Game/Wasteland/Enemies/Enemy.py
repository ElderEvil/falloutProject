from enum import Enum


class EnemyType(Enum):
    GHOUL = "Feral Ghoul"
    RAIDER = "Raider"
    DEATHCLAW = "Deathclaw"
    RADSCORPION = "Radscorpion"
    RADROACH = "Radroach"
    MOLERAT = "Mole rat"


class Enemy:
    def __init__(self, enemy_type: EnemyType, level: int, name: str = None):
        self.name = name or enemy_type
        self.enemy_type = enemy_type
        self.level = level
        self.max_health = self.calculate_max_health()
        self.health = self.max_health
        self.attack = self.calculate_attack()
        self.defense = 0

    def calculate_max_health(self) -> int:
        if self.enemy_type == EnemyType.RAIDER:
            return 100 + (self.level - 1) * 10
        elif self.enemy_type == EnemyType.MOLERAT:  # noqa: RET505
            return 70 + (self.level - 1) * 7
        elif self.enemy_type == EnemyType.GHOUL:
            return 80 + (self.level - 1) * 8
        elif self.enemy_type == EnemyType.DEATHCLAW:
            return 150 + (self.level - 1) * 15
        else:
            raise ValueError("Invalid enemy type")  # noqa: TRY003

    def calculate_attack(self) -> int:
        if self.enemy_type == EnemyType.RAIDER:
            return 10 + (self.level - 1) * 2
        elif self.enemy_type == EnemyType.GHOUL:  # noqa: RET505
            return 8 + (self.level - 1)
        elif self.enemy_type == EnemyType.DEATHCLAW:
            return 20 + (self.level - 1) * 3
        else:
            raise ValueError("Invalid enemy type")  # noqa: TRY003

    def take_damage(self, damage):
        self.health -= max(damage - self.defense, 0)
        if self.health <= 0:
            self.health = 0
            print(f"{self.name} has been defeated!")

    def is_alive(self):
        return self.health > 0

    def __str__(self):
        return f"{self.name} ({self.health}/{self.max_health})"
