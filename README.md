# Fallout Shelter Game
Fallout Shelter Game is a text-based simulation game where the player manages a vault full of dwellers, balancing their needs and resources to keep the vault thriving.

## Installation
To use the Fallout Shelter Game, you need to have Python installed on your computer. You can download Python from the official website: https://www.python.org/downloads/

The game also requires the Faker library to generate random names for the dwellers. You can install the library using pip by running the following command in your terminal:

`pip install -r requirements.txt`

## Usage
To start playing the game, simply run the fallout_shelter_game.py file in your terminal:

`python main.py`

You will be prompted to enter the number of dwellers you want to start with. Once you have entered the number, the game will begin.

During the game, you will be prompted with various options to manage your vault, such as building new rooms, assigning dwellers to tasks, and managing resources. Follow the prompts to make your decisions and progress through the game.

The goal of the game is to keep your vault thriving and build a community of happy and productive dwellers.
## Project structure 
```
falloutProject/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── crud/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── junk.py
│   │   │   ├── outfit.py
│   │   │   └── weapon.py
│   │   ├── endpoints/
│   │   │   ├── __init__.py
│   │   │   ├── junk.py
│   │   │   ├── outfit.py
│   │   │   ├── weapon.py
│   │   │   └── auth.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── junk.py
│   │       ├── outfit.py
│   │       └── weapon.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── settings.py
│   │   └── databases.py
│   └── db/
│       ├── __init__.py
│       └── base.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── endpoints/
│   │   │   ├── __init__.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_junk.py
│   │   │   ├── test_outfit.py
│   │   │   └── test_weapon.py
│   │   ├── test_auth.py
│   │   └── test_base.py
│   └── db/
│       ├── __init__.py
│       ├── test_database.py
│       └── test_models.py
├── README.md
├── requirements.txt
└── setup.py
```
## Credits
This game was developed by Dmytro Nedavnii as a pet project.

The game is inspired by the Fallout Shelter game by Bethesda Softworks.