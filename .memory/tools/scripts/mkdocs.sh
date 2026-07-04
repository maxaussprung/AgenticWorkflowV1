#!/usr/bin/env bash
# Requirements-site build with the VERIFIED Windows venv path (see 03): mkdocs is at
# .venv/Scripts/mkdocs.exe here, NOT the POSIX .venv/bin/mkdocs that AGENTS.md cites. --strict by
# default. Run after editing any docs/requirements/** page (e.g. openspec_change frontmatter + Architecture).
# RUN:  bash .memory/tools/scripts/mkdocs.sh [build|serve]   (default: strict build)
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
MK=".venv/Scripts/mkdocs.exe"; [ -x "$MK" ] || MK=".venv/bin/mkdocs"   # fall back to POSIX if ever on Linux
CMD="${1:-build}"
case "$CMD" in
  build) "$MK" build -f tools/requirements-site/mkdocs.yml --strict;;
  serve) "$MK" serve -f tools/requirements-site/mkdocs.yml;;
  *) echo "usage: mkdocs.sh [build|serve]"; exit 2;;
esac
