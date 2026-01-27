# Testing Configuration

## pytest Configuration

### pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
    "--durations=10",
]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning",
]
```

### With Coverage

```toml
[tool.pytest.ini_options]
addopts = "--cov=myproject --cov-report=term-missing --cov-fail-under=80"
```

## Coverage Configuration

```toml
[tool.coverage.run]
source = ["src"]
branch = true
parallel = true
omit = [
    "*/tests/*",
    "*/__main__.py",
    "*/_cli.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "@abstractmethod",
]
fail_under = 80
show_missing = true
skip_covered = true

[tool.coverage.html]
directory = "htmlcov"
```

## Dependency Groups

```toml
[dependency-groups]
test = [
    "pytest>=8.0",
    "pytest-cov",
    "pytest-timeout",
    "pytest-asyncio",
    "coverage[toml]",
]
```

## Running Tests

```bash
# Basic
uv run pytest

# With coverage
uv run pytest --cov=myproject

# Verbose
uv run pytest -v

# Specific test
uv run pytest tests/test_api.py::test_login

# Stop on first failure
uv run pytest -x

# Show local variables
uv run pytest -l

# Parallel execution
uv run pytest -n auto  # requires pytest-xdist
```

## Makefile Target

```makefile
.PHONY: test
test:
	uv sync --group test
	uv run pytest -svv --timeout=300 --cov=$(MODULE) $(TEST_ARGS)
	uv run coverage report -m --fail-under 80
```

## Test Structure

```
project/
├── src/
│   └── myproject/
│       ├── __init__.py
│       └── core.py
└── tests/
    ├── conftest.py
    ├── test_core.py
    └── integration/
        └── test_api.py
```

## conftest.py Example

```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

@pytest.fixture(scope="session")
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()
```

## Async Testing

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result == expected
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [coverage.py](https://coverage.readthedocs.io/)
