# PEP 723 - Inline Script Metadata

PEP 723 enables embedding dependencies directly in single-file Python scripts.

**Official Spec**: [https://peps.python.org/pep-0723/](https://peps.python.org/pep-0723/)

## Basic Syntax

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests<3",
#   "rich",
# ]
# ///

import requests
from rich.pretty import pprint

response = requests.get("https://api.github.com")
pprint(response.json())
```

## Format Rules

1. **Start marker**: `# /// script`
2. **End marker**: `# ///`
3. **Content**: TOML format, each line prefixed with `#`
4. **Encoding**: UTF-8

## Standard Fields

### `dependencies`

```python
# dependencies = [
#   "requests<3",              # Version constraint
#   "rich",                    # Latest version
#   "numpy>=1.20,<2.0",       # Range
#   "pandas[excel]",           # With extras
#   "pkg @ git+https://github.com/user/repo.git",  # From git
#   "pywin32 ; sys_platform == 'win32'",  # Platform-specific
# ]
```

### `requires-python`

```python
# requires-python = ">=3.11"
# requires-python = ">=3.10,<3.13"
# requires-python = "==3.12.*"
```

## Tool Configuration

```python
# /// script
# dependencies = ["requests"]
# [tool.uv]
# exclude-newer = "2026-01-01T00:00:00Z"
# ///
```

## Using with uv

### Run Script

```bash
# Dependencies auto-installed
uv run script.py

# With specific Python
uv run --python 3.12 script.py
```

### Create Script

```bash
uv init --script example.py --python 3.12
```

### Manage Dependencies

```bash
# Add dependency
uv add --script example.py requests rich

# Remove dependency
uv remove --script example.py requests

# Lock dependencies
uv lock --script example.py
```

## Executable Shebang

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///

import httpx
print(httpx.get("https://example.com").text)
```

```bash
chmod +x script.py
./script.py
```

## Complete Example

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx>=0.27",
#   "pydantic>=2.0",
#   "rich",
# ]
# [tool.uv]
# exclude-newer = "2026-01-01T00:00:00Z"
# ///

"""Fetch and display user data from API."""

import httpx
from pydantic import BaseModel
from rich import print

class User(BaseModel):
    id: int
    name: str
    email: str

def main() -> None:
    response = httpx.get("https://jsonplaceholder.typicode.com/users/1")
    user = User(**response.json())
    print(f"[green]User:[/green] {user.name} ({user.email})")

if __name__ == "__main__":
    main()
```

## When to Use

| Scenario | Use PEP 723 | Use pyproject.toml |
|----------|-------------|-------------------|
| Single-file utility | Yes | No |
| Shareable script | Yes | No |
| Multi-file project | No | Yes |
| Reusable package | No | Yes |
| Has tests | No | Yes |

## References

- [PEP 723](https://peps.python.org/pep-0723/)
- [uv Scripts Guide](https://docs.astral.sh/uv/guides/scripts/)
- [Packaging Spec](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
