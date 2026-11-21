#!/usr/bin/env python3
"""Handwritten code-size report for two Git refs.

Answers "how big is this change, really?" without a checkout: every number is read from the Git object
database, so a dirty working tree and the checked-out branch do not affect the result.

Run from anywhere inside the repository:

    python3 scripts/size-report.py <base-ref> [head-ref]        # head defaults to HEAD

Counting rules (keep these stable so runs stay comparable):

- backend production: ``backend/app/**/*.py`` excluding ``app/tests/`` and ``app/alembic/``.
- backend migrations: ``backend/app/alembic/**/*.py`` (handwritten, reported separately because the
  89k backend figure in issue #1469 is production + migrations).
- backend tests: ``backend/app/tests/**/*.py``.
- frontend production: ``frontend/src/**/*.{ts,vue,css}`` excluding generated files.
- frontend generated: files named ``*.generated.*`` under ``frontend/src`` (the OpenAPI types).
- frontend tests: ``frontend/tests/**/*.{ts,vue}``.
- catalog data: ``backend/app/data/**/*.{json,yaml,yml,csv,sql}`` and
  ``frontend/src/assets/data/**/*.{json,yaml,yml,csv}``; data rows, not code, so they never count toward
  the production budget.

Policy signals:

- **Test:production ratio** is printed twice for the backend: excluding migrations, and including them.
  The figure quoted in issue #1469 (1.12) uses the including-migrations denominator.
- **Gross handwritten additions** sum added lines from the two-ref diff, including migrations in
  production and both test trees in tests. This is the number the ~300-line PR size prompt uses; net LOC
  deltas understate it when the change also deletes code. It covers application and test code only:
  tooling such as this script is outside the total.

A file's line count is ``wc -l`` style: newlines, plus one when the last line lacks a trailing newline.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

BACKEND_PRODUCTION = "Backend production"
BACKEND_MIGRATIONS = "Backend migrations"
BACKEND_TESTS = "Backend tests"
FRONTEND_PRODUCTION = "Frontend production"
FRONTEND_GENERATED = "Frontend generated"
FRONTEND_TESTS = "Frontend tests"
BACKEND_CATALOG = "Backend catalog data"
FRONTEND_CATALOG = "Frontend catalog data"

CATEGORY_ORDER = (
    BACKEND_PRODUCTION,
    BACKEND_MIGRATIONS,
    BACKEND_TESTS,
    FRONTEND_PRODUCTION,
    FRONTEND_GENERATED,
    FRONTEND_TESTS,
    BACKEND_CATALOG,
    FRONTEND_CATALOG,
)

LARGE_FILE_THRESHOLD = 600
PR_SIZE_PROMPT = 300


@dataclass(frozen=True)
class Snapshot:
    """One ref's counted tree."""

    ref: str
    lines: dict[str, int]
    files: dict[str, int]
    modules: int
    feature_docs: int
    migrations: int
    large_files: tuple[tuple[int, str], ...]

    def line_total(self, category: str) -> int:
        """Line count for one report category."""
        return self.lines[category]

    def file_total(self, category: str) -> int:
        """File count for one report category."""
        return self.files[category]

    @property
    def handwritten_production(self) -> int:
        """Backend production, migrations and frontend production."""
        return (
            self.lines[BACKEND_PRODUCTION]
            + self.lines[BACKEND_MIGRATIONS]
            + self.lines[FRONTEND_PRODUCTION]
        )

    @property
    def handwritten_tests(self) -> int:
        """Backend and frontend test trees."""
        return self.lines[BACKEND_TESTS] + self.lines[FRONTEND_TESTS]


@dataclass(frozen=True)
class Report:
    """A base/head comparison plus the policy signals."""

    base: Snapshot
    head: Snapshot
    base_commit: str
    head_commit: str
    changed_files: int
    added: dict[str, int]

    @property
    def added_production(self) -> int:
        """Gross handwritten production additions (migrations included)."""
        return (
            self.added[BACKEND_PRODUCTION]
            + self.added[BACKEND_MIGRATIONS]
            + self.added[FRONTEND_PRODUCTION]
        )

    @property
    def added_tests(self) -> int:
        """Gross handwritten test additions."""
        return self.added[BACKEND_TESTS] + self.added[FRONTEND_TESTS]

    @property
    def added_total(self) -> int:
        """Gross application/test additions used by the ~300-line PR prompt."""
        return self.added_production + self.added_tests


