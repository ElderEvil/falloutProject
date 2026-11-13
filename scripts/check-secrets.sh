#!/usr/bin/env bash
set -euo pipefail

# prek supplies these for --from-ref/--to-ref runs; ordinary commits scan the index.
if [[ -n "${PRE_COMMIT_FROM_REF:-}" || -n "${PRE_COMMIT_TO_REF:-}" ]]; then
  from_ref=$(git rev-parse --verify "${PRE_COMMIT_FROM_REF:?Missing starting ref}^{commit}")
  to_ref=$(git rev-parse --verify "${PRE_COMMIT_TO_REF:?Missing destination ref}^{commit}")
  base_ref=$(git merge-base "$from_ref" "$to_ref")
  exec gitleaks git --redact --verbose --log-opts="$base_ref..$to_ref"
fi

exec gitleaks git --pre-commit --redact --staged --verbose
