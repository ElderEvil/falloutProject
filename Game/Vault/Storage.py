from Game.Items.models import Item
from Game.settings import DEFAULT_STORAGE_CAPACITY


class Storage:
    __instance = None

    @staticmethod
    def get_instance():
        if Storage.__instance is None:
            Storage()
        return Storage.__instance

    def __init__(self):
        if Storage.__instance is not None:
            raise Exception("You cannot create more than one instance of Storage.")
        else:
            self.capacity = DEFAULT_STORAGE_CAPACITY
            self.items = {}
            Storage.__instance = self

    def add_item(self, item: Item, quantity: int):
        if item in self.items:
            if self.items[item] + quantity <= self.capacity:
                self.items[item] += quantity
                return True
            else:
                return False
        else:
            if quantity <= self.capacity:
                self.items[item] = quantity
                return True
            else:
                return False

    def remove_item(self, item, quantity: int):
        if item in self.items:
            if self.items[item] >= quantity:
                self.items[item] -= quantity
                return True
            else:
                return False
        else:
            return False

    def get_items(self) -> dict[Item, int]:
        return self.items
