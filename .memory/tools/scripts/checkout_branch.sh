#!/usr/bin/env bash
# Safe branch checkout for fix/continue flows: refuse if the tree has tracked changes,
# fetch, checkout, fast-forward, show status. Untracked-only (e.g. package-lock, .memory) is OK.
# RUN:  bash .memory/tools/scripts/checkout_branch.sh feature/<branch>
set -euo pipefail
BRANCH="${1:?usage: checkout_branch.sh <branch>}"
cd "$(git rev-parse --show-toplevel)"

# Block only on TRACKED modifications (staged/unstaged); untracked files are fine.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ABORT: tracked changes present — commit/stash first:"; git status --short | grep -vE '^\?\?'; exit 1
fi

git fetch origin "$BRANCH" --quiet || true
git checkout "$BRANCH"
git pull --ff-only 2>&1 | tail -1 || echo "(no upstream fast-forward)"
echo "=== on $(git rev-parse --abbrev-ref HEAD); status (untracked hidden) ==="
git status --short | grep -vE '^\?\?' || echo "clean"