def git(repo: Path, *args: str) -> bytes:
    """Run one Git command and return stdout, failing with its stderr."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip() or "git command failed"
        raise SystemExit(f"size-report: {message}")
    return result.stdout


def resolve_ref(repo: Path, ref: str) -> str:
    """Resolve a ref to a commit and fail with a readable message when it does not exist."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "rev-parse",
            "--verify",
            "--quiet",
            f"{ref}^{{commit}}",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"size-report: unknown Git ref {ref!r}")
    return result.stdout.decode().strip()


def list_files(repo: Path, commit: str) -> list[str]:
    """Every path in the commit's tree."""
    return (
        git(repo, "ls-tree", "-r", "--name-only", commit)
        .decode("utf-8", errors="replace")
        .splitlines()
    )


def is_generated(path: str) -> bool:
    """True for checked-in generated files such as ``api.generated.ts``."""
    return ".generated." in Path(path).name


def category_paths(paths: Iterable[str]) -> dict[str, list[str]]:
    """Map repository paths to the report categories."""
    backend = [p for p in paths if p.startswith("backend/app/") and p.endswith(".py")]
    frontend = [
        p
        for p in paths
        if p.startswith("frontend/src/") and p.endswith((".ts", ".vue", ".css"))
    ]
    return {
        BACKEND_PRODUCTION: [
            p
            for p in backend
            if not p.startswith(("backend/app/tests/", "backend/app/alembic/"))
        ],
        BACKEND_MIGRATIONS: [
            p for p in backend if p.startswith("backend/app/alembic/")
        ],
        BACKEND_TESTS: [p for p in backend if p.startswith("backend/app/tests/")],
        FRONTEND_PRODUCTION: [p for p in frontend if not is_generated(p)],
        FRONTEND_GENERATED: [p for p in frontend if is_generated(p)],
        FRONTEND_TESTS: [
            p
            for p in paths
            if p.startswith("frontend/tests/") and p.endswith((".ts", ".vue"))
        ],
        BACKEND_CATALOG: [
            p
            for p in paths
            if p.startswith("backend/app/data/")
            and p.endswith((".json", ".yaml", ".yml", ".csv", ".sql"))
        ],
        FRONTEND_CATALOG: [
            p
            for p in paths
            if p.startswith("frontend/src/assets/data/")
            and p.endswith((".json", ".yaml", ".yml", ".csv"))
        ],
    }


def count_lines(repo: Path, commit: str, paths: list[str]) -> dict[str, int]:
    """Line counts for the given paths, read in one ``git cat-file --batch`` stream."""
    if not paths:
        return {}
    request = "".join(f"{commit}:{path}\n" for path in paths).encode()
    stream = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=request,
        capture_output=True,
        check=False,
    )
    if stream.returncode != 0:
        raise SystemExit(
            "size-report: reading blobs failed: "
            f"{stream.stderr.decode(errors='replace').strip()}"
        )

    output = stream.stdout
    counts: dict[str, int] = {}
    cursor = 0
    for path in paths:
        header_end = output.index(b"\n", cursor)
        header = output[cursor:header_end].decode(errors="replace").split()
        cursor = header_end + 1
        if len(header) != 3 or header[1] != "blob":
            counts[path] = 0
            continue
        size = int(header[2])
        blob = output[cursor : cursor + size]
        cursor += size + 1  # the batch protocol's trailing newline
        counts[path] = blob.count(b"\n") + (
            1 if blob and not blob.endswith(b"\n") else 0
        )
    return counts


