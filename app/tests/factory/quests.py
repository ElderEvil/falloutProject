import random

from faker import Faker

fake = Faker()


def create_fake_quest_step():
    return {
        "title": fake.sentence(),
        "description": fake.sentence(),
        "order_number": random.randint(1, 10),
        "completed": random.choice([True, False]),
    }


def create_fake_quest():
    return {"title": fake.sentence(), "description": fake.sentence(), "completed": random.choice([True, False])}
