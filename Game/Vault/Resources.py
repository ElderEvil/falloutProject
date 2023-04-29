class ResourceType:
    def __init__(self, name: str, max_amount: int):
        self.name = name
        self.max_amount = max_amount
        self.current_amount = max_amount

    def consume(self, amount: int):
        if self.current_amount < amount:
            return False
        else:  # noqa: RET505
            self.current_amount -= amount
            return True

    def produce(self, amount: int):
        if self.current_amount + amount > self.max_amount:
            self.current_amount = self.max_amount
        else:
            self.current_amount += amount

    def __str__(self):
        return f"{self.name}: {self.current_amount}/{self.max_amount}"
