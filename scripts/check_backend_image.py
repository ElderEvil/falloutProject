"""Run inside the built backend image with networking disabled and a read-only filesystem."""

import asyncio
import importlib.util
import os
import platform
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvloop
from app.core.async_runtime import run_async

image_python = subprocess.check_output(
    ["/usr/local/bin/python", "--version"], text=True
).strip()
assert image_python == f"Python {platform.python_version()}", (
    f"Baked environment uses Python {platform.python_version()}, but the image provides {image_python}"
)
assert os.getuid() == 1000, "Runtime must use appuser"
for name in ("pytest", "coverage", "fakeredis", "ruff", "ty", "prek"):
    assert importlib.util.find_spec(name) is None, f"Dev package shipped: {name}"
for name in ("app/tests", "tests", ".env", ".env.local", ".env.production"):
    assert not Path("/app", name).exists(), f"Non-runtime file shipped: {name}"
assert Path("/app/app/data").is_dir()
assert Path("/app/alembic.ini").is_file()
assert Path("/app/alembic-legacy.ini").is_file()
assert Path("/CHANGELOG.md").is_file()

# Vault Radio Hour degrades to raw WAV without this binary, so the production
# image must ship it.
ffmpeg = shutil.which("ffmpeg")
assert ffmpeg, "ffmpeg is missing from the runtime image"
subprocess.run(
    [ffmpeg, "-version"],
    check=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

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
# Jev is lazy-loaded by chat: importing the API alone does not exercise its SDK.
__import__("pydantic_ai.models.typesafe")


async def check_async_work() -> asyncio.AbstractEventLoop:
    """Exercise task scheduling and timers on the baked runtime's event loop."""
    assert await asyncio.create_task(asyncio.sleep(0.001, result="ready")) == "ready"
    return asyncio.get_running_loop()


api_loop = uvloop.run(check_async_work())
assert isinstance(api_loop, uvloop.Loop), "API async work must execute on uvloop"
with ThreadPoolExecutor(max_workers=1) as worker:
    worker_loop = worker.submit(run_async, check_async_work()).result(timeout=10)
    next_loop = worker.submit(run_async, check_async_work()).result(timeout=10)
    assert isinstance(worker_loop, asyncio.AbstractEventLoop)
    assert worker_loop is next_loop, (
        "Consecutive worker calls must reuse the thread's event loop"
    )
    assert worker_loop is not api_loop and not worker_loop.is_closed()
    worker.submit(worker_loop.close).result(timeout=10)

for command in ("uvicorn", "alembic", "dramatiq", "periodiq", "fo-cli"):
    subprocess.run(
        ["/bin/uv", "run", "--offline", command, "--help"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
print("Production backend image checks passed")
