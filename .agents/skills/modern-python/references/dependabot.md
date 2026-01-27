# Dependabot Configuration

Automated dependency updates for Python projects.

## Basic Configuration

```yaml
# .github/dependabot.yml
version: 2

updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: daily

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: daily
```

## Advanced Configuration

```yaml
version: 2

updates:
  # Python dependencies (uv)
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: daily
    cooldown:
      default-days: 7  # Wait 7 days before updating new releases
    groups:
      python:
        patterns: ["*"]
    commit-message:
      prefix: "chore(deps)"
    labels:
      - "dependencies"
      - "python"
    reviewers:
      - "username"

  # GitHub Actions
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: daily
    cooldown:
      default-days: 7
    groups:
      actions:
        patterns: ["*"]
    commit-message:
      prefix: "chore(deps)"
    labels:
      - "dependencies"
      - "github-actions"
```

## Key Options

### Schedule Intervals

| Interval | Description |
|----------|-------------|
| `daily` | Every weekday |
| `weekly` | Once a week |
| `monthly` | Once a month |

### Cooldown

Wait before updating newly released packages (security feature):

```yaml
cooldown:
  default-days: 7  # Wait 7 days for new releases
```

### Grouping Updates

Reduce PR noise by grouping related updates:

```yaml
groups:
  python:
    patterns: ["*"]  # All Python packages

  # Or specific groups
  testing:
    patterns: ["pytest*", "coverage"]
  linting:
    patterns: ["ruff", "ty"]
```

### Ignoring Updates

```yaml
ignore:
  - dependency-name: "boto3"
    versions: [">=2.0.0"]  # Ignore v2+

  - dependency-name: "numpy"
    update-types: ["version-update:semver-major"]
```

## Package Ecosystems

| Ecosystem | For |
|-----------|-----|
| `uv` | Python (pyproject.toml + uv.lock) |
| `pip` | Python (requirements.txt) |
| `github-actions` | Workflow actions |
| `docker` | Dockerfiles |
| `npm` | Node.js |

## Security Updates

Dependabot also creates PRs for security vulnerabilities:

```yaml
# Automatic - no config needed
# Configure in Settings > Code security and analysis
```

## Workflow Triggers

```yaml
# .github/workflows/test.yml
on:
  pull_request:
    branches: [main]
```

Dependabot PRs will trigger this workflow automatically.

## Auto-merge for Patches

```yaml
# .github/workflows/dependabot-auto-merge.yml
name: Dependabot auto-merge
on: pull_request

permissions:
  contents: write
  pull-requests: write

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    if: github.actor == 'dependabot[bot]'
    steps:
      - uses: dependabot/fetch-metadata@v2
        id: metadata

      - if: steps.metadata.outputs.update-type == 'version-update:semver-patch'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Complete Example

```yaml
version: 2

updates:
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: daily
    cooldown:
      default-days: 7
    groups:
      python:
        patterns: ["*"]
    commit-message:
      prefix: "chore(deps)"
      include: "scope"
    labels:
      - "dependencies"
    open-pull-requests-limit: 10

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    cooldown:
      default-days: 7
    groups:
      actions:
        patterns: ["*"]
    commit-message:
      prefix: "chore(deps)"
    labels:
      - "dependencies"
      - "github-actions"
```

## References

- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [Configuration Options](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
