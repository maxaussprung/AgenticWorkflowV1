#!/usr/bin/env bash
# Merge-safety gate — run BEFORE committing/pushing a `test`-branch merge (or any conflict resolution).
# Merges are DANGEROUS: a bad resolution silently LOSES functionality or leaves ARTEFACTS/DUPLICATES.
# This catches the mechanical failure modes; the SEMANTIC check (did both features' behaviour survive?)
# is on you — ground it in openspec/track.md + the requirements behind BOTH sides (see 05 "Merge safety"
# and the safe-rebase-on-master skill). After this passes, run verify.sh (typecheck/lint/tests/build).
#
# Checks:  1) leftover conflict markers in tracked code (excludes .memory/ + reports/ docs)
#          2) every changed *.json still parses (barrel/i18n/openspec files break silently otherwise)
#          3) [optional] test files present on <feature-branch> but MISSING now = lost-in-merge tests
# RUN:  bash .memory/tools/scripts/merge_check.sh [feature/<branch-just-merged>]
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
BRANCH="${1:-}"; RC=0

echo "== 1) conflict markers (tracked code, excl .memory/ + reports/) =="
if git grep -nI -E '^(<<<<<<< |=======$|>>>>>>> )' -- ':!.memory/**' ':!reports/**' ':!**/*.md' ; then
  echo "   FAIL: conflict markers above — resolve them."; RC=1
else echo "   ok: no conflict markers"; fi

echo "== 2) changed source JSON validity (vs origin/master; excl reports/ + .memory/) =="
BASE="$(git merge-base HEAD origin/master 2>/dev/null || echo '')"
JSON=$( { [ -n "$BASE" ] && git diff --name-only "$BASE"...HEAD -- '*.json'; git diff --name-only -- '*.json'; git diff --cached --name-only -- '*.json'; } \
        | grep -vE '^(reports/|\.memory/)' | sort -u )
if [ -z "$JSON" ]; then echo "   (no changed source JSON)"; else
  for f in $JSON; do
    [ -f "$f" ] || continue
    if jq empty "$f" 2>/dev/null; then echo "   ok: $f"; else echo "   FAIL: invalid JSON -> $f"; RC=1; fi
  done
fi

if [ -n "$BRANCH" ]; then
  echo "== 3) lost-test scan: test files on origin/$BRANCH missing on HEAD =="
  git fetch origin "$BRANCH" --quiet 2>/dev/null || true
  # Compare against the INDEX (git ls-files), not committed HEAD, so a staged-but-uncommitted
  # merge is judged on what it actually contains (self-heal: HEAD gave false positives mid-merge).
  LOST=$(comm -23 \
    <(git ls-tree -r --name-only "origin/$BRANCH" | grep -E '(\.test\.tsx?$|Tests\.cs$|/__tests__/)' | sort) \
    <(git ls-files                                | grep -E '(\.test\.tsx?$|Tests\.cs$|/__tests__/)' | sort) )
  if [ -n "$LOST" ]; then
    echo "   WARN: test files on the branch are ABSENT on HEAD (renamed OR lost — verify each):"
    echo "$LOST" | sed 's/^/     - /'; RC=1
  else echo "   ok: no test files dropped vs origin/$BRANCH"; fi
fi

echo ""
if [ "$RC" -eq 0 ]; then
  echo "MERGE-CHECK PASSED (mechanical). Now run: bash .memory/tools/scripts/verify.sh all"
  echo "and confirm the SEMANTIC merge (both features' behaviour survived) against track.md + requirements."
else echo "MERGE-CHECK FAILED — fix the above before committing the merge."; fi
exit "$RC"
