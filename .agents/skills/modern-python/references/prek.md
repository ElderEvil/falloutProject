# Prek - Fast Pre-commit Hooks

Prek is a Rust-based reimplementation of pre-commit. 10x faster, same config format.

**Repository**: [https://github.com/j178/prek](https://github.com/j178/prek)
**Documentation**: [https://prek.j178.dev/](https://prek.j178.dev/)

## Installation

```bash
# Standalone (recommended)
curl -LsSf https://github.com/j178/prek/releases/download/v0.3.0/prek-installer.sh | sh

# Via uv
uv tool install prek

# Via cargo
cargo install --locked prek
```

## Migration from pre-commit

```bash
# Replace command, keep config
prek install -f
```

Your `.pre-commit-config.yaml` works unchanged.

## Configuration

### Basic Structure

```yaml
fail_fast: false
default_install_hook_types: [pre-commit, pre-push]

repos:
  # Built-in hooks (prek-only, fastest)
  - repo: builtin
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json

  # Remote repository
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]

  # Local hooks
  - repo: local
    hooks:
      - id: test
        name: Run tests
        entry: make test
        language: system
        pass_filenames: false
```

### Built-in Hooks (`repo: builtin`)

Rust implementations - offline, zero-setup:

| Hook | Description |
|------|-------------|
| `trailing-whitespace` | Trim trailing whitespace |
| `end-of-file-fixer` | Ensure newline at EOF |
| `check-yaml` | Validate YAML syntax |
| `check-json` | Validate JSON syntax |
| `check-toml` | Validate TOML syntax |
| `check-added-large-files` | Prevent large files |
| `mixed-line-ending` | Normalize line endings |
| `detect-private-key` | Detect private keys |
| `no-commit-to-branch` | Protect branches |

### Priority (Parallel Execution)

```yaml
repos:
  - repo: local
    hooks:
      - id: format
        priority: 0   # Runs first
        
      - id: lint
        priority: 10  # Runs after format
        
      - id: test
        priority: 20  # Runs last
        stages: [pre-push]
```

Same priority = concurrent execution.

### Glob Patterns (prek-only)

```yaml
# Instead of regex
files:
  glob: src/**/*.py

exclude:
  glob:
    - dist/**
    - build/**
```

## Commands

```bash
# Run all hooks
prek run

# Run specific hooks
prek run ruff black

# Run on all files
prek run --all-files

# Run on specific directory
prek run --directory src/

# Run on last commit
prek run --last-commit

# List configured hooks
prek list

# Update hook versions
prek auto-update
prek auto-update --cooldown-days 7  # Security

# Install git hooks
prek install
prek install --hook-type pre-push
```

## Complete Example

```yaml
minimum_prek_version: '0.2.0'
fail_fast: false
default_install_hook_types: [pre-commit, pre-push]

repos:
  - repo: builtin
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
        priority: 0
      - id: ruff-format
        priority: 0

  - repo: local
    hooks:
      - id: ty
        name: Type check
        entry: uv run ty check src/
        language: system
        types: [python]
        pass_filenames: false
        priority: 10

      - id: test
        name: Run tests
        entry: uv run pytest
        language: system
        types: [python]
        pass_filenames: false
        stages: [pre-push]
        priority: 20
```

## GitHub Actions

```yaml
name: Prek
on: [push, pull_request]

jobs:
  prek:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: j178/prek-action@v1
```

## Key Benefits

- **10x faster** than pre-commit
- **Parallel execution** via priority system
- **Auto-install** Python/Node/Go/Rust toolchains
- **Built-in hooks** in Rust (no Python needed)
- **Workspace mode** for monorepos
- **Same config** as pre-commit

## References

- [Documentation](https://prek.j178.dev/)
- [Configuration](https://prek.j178.dev/configuration/)
- [Built-in Hooks](https://prek.j178.dev/builtin/)
