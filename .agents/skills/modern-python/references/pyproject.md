# pyproject.toml Complete Reference

Based on [trailofbits/cookiecutter-python](https://github.com/trailofbits/cookiecutter-python) template.

## Build System

```toml
[build-system]
requires = ["uv_build>=0.9.0,<0.10.0"]
build-backend = "uv_build"
```

**Why `uv_build`**: Simpler than hatchling, sufficient for most cases, integrates seamlessly with uv.

## Project Metadata

```toml
[project]
name = "myproject"
version = "0.1.0"
description = "Project description"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["python", "project"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "httpx>=0.27.0",
    "rich>=13.0.0",
]

[project.urls]
Homepage = "https://github.com/user/project"
Documentation = "https://project.readthedocs.io"
Repository = "https://github.com/user/project"

[project.scripts]
my-cli = "myproject:main"

[project.entry-points."myproject.plugins"]
plugin-name = "myproject.plugins:Plugin"
```

## Dependency Groups (PEP 735)

**Modern approach** - replaces `[project.optional-dependencies]` for dev tools:

```toml
[dependency-groups]
dev = [
    {include-group = "lint"},
    {include-group = "test"},
    {include-group = "doc"},
]
lint = [
    "ruff~=0.14.0",
    "ty>=0.0.8",
]
test = [
    "pytest>=8.0",
    "pytest-cov",
    "pytest-timeout",
    "coverage[toml]",
]
doc = ["pdoc"]
audit = ["pip-audit"]
```

**Install**: `uv sync --group dev` or `uv sync --all-groups`

## Ruff Configuration

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.format]
line-ending = "lf"
quote-style = "double"

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "D203",    # Conflicts with D211
    "D213",    # Conflicts with D212
    "COM812",  # Conflicts with formatter
    "ISC001",  # Conflicts with formatter
]

[tool.ruff.lint.mccabe]
max-complexity = 8

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.pylint]
max-branches = 12
max-returns = 6
max-positional-args = 5

[tool.ruff.lint.per-file-ignores]
"test/**/*.py" = [
    "D",        # No docstrings in tests
    "S101",     # Asserts expected in tests
    "PLR2004",  # Magic values in tests
]
"**/conftest.py" = ["D"]
```

## Ty Configuration (Type Checker)

```toml
[tool.ty.terminal]
error-on-warning = true

[tool.ty.environment]
python-version = "3.11"

[tool.ty.src]
include = ["src", "test"]

[tool.ty.rules]
possibly-unresolved-reference = "error"
unused-ignore-comment = "warn"
```

## Pytest Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["test"]
python_files = ["test_*.py"]
addopts = "--durations=10"
```

## Coverage Configuration

```toml
[tool.coverage.run]
source = ["src"]
branch = true
omit = ["*/tests/*", "*/_cli.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
fail_under = 80
```

## Complete Template

```toml
[project]
name = "myproject"
version = "0.1.0"
description = "My awesome project"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "Your Name", email = "you@example.com"}]
dependencies = []

[dependency-groups]
dev = [{include-group = "lint"}, {include-group = "test"}]
lint = ["ruff~=0.14.0", "ty>=0.0.8"]
test = ["pytest>=8.0", "pytest-cov", "coverage[toml]"]

[build-system]
requires = ["uv_build>=0.9.0"]
build-backend = "uv_build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"test/**/*.py" = ["D", "S101", "PLR2004"]

[tool.ty.environment]
python-version = "3.11"

[tool.ty.terminal]
error-on-warning = true

[tool.pytest.ini_options]
testpaths = ["test"]
addopts = "--cov=myproject --cov-fail-under=80"

[tool.coverage.run]
source = ["src"]
branch = true
```

## References

- [PEP 735 - Dependency Groups](https://peps.python.org/pep-0735/)
- [trailofbits/cookiecutter-python pyproject.toml](https://github.com/trailofbits/cookiecutter-python/blob/main/%7B%7Bcookiecutter.project_slug%7D%7D/pyproject.toml)
- [uv Documentation](https://docs.astral.sh/uv/)
