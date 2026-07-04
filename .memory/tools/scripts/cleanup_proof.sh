#!/usr/bin/env bash
# Remove proof/temp artifacts after posting (or after an abandoned attempt): any throwaway preview
# pages left in the frontend (the `pages/__*.tsx` convention) + scratchpad screenshots/scripts/logs.
# Does NOT touch committed files. Pass the scratchpad dir to also clean it.
# RUN:  bash .memory/tools/scripts/cleanup_proof.sh [scratchpad_dir]
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
SC="${1:-}"

# 1) Throwaway preview pages (never committed) — detect via git across tracked+untracked.
mapfile -t previews < <(git -C "$ROOT" status --porcelain --untracked-files=all | awk '{print $2}' | grep -E 'src/pages/__' || true)
for f in "${previews[@]:-}"; do [ -n "$f" ] && rm -f "$ROOT/$f" && echo "removed throwaway $f"; done

# 2) Scratchpad proof artifacts (screenshots + one-off post/rebut scripts + logs).
if [ -n "$SC" ] && [ -d "$SC" ]; then
  rm -f "$SC"/shot_*.png "$SC"/proof_*.png "$SC"/*_proof*.png "$SC"/*.log \
        "$SC"/post_*.py "$SC"/rebut_*.py "$SC"/shoot*.py "$SC"/debug*.py 2>/dev/null || true
  echo "cleaned scratchpad: $SC"
fi

# 3) The agent temp workspace (.memory/temp/ — where agents copy templates + create throwaway scripts)
#    and stray python caches under the memory tools.
rm -rf "$ROOT/.memory/temp"/* 2>/dev/null || true
rm -rf "$ROOT/.memory/tools/scripts/__pycache__" 2>/dev/null || true

echo "done. Remaining tracked changes:"; git -C "$ROOT" status --short | grep -vE '^\?\?' || echo "  (clean)"
