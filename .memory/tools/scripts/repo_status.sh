#!/usr/bin/env bash
# One-shot repo orientation (READ-ONLY): branch + tracked status + diff-stat + recent log.
# Run at the start of a fix/continue to see where things stand in one call.
# RUN:  bash .memory/tools/scripts/repo_status.sh
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
echo "=== branch ==="; git rev-parse --abbrev-ref HEAD
echo "=== status (tracked changes; untracked hidden) ==="; git status --short | grep -vE '^\?\?' || echo "  clean"
echo "=== diff --stat (unstaged) ==="; git diff --stat | tail -25
echo "=== recent commits ==="; git log --oneline -8
