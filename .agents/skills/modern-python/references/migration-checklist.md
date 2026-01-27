# Migration Checklist

Step-by-step guide for migrating existing Python projects to modern tooling.

## Pre-Migration Assessment

- [ ] Identify current Python version
- [ ] List all dependencies (requirements.txt, setup.py, etc.)
- [ ] Note dev/test dependencies separately
- [ ] Check for custom scripts/tooling
- [ ] Verify CI/CD configuration

## Phase 1: uv Setup

### From requirements.txt

```bash
# Initialize uv
uv init --bare

# Add dependencies
uv add -r requirements.txt

# Add dev dependencies (if separate)
uv add --group dev -r requirements-dev.txt

# Verify
uv sync
uv run python -c "import myproject"
```

### From setup.py / setup.cfg

```bash
# Initialize
uv init --bare

# Copy metadata to pyproject.toml manually:
# - name, version, description, author
# - Move install_requires to dependencies

# Add dependencies via uv add
uv add requests httpx  # from install_requires

# Add dev dependencies
uv add --group dev pytest ruff

# Delete old files
rm setup.py setup.cfg MANIFEST.in
```

### From Poetry

```bash
# Initialize
uv init --bare

# Import from pyproject.toml:
# - Copy [project] metadata
# - Convert [tool.poetry.dependencies] to dependencies
# - Convert dev-dependencies to [dependency-groups]

# Re-lock
rm poetry.lock
uv lock

# Delete poetry-specific sections
# Remove [tool.poetry.*] from pyproject.toml
```

### Cleanup

- [ ] Delete `requirements.txt`, `requirements-dev.txt`
- [ ] Delete `setup.py`, `setup.cfg`, `MANIFEST.in`
- [ ] Delete old lock files (`Pipfile.lock`, `poetry.lock`)
- [ ] Delete old virtual environments (`venv/`, `.venv/`)
- [ ] Add `uv.lock` to git
- [ ] Add `.venv/` to `.gitignore`

## Phase 2: Ruff Migration

### From flake8 + black + isort

```bash
# Remove old tools
uv remove flake8 black isort 2>/dev/null || true

# Add ruff
uv add --group lint ruff

# Delete old configs
rm -f .flake8 .isort.cfg

# Add ruff config to pyproject.toml
```

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D", "S101"]
```

```bash
# Apply fixes
uv run ruff check --fix .
uv run ruff format .

# Remove old tool sections from pyproject.toml
# [tool.black], [tool.isort]
```

## Phase 3: Type Checker Migration

### From mypy / pyright

```bash
# Remove old type checker
uv remove mypy pyright 2>/dev/null || true

# Add ty
uv add --group lint ty

# Delete old configs
rm -f mypy.ini pyrightconfig.json
```

```toml
[tool.ty.environment]
python-version = "3.11"

[tool.ty.terminal]
error-on-warning = true

[tool.ty.src]
include = ["src", "tests"]
```

```bash
# Run ty
uv run ty check src/

# Remove old sections from pyproject.toml
# [tool.mypy], [tool.pyright]
```

## Phase 4: Pre-commit Migration

### From pre-commit to prek

```bash
# Install prek
uv tool install prek

# Reinstall hooks
prek install -f

# Update config for prek features (optional)
```

```yaml
# Optional: Use builtin hooks
repos:
  - repo: builtin  # prek-only, faster
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
```

## Phase 5: CI/CD Updates

### GitHub Actions

```yaml
# Before
- uses: actions/setup-python@v4
  with:
    python-version: '3.11'
- run: pip install -r requirements.txt

# After
- uses: astral-sh/setup-uv@v7
- run: uv sync --frozen
```

### Makefile

```makefile
# Before
.PHONY: install
install:
	pip install -r requirements.txt

# After
.PHONY: dev
dev:
	uv sync --all-groups
	uv run prek install
```

## Phase 6: Testing Updates

```toml
[dependency-groups]
test = ["pytest>=8.0", "pytest-cov", "coverage[toml]"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=myproject --cov-fail-under=80"
```

```bash
# Update test commands
uv run pytest
```

## Final Checklist

### Files to Delete

- [ ] `requirements.txt`, `requirements-dev.txt`
- [ ] `setup.py`, `setup.cfg`, `MANIFEST.in`
- [ ] `.flake8`, `.isort.cfg`
- [ ] `mypy.ini`, `pyrightconfig.json`
- [ ] `Pipfile`, `Pipfile.lock`
- [ ] `poetry.lock`
- [ ] Old `venv/` directories

### Files to Add/Update

- [ ] `pyproject.toml` (consolidated config)
- [ ] `uv.lock` (dependency lock)
- [ ] `.python-version` (Python version pin)
- [ ] Updated `.gitignore`
- [ ] Updated CI workflows

### Config to Remove from pyproject.toml

- [ ] `[tool.black]`
- [ ] `[tool.isort]`
- [ ] `[tool.mypy]`
- [ ] `[tool.pyright]`
- [ ] `[tool.poetry.*]`

### Config to Add to pyproject.toml

- [ ] `[dependency-groups]`
- [ ] `[tool.ruff]`
- [ ] `[tool.ty]`
- [ ] `[build-system]` with `uv_build`

## Verification

```bash
# Clean install test
rm -rf .venv uv.lock
uv sync
uv run pytest
uv run ruff check .
uv run ty check src/
```

## Common Issues

### Import Errors After Migration

```bash
# Ensure src layout is configured
uv sync
uv run python -c "import myproject"
```

### Lock File Conflicts

```bash
# Regenerate lock
rm uv.lock
uv lock
```

### Type Errors with ty

ty is stricter than mypy. Options:
1. Fix the actual type errors
2. Add to `[tool.ty.rules]` with `"warn"` or `"ignore"`
3. Use `# type: ignore` comments

## References

- [uv Migration](https://docs.astral.sh/uv/guides/migrate/)
- [Ruff Migration](https://docs.astral.sh/ruff/migration/)