def snapshot(repo: Path, ref: str) -> Snapshot:
    """Count one ref's categories, tree shape and large files."""
    commit = resolve_ref(repo, ref)
    paths = list_files(repo, commit)
    grouped = category_paths(paths)

    lines = dict.fromkeys(CATEGORY_ORDER, 0)
    files = dict.fromkeys(CATEGORY_ORDER, 0)
    large_files: list[tuple[int, str]] = []
    for category in CATEGORY_ORDER:
        counts = count_lines(repo, commit, grouped[category])
        lines[category] = sum(counts.values())
        files[category] = len(counts)
        if category in (BACKEND_PRODUCTION, FRONTEND_PRODUCTION):
            large_files.extend(
                (line_count, path)
                for path, line_count in counts.items()
                if line_count > LARGE_FILE_THRESHOLD
            )

    modules = {
        path.split("/")[3]
        for path in paths
        if path.startswith("frontend/src/modules/") and len(path.split("/")) > 4
    }
    feature_docs = {
        path
        for path in paths
        if path.startswith("docs/features/")
        and path.endswith(".md")
        and path.count("/") == 2
    }
    migrations = {
        path
        for path in paths
        if path.startswith(
            ("backend/app/alembic/baseline_versions/", "backend/app/alembic/versions/")
        )
        and path.endswith(".py")
        and Path(path).name != "__init__.py"
    }

    return Snapshot(
        ref=ref,
        lines=lines,
        files=files,
        modules=len(modules),
        feature_docs=len(feature_docs),
        migrations=len(migrations),
        large_files=tuple(sorted(large_files, reverse=True)),
    )


def changed_files(repo: Path, base: str, head: str) -> int:
    """Files whose content differs between the two commits (renames count once)."""
    output = git(repo, "diff", "--name-only", base, head)
    return len([line for line in output.decode(errors="replace").splitlines() if line])


def added_lines(
    repo: Path, base: str, head: str, categories: dict[str, list[str]]
) -> dict[str, int]:
    """Gross added lines per category, with renames attributed to their new path."""
    category_of = {
        path: category for category, paths in categories.items() for path in paths
    }
    output = git(repo, "diff", "--numstat", "-M", "-z", base, head)
    tokens = output.split(b"\0")
    additions = dict.fromkeys(CATEGORY_ORDER, 0)

    index = 0
    while index < len(tokens):
        header = tokens[index]
        index += 1
        if not header:
            continue
        fields = header.split(b"\t", 2)
        if len(fields) != 3:
            continue
        added_raw, _deleted_raw, path_raw = fields
        if path_raw:
            target = path_raw.decode(errors="replace")
        else:
            # Rename/copy records carry the old and new paths as separate tokens.
            if index + 1 >= len(tokens):
                break
            target = tokens[index + 1].decode(errors="replace")
            index += 2
        category = category_of.get(target)
        if category is not None and added_raw != b"-":
            additions[category] += int(added_raw)
    return additions


def format_delta(delta: int) -> str:
    """Signed delta with thousands separators; zero stays unsigned."""
    return f"{delta:+,}" if delta else "0"


def ratio(numerator: int, denominator: int) -> float:
    """Numerator over denominator, or 0.0 when the denominator is empty."""
    return numerator / denominator if denominator else 0.0


def build_report(repo: Path, base_ref: str, head_ref: str) -> Report:
    """Compare two refs into a typed report."""
    base_commit = resolve_ref(repo, base_ref)
    head_commit = resolve_ref(repo, head_ref)
    head_paths = list_files(repo, head_commit)
    return Report(
        base=snapshot(repo, base_ref),
        head=snapshot(repo, head_ref),
        base_commit=base_commit,
        head_commit=head_commit,
        changed_files=changed_files(repo, base_commit, head_commit),
        added=added_lines(repo, base_commit, head_commit, category_paths(head_paths)),
    )


