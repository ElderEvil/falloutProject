from Game.Quests.QuestManager import QuestManager
from Game.Quests.Tasks import TaskManager
from Game.Vault.Vault import Vault
from Game.logger_settings import logger
from utilities.menu_navigation import NavigationStack


def get_help():
    ...


def show_settings():
    ...


def get_valid_int_input(prompt, lower_bound, upper_bound):
    while True:
        try:
            value = int(input(prompt))
            if lower_bound <= value <= upper_bound:
                return value
            raise ValueError(f"Value must be between {lower_bound} and {upper_bound}")
        except ValueError:
            logger.error(f"Please enter a valid number between {lower_bound} and {upper_bound}.")


def display_menu(menu_items):
    print("What do you want to do?")
    for key, value in menu_items.items():
        print(f"{key}. {value['name']}")
    print("b. Go back")


def main():
    # Ask for the number of the vault
    vault_num = get_valid_int_input('Enter the number of your vault: ', 1, 999)
    vault = Vault(name=f"Vault {vault_num}")
    navigation_stack = NavigationStack()
    quest_manager = QuestManager()
    task_manager = TaskManager()

    def build_room():
        rooms_to_build = vault.get_available_room_types()
        print("Rooms you can build:")
        for i, room in enumerate(rooms_to_build, start=1):
            print(f"{i}. {room['name']}")
        room_choice = get_valid_int_input("Enter room number", 1, len(rooms_to_build))
        vault.construct_room(rooms_to_build[room_choice - 1])

    # Define menu items

    pip_boy_menu = {
        1: {"name": "Quests", "function": quest_manager.get_quests},
        2: {"name": "Tasks", "function": task_manager.get_tasks},
        3: {"name": "Storage", "function": vault.show_storage},
        4: {"name": "Help", "function": get_help},
        5: {"name": "Settings", "function": show_settings},
        0: {"name": "Back", "function": show_settings},
    }

    main_menu = {
        1: {"name": "Status", "function": vault.show_status},
        2: {"name": "Pip-Boy", "function": pip_boy_menu},
        3: {"name": "Build room", "function": build_room},
        0: {"name": "Exit", "function": exit},
    }

    # Main game loop
    while True:
        # Display current menu

        # Display menu and get user input
        display_menu(main_menu)
        choice = input("Enter the number of your choice (or 'b' to go back): ")

        # Check if user wants to go back
        if choice.lower() == 'b':
            navigation_stack.pop()

        # Execute chosen menu item
        else:
            try:
                choice = int(choice)
                menu_item = main_menu.get(choice)
                if menu_item:
                    function = menu_item['function']
                    navigation_stack.push(function)
                else:
                    raise ValueError
            except ValueError:
                logger.error("Please enter a valid choice.")


if __name__ == "__main__":
    main()
