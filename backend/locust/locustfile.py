"""Main locustfile for Fallout Shelter API load testing.

This file defines different user behaviors and load test scenarios.

Usage:
    # Basic usage with web UI
    locust -f backend/locust/locustfile.py --host http://localhost:8000

    # Headless mode with specific parameters
    locust -f backend/locust/locustfile.py --host http://localhost:8000 \
        --users 10 --spawn-rate 2 --run-time 5m --headless

    # Use specific user class
    locust -f backend/locust/locustfile.py --host http://localhost:8000 \
        GamePlayer --users 50 --spawn-rate 5

Environment Variables:
    LOCUST_HOST: API host URL (default: http://localhost:8000)
    LOCUST_TEST_USER_EMAIL: Test user email
    LOCUST_TEST_USER_PASSWORD: Test user password
"""

from config import config
from tasks.dweller_tasks import DwellerTaskSet
from tasks.game_tasks import GameTaskSet
from tasks.vault_tasks import VaultTaskSet
from utils import AuthMixin

from locust import HttpUser, between, events, task


@events.init_command_line_parser.add_listener
def _(parser):
    """Add custom command line arguments."""
    parser.add_argument(
        "--test-user-email",
        type=str,
        default=config.test_user_email,
        help="Test user email for authentication",
    )
    parser.add_argument(
        "--test-user-password",
        type=str,
        default=config.test_user_password,
        help="Test user password for authentication",
    )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):  # noqa: ARG001
    """Hook that runs when test starts."""
    print(f"\n{'=' * 60}")
    print(f"Starting load test against: {environment.host}")
    print(f"Test user: {config.test_user_email}")
    print(f"{'=' * 60}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):  # noqa: ARG001
    """Hook that runs when test stops."""
    print(f"\n{'=' * 60}")
    print("Load test completed!")
    print(f"{'=' * 60}\n")


class BaseVaultUser(AuthMixin, HttpUser):
    """Base user class with authentication."""

    abstract = True
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a simulated user starts."""
        # Login to get access token
        self.login(config.test_user_email, config.test_user_password)

        # Initialize data structures
        self.vault_ids = []
        self.dweller_ids = []

        # Get initial list of vaults
        response = self.authenticated_get("/api/v1/vaults/", name="Initial vault list")
        if response.status_code == 200:
            vaults = response.json()
            self.vault_ids = [v["id"] for v in vaults]


class CasualPlayer(BaseVaultUser):
    """
    Casual player - mostly reads data, occasional writes.

    This user simulates a player who:
    - Checks their vaults frequently
    - Looks at dwellers and rooms
    - Occasionally triggers game actions
    - Rarely creates new content
    """

    weight = 7  # 70% of users are casual players

    tasks = {
        VaultTaskSet: 5,  # 50% vault operations
        DwellerTaskSet: 3,  # 30% dweller operations
        GameTaskSet: 2,  # 20% game operations
    }


class ActivePlayer(BaseVaultUser):
    """
    Active player - balanced mix of reads and writes.

    This user simulates a player who:
    - Frequently manages vaults and dwellers
    - Creates new content regularly
    - Triggers game ticks often
    - Actively plays the game
    """

    weight = 2  # 20% of users are active players

    tasks = {
        VaultTaskSet: 4,  # 40% vault operations (includes creates)
        DwellerTaskSet: 3,  # 30% dweller operations
        GameTaskSet: 3,  # 30% game operations
    }


class PowerUser(BaseVaultUser):
    """
    Power user - heavy operations, creates lots of content.

    This user simulates a player who:
    - Creates multiple vaults
    - Manages many dwellers
    - Constantly triggers game mechanics
    - Stress tests the system
    """

    weight = 1  # 10% of users are power users
    wait_time = between(0.5, 1.5)  # Faster actions

    tasks = {
        VaultTaskSet: 3,  # Includes many creates
        DwellerTaskSet: 4,  # Creates many dwellers
        GameTaskSet: 3,  # Heavy game tick usage
    }


class GamePlayer(BaseVaultUser):
    """
    Game-focused player - focuses on game loop and mechanics.

    This user simulates a player who:
    - Primarily interacts with game mechanics
    - Triggers ticks, checks incidents
    - Manages quests and objectives
    - Less focused on CRUD operations
    """

    weight = 1

    tasks = {
        GameTaskSet: 7,  # 70% game operations
        VaultTaskSet: 2,  # 20% vault checks
        DwellerTaskSet: 1,  # 10% dweller checks
    }


class ReadOnlyPlayer(BaseVaultUser):
    """
    Read-only player - only views data, no mutations.

    Useful for testing read performance and caching.
    """

    @task(5)
    def view_vaults(self):
        """View all vaults."""
        response = self.authenticated_get("/api/v1/vaults/", name="GET /vaults/")
        if response.status_code == 200:
            vaults = response.json()
            self.vault_ids = [v["id"] for v in vaults]

    @task(3)
    def view_vault_details(self):
        """View vault details."""
        if self.vault_ids:
            vault_id = self.vault_ids[0]
            self.authenticated_get(f"/api/v1/vaults/{vault_id}", name="GET /vaults/{id}")

    @task(3)
    def view_game_state(self):
        """View game state."""
        if self.vault_ids:
            vault_id = self.vault_ids[0]
            self.authenticated_get(
                f"/api/v1/game/vaults/{vault_id}/game-state",
                name="GET /game/vaults/{id}/game-state",
            )

    @task(2)
    def view_dwellers(self):
        """View dwellers."""
        if self.vault_ids:
            vault_id = self.vault_ids[0]
            self.authenticated_get(
                f"/api/v1/dwellers/vault/{vault_id}/",
                name="GET /dwellers/vault/{id}/",
            )


# If you want to run a specific scenario, you can set it as default:
# Example: locust -f locustfile.py CasualPlayer
