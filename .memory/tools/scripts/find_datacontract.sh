#!/usr/bin/env bash
# Slice-selection aid: does a data contract for <keyword> already exist in the repo? Greps the
# committed contract docs + source imports so you can tell if a contract-dependent requirement is
# buildable now (see 05 selection rules; read the .md, not the .xlsx — global memory vvf-data-contracts).
# READ-ONLY. RUN:  bash .memory/tools/scripts/find_datacontract.sh <keyword>   e.g. Audit | KCRM | PERI | Redirection
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
KW="${1:?usage: find_datacontract.sh <keyword>}"
echo "=== docs/requirements/data-contracts (agent-facing .md) ==="
grep -rilE "$KW" docs/requirements/data-contracts 2>/dev/null | sed 's#^#  #' || true
echo "=== docs/requirements/data-sources / source-import (raw contracts) ==="
grep -rilE "$KW" docs/requirements/data-sources docs/requirements/source-import* 2>/dev/null | sed 's#^#  #' || true
echo "=== filenames matching (any location under docs/requirements) ==="
find docs/requirements -type f -iname "*$KW*" 2>/dev/null | sed 's#^#  #' || true
echo "(no lines under a heading = no contract found there → likely NOT buildable yet; confirm on the requirement page)"
