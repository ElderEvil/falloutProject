"""Run inside the built backend image with networking disabled and a read-only filesystem."""

# ruff: file-ignore[INP001, S101, S106, S603]

import importlib.util
import os
import subprocess
from pathlib import Path

assert os.getuid() == 1000, "Runtime must use appuser"
for name in ("pytest", "coverage", "fakeredis", "ruff", "ty", "prek"):
    assert importlib.util.find_spec(name) is None, (
        f"Development package shipped: {name}"
    )
for name in ("app/tests", "tests", ".env", ".env.local", ".env.production"):
    assert not Path("/app", name).exists(), f"Non-runtime file shipped: {name}"
assert Path("/app/app/data").is_dir()
assert Path("/app/alembic.ini").is_file()
assert Path("/CHANGELOG.md").is_file()

os.environ.update(
    SECRET_KEY="container-smoke-test-key",
    EMAIL_TEST_USER="test@example.com",
    FIRST_SUPERUSER_USERNAME="admin",
    FIRST_SUPERUSER_EMAIL="admin@example.com",
    FIRST_SUPERUSER_PASSWORD="container-smoke-password",
    USERS_OPEN_REGISTRATION="false",
    POSTGRES_SERVER="localhost",
    POSTGRES_USER="postgres",
    POSTGRES_PASSWORD="postgres",
    POSTGRES_DB="fallout",
    REDIS_HOST="localhost",
    REDIS_PORT="6379",
    LOGFIRE_SEND_TO_LOGFIRE="false",
)
for module in ("main", "app.api.tasks"):
    __import__(module)
for command in ("uvicorn", "alembic", "dramatiq", "periodiq", "fo-cli"):
    subprocess.run(
        ["/bin/uv", "run", "--offline", command, "--help"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
print("Production backend image checks passed")
