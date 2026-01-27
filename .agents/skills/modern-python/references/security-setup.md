# Security Tools Setup

Based on [trailofbits/cookiecutter-python](https://github.com/trailofbits/cookiecutter-python).

## Overview

| Tool | Purpose | When It Runs |
|------|---------|--------------|
| **detect-private-key** | Secret detection | pre-commit (builtin) |
| **zizmor** | GitHub Actions security | CI workflow |
| **pip-audit** | Dependency vulnerabilities | CI, manual |
| **Dependabot** | Dependency updates | Scheduled |

## Pre-commit Security Hooks

### Using prek built-ins

```yaml
repos:
  - repo: builtin
    hooks:
      - id: detect-private-key
      - id: check-added-large-files
        args: [--maxkb=1024]
```

## Zizmor - GitHub Actions Security

Static analysis for GitHub Actions workflows.

### Workflow

```yaml
# .github/workflows/zizmor.yml
name: GitHub Actions Security Analysis

on:
  push:
    branches: ["main"]
  pull_request:

permissions: {}

jobs:
  zizmor:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      contents: read
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: zizmorcore/zizmor-action@v0.4.1
```

### What zizmor Detects

- Template injection vulnerabilities
- Credential leakage
- Excessive permissions
- Impostor commits
- Confusable git references

## pip-audit - Dependency Scanning

```bash
# Install
uv add --group audit pip-audit

# Run
uv run pip-audit

# CI usage
uv run pip-audit --strict
```

### In Dependency Groups

```toml
[dependency-groups]
audit = ["pip-audit"]
dev = [{include-group = "audit"}]
```

## Secure CI/CD Patterns

### Action Pinning

Always pin actions by SHA with version comment:

```yaml
# Good
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    persist-credentials: false

# Bad
- uses: actions/checkout@v4
```

### Minimal Permissions

```yaml
permissions: {}  # Top-level: deny all

jobs:
  build:
    permissions:
      contents: read  # Only what's needed
```

### Credential Protection

```yaml
- uses: actions/checkout@v4
  with:
    persist-credentials: false  # Prevent credential leakage
```

## SLSA Provenance for Releases

```yaml
# .github/workflows/release.yml
jobs:
  build:
    steps:
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: distributions
          path: dist/

  generate-provenance:
    needs: [build]
    permissions:
      id-token: write
      attestations: write
    steps:
      - uses: actions/download-artifact@v4
      - uses: actions/attest-build-provenance@v3
        with:
          subject-path: 'dist/*'

  publish:
    needs: [build, generate-provenance]
    permissions:
      id-token: write
    steps:
      - uses: pypa/gh-action-pypi-publish@v1
        with:
          attestations: true
```

## Dependabot Configuration

See [dependabot.md](./dependabot.md).

## Security Checklist

- [ ] Pin GitHub Actions by SHA
- [ ] Use `persist-credentials: false` on checkout
- [ ] Minimal permissions per job
- [ ] Add zizmor workflow
- [ ] Run pip-audit in CI
- [ ] Enable Dependabot
- [ ] Use Trusted Publishing for PyPI
- [ ] Generate SLSA provenance

## References

- [zizmor](https://github.com/zizmorcore/zizmor)
- [pip-audit](https://github.com/pypa/pip-audit)
- [SLSA](https://slsa.dev/)
- [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
