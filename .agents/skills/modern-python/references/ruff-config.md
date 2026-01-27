# Ruff Configuration Reference

**Documentation**: [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/)

## Configuration Files

Priority order:
1. `.ruff.toml` (highest)
2. `ruff.toml`
3. `pyproject.toml` (most common)

## Basic Structure

```toml
[tool.ruff]
line-length = 100
indent-width = 4
target-version = "py312"
exclude = [".venv", "build", "dist"]

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
```

## Rule Selection

### Common Rule Categories

| Code | Category | Description |
|------|----------|-------------|
| `E` | pycodestyle | PEP 8 errors |
| `W` | pycodestyle | PEP 8 warnings |
| `F` | Pyflakes | Logical errors |
| `I` | isort | Import sorting |
| `N` | pep8-naming | Naming conventions |
| `D` | pydocstyle | Docstrings |
| `UP` | pyupgrade | Modern syntax |
| `B` | flake8-bugbear | Common bugs |
| `C4` | comprehensions | Comprehension improvements |
| `S` | flake8-bandit | Security |
| `T20` | flake8-print | Print statements |
| `RUF` | Ruff-specific | Ruff rules |

### Recommended Configurations

**Conservative:**
```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"]
```

**Moderate:**
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "C4"]
```

**Strict:**
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "C4", "D", "S", "SIM", "RET"]
```

### Why NOT `select = ["ALL"]`

**Avoid** - causes issues:
- Enables unstable/preview rules
- Includes conflicting rules
- Too noisy (800+ rules)
- Breaks on upgrades

**Better approach:**
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B"]
extend-select = ["D", "S"]  # Add gradually
```

## Common Ignores

```toml
[tool.ruff.lint]
ignore = [
    "E501",   # Line too long (formatter handles)
    "D203",   # Conflicts with D211
    "D213",   # Conflicts with D212
    "COM812", # Conflicts with formatter
    "ISC001", # Conflicts with formatter
]
```

## Per-File Ignores

```toml
[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]  # Unused imports OK
"tests/**/*.py" = [
    "D",       # No docstrings
    "S101",    # Asserts OK
    "PLR2004", # Magic values OK
]
"scripts/*.py" = ["T20"]  # Print OK
```

## Format Configuration

```toml
[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
skip-magic-trailing-comma = false
docstring-code-format = true
```

## isort Settings

```toml
[tool.ruff.lint.isort]
known-first-party = ["myproject"]
force-single-line = false
lines-after-imports = 2
```

## pydocstyle Settings

```toml
[tool.ruff.lint.pydocstyle]
convention = "google"  # or "numpy", "pep257"
```

## Complexity Limits

```toml
[tool.ruff.lint.mccabe]
max-complexity = 8

[tool.ruff.lint.pylint]
max-branches = 12
max-returns = 6
max-positional-args = 5
```

## Complete Example

```toml
[tool.ruff]
line-length = 100
indent-width = 4
target-version = "py311"
exclude = [
    ".venv", "build", "dist", "node_modules",
    ".git", "__pycache__", ".mypy_cache",
]
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle
    "F",      # Pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # comprehensions
    "SIM",    # simplify
]
ignore = ["E501"]
fixable = ["ALL"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/**/*.py" = ["D", "S101", "PLR2004"]

[tool.ruff.lint.isort]
known-first-party = ["myproject"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true
```

## CLI Usage

```bash
# Lint
ruff check .
ruff check --fix .
ruff check --unsafe-fixes .

# Format
ruff format .
ruff format --check .
ruff format --diff .

# Combined workflow
ruff check --fix . && ruff format .

# Info
ruff rule E501
ruff check --show-settings
```

## Integration with uv

```bash
# Add to project
uv add --dev ruff

# Run via uv
uv run ruff check .
uv run ruff format .
```

## Migration

### From Black
```toml
[tool.ruff]
line-length = 88
[tool.ruff.format]
quote-style = "double"
```

### From Flake8
```toml
[tool.ruff.lint]
select = ["E", "F", "W", "C90"]
```

### From isort
```toml
[tool.ruff.lint]
select = ["I"]
[tool.ruff.lint.isort]
known-first-party = ["myproject"]
```
