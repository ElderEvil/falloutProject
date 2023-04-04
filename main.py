from Game.Vault.Vault import Vault
from Game.Vault.utilities.Navigation import NavigationStack
from logger_settings import logger


def get_valid_int_input(prompt: str, lower_bound: int, upper_bound: int):
    while True:
        try:
            value = int(input(prompt))
            if lower_bound <= value <= upper_bound:
                return value
            raise ValueError(f"Value must be between {lower_bound} and {upper_bound}")
        except ValueError:
            logger.error(f"Please enter a valid number between {lower_bound} and {upper_bound}.")


def display_menu(actions):
    print("What do you want to do?")
    for key, value in actions.items():
        print(f"{key}. {value['name']}")


def navigate_menu(actions: dict[int, dict], stack: NavigationStack):
    while True:
        # Display menu
        display_menu(actions)

        # Get user input
        choice = get_valid_int_input("Enter the number of your choice: ", 0, len(actions) - 1)

        # Execute action
        action = actions.get(choice)

        if action:
            if 'function' in action:
                stack.push(action)
                action['function']()
            elif 'back' in action:
                stack.pop()
                if not stack.is_empty():
                    stack.current()['function']()
            elif 'exit' in action:
                return
        else:
            print("Invalid choice. Please try again.")


def main():
    # Ask for the number of the vault
    vault_num = get_valid_int_input('Enter the number of your vault: ', 1, 999)
    vault = Vault(f"Vault {vault_num}")
    vault.show_status(True)

    def show_dwellers():
        for d in vault.dwellers:
            print(d)
        return vault.dwellers

    def build_room():
        room_types = vault.get_available_room_types()
        print("Choose room to build")
        for i, room in enumerate(room_types):
            print(f"{i}. {room.name}")
        choice = int(input())
        room = room_types[choice]
        vault.construct_room(room)
        return None

    def manage_dwellers():
        menu_items = {
            1: {"name": "Move dweller to another room", "function": move_dweller},
            2: {"name": "Remove dweller", "function": remove_dweller},
            0: {"name": "Back", "function": None},
        }
        return menu_items

    def move_dweller():
        print("Not implemented yet")
        return None

    def remove_dweller():
        dwellers = vault.dwellers
        print("Choose dweller to kick")
        for i, dweller in enumerate(dwellers):
            print(f"{i}. {dweller.full_name}")
        choice = int(input())
        dweller = dwellers[choice]
        vault.remove_dweller(dweller)
        return None

    # Define main menu items

    stack = NavigationStack()
    # navigate_menu(actions, stack)


if __name__ == '__main__':
    main()