def print_report(report: Report) -> None:
    """Human-readable table, ratios and the PR size prompt."""
    base, head = report.base, report.head
    print(
        f"Size report: {base.ref} ({report.base_commit[:9]}) -> "
        f"{head.ref} ({report.head_commit[:9]})"
    )
    print()
    print(f"{'category':<26}{'base':>12}{'head':>12}{'delta':>12}{'files':>16}")
    print("-" * 78)
    for category in CATEGORY_ORDER:
        base_lines = base.line_total(category)
        head_lines = head.line_total(category)
        print(
            f"{category:<26}{base_lines:>12,}{head_lines:>12,}"
            f"{format_delta(head_lines - base_lines):>12}"
            f"{base.file_total(category):>8} -> {head.file_total(category):<5}"
        )
    print("-" * 78)

    for label, base_lines, head_lines in (
        (
            "Backend production",
            base.line_total(BACKEND_PRODUCTION),
            head.line_total(BACKEND_PRODUCTION),
        ),
        (
            "Frontend production",
            base.line_total(FRONTEND_PRODUCTION),
            head.line_total(FRONTEND_PRODUCTION),
        ),
        (
            "Handwritten production",
            base.handwritten_production,
            head.handwritten_production,
        ),
        ("Backend tests", base.line_total(BACKEND_TESTS), head.line_total(BACKEND_TESTS)),
        ("Frontend tests", base.line_total(FRONTEND_TESTS), head.line_total(FRONTEND_TESTS)),
        ("Handwritten tests", base.handwritten_tests, head.handwritten_tests),
    ):
        print(
            f"{label:<26}{base_lines:>12,}{head_lines:>12,}"
            f"{format_delta(head_lines - base_lines):>12}"
        )

    print()
    print(f"{'test:production ratio':<26}{'base':>12}{'head':>12}")
    print("-" * 50)
    ratios = (
        (
            "Backend (excl migrations)",
            ratio(base.line_total(BACKEND_TESTS), base.line_total(BACKEND_PRODUCTION)),
            ratio(head.line_total(BACKEND_TESTS), head.line_total(BACKEND_PRODUCTION)),
        ),
        (
            "Backend (incl migrations)",
            ratio(
                base.line_total(BACKEND_TESTS),
                base.line_total(BACKEND_PRODUCTION)
                + base.line_total(BACKEND_MIGRATIONS),
            ),
            ratio(
                head.line_total(BACKEND_TESTS),
                head.line_total(BACKEND_PRODUCTION)
                + head.line_total(BACKEND_MIGRATIONS),
            ),
        ),
        (
            "Frontend",
            ratio(
                base.line_total(FRONTEND_TESTS), base.line_total(FRONTEND_PRODUCTION)
            ),
            ratio(
                head.line_total(FRONTEND_TESTS), head.line_total(FRONTEND_PRODUCTION)
            ),
        ),
    )
    for label, base_ratio, head_ratio in ratios:
        print(f"{label:<26}{base_ratio:>12.2f}{head_ratio:>12.2f}")

    print()
    print(
        f"Gross handwritten application/test additions (PR size prompt at ~{PR_SIZE_PROMPT}):"
    )
    for label, count in (
        ("Production", report.added_production),
        ("Tests", report.added_tests),
        ("Total", report.added_total),
    ):
        print(f"{label:<26}{count:>12,}")
    print(
        "  Scope: application + test code; tooling, generated and catalog files excluded."
    )
    if report.added_total >= PR_SIZE_PROMPT:
        print("  -> above the prompt: record what the change replaces.")
    print()
    print(
        f"Changed files: {report.changed_files}    "
        f"Modules: {base.modules} -> {head.modules}    "
        f"Feature docs: {base.feature_docs} -> {head.feature_docs}    "
        f"Migrations: {base.migrations} -> {head.migrations}"
    )

    print()
    print(f"Files over {LARGE_FILE_THRESHOLD} lines (handwritten production, head):")
    if not head.large_files:
        print("  none")
    for line_count, path in head.large_files:
        print(f"  {line_count:>6,}  {path}")
    print()
    print(
        "Definitions: backend production excludes migrations and tests; frontend production excludes "
        "generated files; catalog data (quests, dweller lines, seeds) and tooling count toward no budget. "
        "'Handwritten' rows sum both sides."
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the two refs."""
    parser = argparse.ArgumentParser(
        description="Report handwritten code size and deltas between two Git refs.",
    )
    parser.add_argument("base", help="base Git ref, e.g. master or a commit SHA")
    parser.add_argument(
        "head", nargs="?", default="HEAD", help="head Git ref (default: HEAD)"
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Run the report."""
    args = parse_args(argv)
    repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
    print_report(build_report(repo, args.base, args.head))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
