# uv Command Reference

**Documentation**: [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

## Quick Reference

| Command | Purpose |
|---------|---------|
| `uv init` | Create project |
| `uv add` | Add dependency |
| `uv remove` | Remove dependency |
| `uv sync` | Install dependencies |
| `uv lock` | Update lockfile |
| `uv run` | Run command |
| `uvx` | Run tool |
| `uv python` | Manage Python |
| `uv build` | Build package |
| `uv publish` | Publish to PyPI |

## Project Initialization

```bash
# Application (default)
uv init my-app

# Library with src/ layout
uv init --lib my-lib

# Packaged CLI
uv init --package my-cli

# Minimal (just pyproject.toml)
uv init --bare my-minimal
```

## Dependency Management

### Adding Dependencies

```bash
# Basic
uv add httpx
uv add "httpx>=0.27"
uv add httpx requests aiohttp

# From requirements
uv add -r requirements.txt

# Dev/group dependencies
uv add --dev pytest
uv add --group lint ruff
uv add --group test pytest coverage

# Optional dependencies (extras)
uv add --optional network httpx

# From git
uv add git+https://github.com/encode/httpx
uv add git+https://github.com/encode/httpx --tag v0.27.0
uv add git+https://github.com/encode/httpx --branch main

# Editable local
uv add --editable ../my-package
```

### Removing Dependencies

```bash
uv remove httpx
uv remove --dev pytest
uv remove --group lint ruff
```

## Syncing Environment

```bash
# Basic sync
uv sync

# With groups
uv sync --group lint
uv sync --group lint --group test
uv sync --all-groups

# Without dev
uv sync --no-dev

# With extras
uv sync --extra network
uv sync --all-extras

# Exact (remove extraneous)
uv sync  # default behavior

# Frozen (from lockfile only)
uv sync --frozen
```

## Locking

```bash
# Update lockfile
uv lock

# Check freshness
uv lock --check

# Upgrade all
uv lock --upgrade

# Upgrade specific
uv lock --upgrade-package httpx
```

## Running Commands

```bash
# Run script
uv run script.py

# Run Python command
uv run python -c "print('hello')"

# Run installed tool
uv run pytest

# With specific Python
uv run --python 3.12 script.py

# With temporary dependencies
uv run --with httpx --with rich script.py

# Without sync
uv run --no-sync script.py

# Locked mode
uv run --locked script.py
```

## Tools

```bash
# Run tool (ephemeral)
uvx ruff check .
uvx black .
uvx [email protected] check .

# Install tool globally
uv tool install ruff
uv tool install [email protected]

# List installed
uv tool list

# Upgrade
uv tool upgrade ruff
uv tool upgrade --all

# Uninstall
uv tool uninstall ruff
```

## Python Management

```bash
# Install
uv python install 3.12
uv python install 3.11 3.12 3.13

# List
uv python list
uv python list --all-versions

# Find
uv python find 3.12

# Pin
uv python pin 3.12

# Uninstall
uv python uninstall 3.11
```

## Building & Publishing

```bash
# Build
uv build
uv build --wheel
uv build --sdist

# Publish
uv publish
uv publish --token $PYPI_TOKEN
```

## Export

```bash
# To requirements.txt
uv export -o requirements.txt

# With extras/groups
uv export --all-extras -o requirements.txt
uv export --group dev -o requirements-dev.txt

# No hashes
uv export --no-hashes -o requirements.txt
```

## pip Interface

```bash
# Install
uv pip install httpx
uv pip install -r requirements.txt

# Compile
uv pip compile requirements.in -o requirements.txt

# Sync
uv pip sync requirements.txt

# List/freeze
uv pip list
uv pip freeze

# Tree
uv pip tree
```

## Cache

```bash
uv cache dir
uv cache clean
uv cache prune
```

## Configuration

### pyproject.toml

```toml
[tool.uv]
managed = true
default-groups = ["dev", "lint"]

[tool.uv.sources]
httpx = { git = "https://github.com/encode/httpx" }
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `UV_CACHE_DIR` | Cache directory |
| `UV_NO_CACHE` | Disable cache |
| `UV_PYTHON_DOWNLOADS` | Python download policy |
| `UV_INDEX_URL` | Default index URL |
| `UV_OFFLINE` | Offline mode |

## Common Workflows

### New Project

```bash
uv init my-project
cd my-project
uv add httpx rich
uv add --dev pytest ruff
uv run python -m my_project
```

### CI/CD

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --frozen
uv run pytest
uv build
uv publish --token $PYPI_TOKEN
```

### Docker

```dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev
CMD ["uv", "run", "python", "-m", "my_app"]
```

## Best Practices

- Commit `uv.lock` to version control
- Use `uv sync --frozen` in CI
- Use `uv run` instead of activating venv
- Use `uvx` for one-off tool execution
- Use dependency groups for dev tools
- Never edit `uv.lock` manually
