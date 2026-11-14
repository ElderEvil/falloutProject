#!/usr/bin/env bash
set -euo pipefail

# prek supplies these for --from-ref/--to-ref runs; ordinary commits scan the index.
if [[ -n "${PRE_COMMIT_FROM_REF:-}" || -n "${PRE_COMMIT_TO_REF:-}" ]]; then
  from_ref=$(git rev-parse --verify "${PRE_COMMIT_FROM_REF:?Missing starting ref}^{commit}")
  to_ref=$(git rev-parse --verify "${PRE_COMMIT_TO_REF:?Missing destination ref}^{commit}")
  base_ref=$(git merge-base "$from_ref" "$to_ref")
  # git omits merge diffs by default; scan each merge against its first parent
  # so a secret introduced only in a conflict resolution is still caught.
  exec gitleaks git --redact --verbose --log-opts="$base_ref..$to_ref --diff-merges=first-parent"
fi

exec gitleaks git --pre-commit --redact --staged --verbose
