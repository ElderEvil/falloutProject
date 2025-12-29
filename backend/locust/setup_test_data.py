"""Setup test data for Locust performance tests.

This script creates test users and initial vaults for load testing.
Run this before starting performance tests.

Usage:
    python -m locust.setup_test_data
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv

backend_dir = Path(__file__).parent.parent
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✓ Loaded environment from {env_file}")
else:
    print(f"⚠ No .env file found at {env_file}")
    print("  Make sure your environment variables are set!")

from app import crud  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import async_session_maker  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.schemas.vault import VaultNumber  # noqa: E402


async def create_test_user():
    """Create a test user for performance testing."""
    async with async_session_maker() as session:
        # Check if user already exists
        existing_user = await crud.user.get_by_email(session, email=settings.EMAIL_TEST_USER)

        if existing_user:
            print(f"✓ Test user already exists: {settings.EMAIL_TEST_USER}")
            return existing_user

        # Create test user
        user_in = UserCreate(
            username=settings.EMAIL_TEST_USER,
            email=settings.EMAIL_TEST_USER,
            password="testpassword",  # Use a simple password for testing
            is_superuser=False,
        )

        user = await crud.user.create(db_session=session, obj_in=user_in)
        print(f"✓ Created test user: {user.email}")
        return user


async def create_initial_vaults(user_id, num_vaults: int = 5):
    """Create initial vaults for the test user."""
    async with async_session_maker() as session:
        # Get existing vaults
        existing_vaults = await crud.vault.get_vaults_with_room_and_dweller_count(db_session=session, user_id=user_id)

        if len(existing_vaults) >= num_vaults:
            print(f"✓ Test user already has {len(existing_vaults)} vaults")
            return existing_vaults

        # Create vaults
        created_vaults = []
        for i in range(num_vaults - len(existing_vaults)):
            vault_number = 100 + i  # Start from vault 100
            vault = await crud.vault.initiate(
                db_session=session, obj_in=VaultNumber(number=vault_number), user_id=user_id
            )
            created_vaults.append(vault)
            print(f"✓ Created vault #{vault_number}")

        return existing_vaults + created_vaults


async def setup():
    """Main setup function."""
    print("\n" + "=" * 60)
    print("Setting up test data for Locust performance tests")
    print("=" * 60 + "\n")

    try:
        # Create test user
        user = await create_test_user()

        # Create initial vaults
        vaults = await create_initial_vaults(user.id, num_vaults=5)

        print("\n" + "=" * 60)
        print("Setup Complete!")
        print("=" * 60)
        print(f"\nTest User: {user.email}")
        print("Password: testpassword")
        print(f"Vaults: {len(vaults)}")
        print("\nYou can now run Locust tests:")
        print("  ./backend/locust/run_tests.sh web")
        print("\n")

    except Exception as e:  # noqa: BLE001
        print(f"\n❌ Error during setup: {e}")
        import traceback  # noqa: PLC0415

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(setup())
