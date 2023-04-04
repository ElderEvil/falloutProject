from Game.Vault.Vault import Vault
from Game.Vault.utilities.Navigation import NavigationStack
from logger_settings import logger


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
    print("f. Go forward")


def main():
    # Ask for the number of the vault
    vault_num = get_valid_int_input('Enter the number of your vault: ', 1, 999)
    vault = Vault(f"Vault {vault_num}")
    navigation_stack = NavigationStack()
    navigation_stack.push(vault.show_status)

    # Define menu items
    menu_items = {
        1: {"name": "Show status", "function": vault.show_status},
        2: {"name": "Build room", "function": vault.get_available_room_types},
        3: {"name": "Manage dwellers", "function": vault.manage_dwellers},
        0: {"name": "Exit", "function": exit},
    }

    # Main game loop
    while True:
        # Display current menu
        current_menu_item = navigation_stack.current()
        current_menu_item(verbose=True)

        # Display menu and get user input
        display_menu(menu_items)
        choice = input("Enter the number of your choice (or 'b' to go back, 'f' to go forward): ")

        # Check if user wants to go back
        if choice.lower() == 'b':
            navigation_stack.pop()

        # Check if user wants to go forward
        elif choice.lower() == 'f':
            current_menu_item = navigation_stack.pop()
            if current_menu_item:
                navigation_stack.push(current_menu_item)

        # Otherwise, execute chosen menu item
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
