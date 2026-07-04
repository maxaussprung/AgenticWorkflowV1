#!/usr/bin/env bash
# Map a page/component keyword to its Next.js route(s) + the data-testids in that component — so a
# reviewer test-guide comment (see 01 "Reviewer test-guide") can be written fast + accurately. READ-ONLY.
# RUN:  bash .memory/tools/scripts/find_route.sh <keyword>   e.g. logdaten | directiveOrderSearch | create
set -uo pipefail
cd "$(git rev-parse --show-toplevel)/csharp/src/frontend"
KW="${1:?usage: find_route.sh <keyword>}"

echo "=== routes (src/pages matching '$KW') ==="
find src/pages -type f \( -name '*.tsx' -o -name 'index.ts' \) 2>/dev/null | grep -iE "$KW" | while read -r f; do
  route=$(printf '%s' "$f" | sed -E 's#^src/pages##; s#/index\.(tsx|ts)$##; s#\.(tsx|ts)$##')
  [ -z "$route" ] && route="/"
  echo "  $f  ->  http://localhost:3000$route"
done
[ -z "$(find src/pages -type f \( -name '*.tsx' -o -name 'index.ts' \) 2>/dev/null | grep -iE "$KW")" ] && \
  echo "  (no page file matched — the view may be reached through a parent flow, e.g. landing → search → row action)"

echo "=== data-testids in components/*$KW* (click targets for the guide) ==="
found=0
for d in $(find src/components -type d -iname "*$KW*" 2>/dev/null); do
  ids=$(grep -rhoE "data-testid=['\"][^'\"]+['\"]" "$d" 2>/dev/null | sort -u)
  [ -n "$ids" ] && { echo "  # $d"; printf '%s\n' "$ids" | sed 's#^#    #'; found=1; }
done
[ "$found" = 0 ] && echo "  (no component dir matched '$KW' — try a broader keyword)"
