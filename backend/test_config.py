"""Quick script to check what credentials Locust will use."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from locust.config import config  # noqa: E402

print("\n" + "=" * 60)
print("Locust Configuration Check")
print("=" * 60)
print(f"Test User Email: {config.test_user_email}")
print(f"Test User Password: {config.test_user_password}")
print(f"API Host: {config.host}")
print("=" * 60 + "\n")
