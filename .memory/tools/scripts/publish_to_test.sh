#!/usr/bin/env bash
# Publish an implementation slice's feature branch onto the shared `test` INTEGRATION branch.
# WHY: testers test ALL open features / open PRs from ONE branch (`test`) instead of checking out
# each feature branch. Azure DevOps now carries a long-lived `test` branch that is the union of every
# currently-open feature branch.
# WHEN (mandatory, master-owned — see 05-slice-workflow.md "Publish to the shared test branch"):
#   - BEFORE complete-implementation-slice opens the PR the FIRST time, and
#   - again after EVERY fix pushed to the feature branch during the testing/UX loop.
# RULES: `test` is a rebuildable DOWNSTREAM integration branch. NEVER merge `test` back into master
#   or into a feature branch; PRs still target master. Push the feature branch to origin FIRST so this
#   merges the latest tip. On conflict the script STOPS (leaves test mid-merge) so you resolve minimally
#   (union track.md/i18n/openspec rows; preserve BOTH features' behaviour for real code — safe-rebase
#   principles), then `git add -A && git commit && git push origin test && git checkout <orig>`.
# MERGE LOG: every real merge writes a forensic event log to .memory/merge-logs/ (auto-generated
#   skeleton: auto-merged + conflict file lists + shas). On a CONFLICT merge you MUST append a
#   `--- resolution ---` section (one line per conflicted file: side taken / union / rationale) + the
#   final pushed sha to that log BEFORE finishing — see 05 "Merge safety" and .memory/merge-logs/README.md.
# RUN:  bash .memory/tools/scripts/publish_to_test.sh feature/<branch> [--no-push]
set -euo pipefail
FEATURE="${1:?usage: publish_to_test.sh <feature-branch> [--no-push]}"
PUSH=1; [ "${2:-}" = "--no-push" ] && PUSH=0
cd "$(git rev-parse --show-toplevel)"
FEATURE="${FEATURE#refs/heads/}"

# Refuse on TRACKED changes (untracked like .memory/package-lock is fine).
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ABORT: tracked changes present — commit/stash first:"; git status --short | grep -vE '^\?\?'; exit 1
fi

ORIG="$(git rev-parse --abbrev-ref HEAD)"
git fetch origin --quiet
git fetch origin "$FEATURE" --quiet || { echo "ABORT: cannot fetch origin/$FEATURE"; exit 1; }

ROOT="$(git rev-parse --show-toplevel)"; MLOGS="$ROOT/.memory/merge-logs"; mkdir -p "$MLOGS"
CLEAN_LOG=""   # set on a clean merge so the push step can stamp the result sha

# Refresh a local `test` that tracks origin/test, then merge the feature tip into it.
git checkout -B test origin/test --quiet
if git merge-base --is-ancestor "origin/$FEATURE" HEAD; then
  echo "Already on test: origin/$FEATURE (nothing to merge)."   # no-op: nothing to log
else
  BASE="$(git merge-base HEAD "origin/$FEATURE" 2>/dev/null | cut -c1-8 || echo '?')"
  TIP="$(git rev-parse --short "origin/$FEATURE")"
  MOUT="$(mktemp)"
  set +e
  git merge --no-ff -m "Merge branch '$FEATURE' into test" "origin/$FEATURE" >"$MOUT" 2>&1
  MRC=$?
  set -e
  cat "$MOUT"
  IDX="$(printf '%03d' $(( $(find "$MLOGS" -maxdepth 1 -name '*.log' 2>/dev/null | wc -l) + 1 )))"
  SAFE="$(echo "$FEATURE" | sed 's#[/ ]#-#g')"
  LOG="$MLOGS/${IDX}-${SAFE}-into-test-$(date +%Y%m%d-%H%M%S).log"
  {
    echo "MERGE ${IDX}  ${FEATURE} -> test"
    echo "when:   $(date '+%Y-%m-%dT%H:%M:%S%z')"
    echo "base:   ${BASE}   tip(${FEATURE}): ${TIP}   result: $([ "$MRC" -eq 0 ] && git rev-parse --short HEAD || echo PENDING)"
    echo "--- auto-merged ---"
    grep -E '^Auto-merging ' "$MOUT" | sed -E 's/^Auto-merging /  /' || true
    echo "--- conflicts ---"
    if grep -q 'CONFLICT' "$MOUT"; then grep -E 'CONFLICT' "$MOUT" | sed -E 's/.*Merge conflict in /  /'; else echo "  (none)"; fi
    echo "--- status ---"
    [ "$MRC" -eq 0 ] && echo "CLEAN merge (no conflicts)." \
                     || echo "CONFLICTS — resolve, then APPEND a '--- resolution ---' section (one line per file) + the final pushed sha here (05 Merge safety)."
  } >"$LOG"
  rm -f "$MOUT"
  echo "merge-log: ${LOG#"$ROOT"/}"
  if [ "$MRC" -ne 0 ]; then
    echo "CONFLICT merging origin/$FEATURE into test — resolve, append RESOLUTION to the merge-log above, commit, push origin test, checkout $ORIG:"
    git --no-pager diff --name-only --diff-filter=U
    exit 2
  fi
  echo "Merged origin/$FEATURE into test."
  CLEAN_LOG="$LOG"
fi

if [ "$PUSH" = 1 ]; then
  git push origin test
  [ -n "$CLEAN_LOG" ] && echo "RESULT: pushed $(git rev-parse --short HEAD)" >>"$CLEAN_LOG"
else echo "(--no-push: not pushing)"; fi
git checkout "$ORIG" --quiet
echo "=== published origin/$FEATURE to test; back on $ORIG ==="
