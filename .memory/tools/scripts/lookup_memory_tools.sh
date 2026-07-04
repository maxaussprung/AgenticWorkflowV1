#!/usr/bin/env bash
# Print EVERY tool/script in the local memory with a one-line description — the agent's cheat-sheet.
# Source of truth = .memory/tools/README.md (single index, kept in sync); this renders it to the
# console so an agent sees at a glance WHAT EXISTS before hand-rolling anything — and notices when a
# needed tool is MISSING (then add it: reusable+parametrised → tools/scripts/ + an index row).
# MANDATORY orientation step (see .memory/README.md "Finding things fast" + "how to search").
# RUN:  bash .memory/tools/scripts/lookup_memory_tools.sh
set -euo pipefail
MEM="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # .memory/
README="$MEM/tools/README.md"

echo "======================= LOCAL MEMORY TOOLS ======================="
echo "(rendered from .memory/tools/README.md — the authoritative index)"
awk -F'|' '
  /^## / { print ""; h=$0; sub(/^## */,"",h); print "### " h; next }
  /^\| \[/ {
    name=$2; desc=$3;
    sub(/^ *\[/,"",name); sub(/\].*$/,"",name); gsub(/^ +| +$/,"",name);
    gsub(/\*\*/,"",desc); gsub(/^ +| +$/,"",desc);
    if (length(desc) > 140) desc = substr(desc,1,137) "...";
    printf "  %-24s %s\n", name, desc;
  }
' "$README"

cat <<'EOF'

======================= DOCS + LOOKUP HELPERS ====================
  .memory/README.md            Index of all memory .md files + "Finding things fast" (READ FIRST)
  code_map.sh <area>           Where code lives + conventions per area (frontend|backend-*|tests)
  session_env.ps1 [-WithSecrets]  Put every tool on PATH (+ load PATs/user into env) — PowerShell
  merge_check.sh [<branch>]    Merge-safety: conflict markers + JSON + lost-test scan (before pushing a merge)
  integration_stack.sh up|test SLOW WSL+Docker local stack / integration tests — only when told / CI IT fails
  az_build.py <pr|branch>      Read a PR/branch CI pipeline result (+ --logs / --tests on failure)

Missing something you keep re-deriving? ADD it (reusable+parametrised) to tools/scripts/ and add an
index row in tools/README.md — then it shows up here automatically. Keep it deduped and grouped.
EOF
