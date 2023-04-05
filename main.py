from Game.Vault.Vault import Vault
from utilities.menu_navigation import NavigationStack
from Game.logger_settings import logger


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


pip_boy = {
    1: {"name": "Quests", "function": "get_quests"},
    2: {"name": "Tasks", "function": "get_tasks"},
    3: {"name": "Storage", "function": "show_storage"},
    4: {"name": "Help", "function": "get_help"},
    5: {"name": "Settings", "function": "settings"},
}


def main():
    # Ask for the number of the vault
    vault_num = get_valid_int_input('Enter the number of your vault: ', 1, 999)
    vault = Vault(f"Vault {vault_num}")
    navigation_stack = NavigationStack()

    # Define menu items
    menu_items = {
        1: {"name": "Status", "function": vault.show_status},
        2: {"name": "Pip-Boy", "function": pip_boy},
        3: {"name": "Build room", "function": vault.get_available_room_types},
        0: {"name": "Exit", "function": exit},
    }

    # Main game loop
    while True:
        # Display current menu

        # Display menu and get user input
        display_menu(menu_items)
        choice = input("Enter the number of your choice (or 'b' to go back): ")

        # Check if user wants to go back
        if choice.lower() == 'b':
            navigation_stack.pop()

        # Execute chosen menu item
        else:
            try:
                choice = int(choice)
                menu_item = menu_items.get(choice)
                if menu_item:
                    function = menu_item['function']
                    navigation_stack.push(function)
                else:
                    raise ValueError
            except ValueError:
                logger.error("Please enter a valid choice.")


if __name__ == "__main__":
    main()
