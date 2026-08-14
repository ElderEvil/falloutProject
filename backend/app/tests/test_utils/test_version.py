"""Tests for application version utilities."""

from pathlib import Path

from app.utils.version import parse_changelog


def test_parse_changelog_supports_semantic_release_headings(tmp_path: Path) -> None:
    """Parse the heading format produced by semantic-release."""
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(
        """# Changelog

## [2.35.0](https://example.test/compare/v2.34.3...v2.35.0) (2026-08-14)

### Features

- **Release automation** — synchronize application versions automatically

---

## [2.34.3] - 2026-08-13

### Fixed

- **Quest chains** — show prerequisite quests correctly
""",
        encoding="utf-8",
    )

    entries = parse_changelog(changelog_path)

    assert [entry["version"] for entry in entries] == ["2.35.0", "2.34.3"]
    assert entries[0]["changes"] == [
        {
            "category": "Features",
            "description": "**Release automation** — synchronize application versions automatically",
        }
    ]
