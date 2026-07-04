#!/usr/bin/env bash
# Run the repo's CANONICAL build/lint/test checks for a slice — the developer's own automated checks
# that complete-implementation-slice expects to already pass. COMPLEMENTS the skills; does NOT replace
# generate-tdd-tests (authoring), complete-implementation-slice (validation+PR), or sonarqube-run-fix.
# Uses the project's own pnpm scripts + dotnet, and auto-loads the NuGet PAT so the backend build works.
#
# RUN:
#   bash .memory/tools/scripts/verify.sh frontend [--jest <pattern>] [--soft]
#   bash .memory/tools/scripts/verify.sh backend  [--filter <expr>] [--it] [--soft]   # --it adds integration tests (needs Docker)
#   bash .memory/tools/scripts/verify.sh all [--soft]
# --soft = the QUICK loop to run after every change (frontend: typecheck+lint, skip jest; backend:
#   build only, skip tests). Default (HARD) = full checks — run before every commit/push/proof.
# Run ONE test fast during iteration (see 10-testing-patterns.md): frontend `--jest <file|-t name>`;
# backend `--filter <expr>` (dotnet --filter, e.g. FullyQualifiedName~OpenCollectionCases or Name~ReturnsX).
# For fast per-file lint during iteration, `next lint --file <path>` is quicker (see 00/03).
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
TARGET="${1:-all}"; shift || true
JESTPAT=""; TESTFILTER=""; RUN_IT=0; SOFT=0
while [ $# -gt 0 ]; do case "$1" in
  --jest)   JESTPAT="${2:-}"; shift 2;;
  --filter) TESTFILTER="${2:-}"; shift 2;;
  --it)     RUN_IT=1; shift;;
  --soft)   SOFT=1; shift;;
  *) echo "ignoring unknown arg: $1"; shift;;
esac; done

FAIL=0
step(){ local name="$1"; shift; echo; echo "=== $name ==="; if "$@"; then echo "-- ok: $name"; else echo "!! FAILED: $name"; FAIL=1; fi; }

verify_frontend(){
  # The frontend .npmrc auths the postat npm feed with NPM_POSTAT_* — set them (same values as the
  # NuGet PAT) so pnpm doesn't warn "Failed to replace env in config: ${NPM_POSTAT_USERNAME}".
  : "${NPM_POSTAT_USERNAME:=jonas.hauser@accenture.com}"
  : "${NPM_POSTAT_CLEAR_TEXT_PASSWORD:=$(jq -r .pat "$ROOT/.memory/PATS/NUGET-PAT.json" 2>/dev/null)}"
  export NPM_POSTAT_USERNAME NPM_POSTAT_CLEAR_TEXT_PASSWORD
  pushd csharp/src/frontend >/dev/null
  step "frontend typecheck (pnpm typecheck)" pnpm typecheck
  step "frontend lint (pnpm lint)"           pnpm lint
  if [ "$SOFT" = 1 ]; then echo "  (--soft: skipping jest)"
  elif [ -n "$JESTPAT" ]; then step "frontend jest ($JESTPAT)" pnpm test "$JESTPAT"
  else                        step "frontend jest (pnpm test)" pnpm test; fi
  popd >/dev/null
}
verify_backend(){
  : "${NUGET_POSTAT_USERNAME:=jonas.hauser@accenture.com}"
  : "${NUGET_POSTAT_CLEAR_TEXT_PASSWORD:=$(jq -r .pat "$ROOT/.memory/PATS/NUGET-PAT.json")}"
  export NUGET_POSTAT_USERNAME NUGET_POSTAT_CLEAR_TEXT_PASSWORD
  step "backend build (dotnet build sln)"    dotnet build csharp/PostAG.Logistics.Mad.sln
  if [ "$SOFT" = 1 ]; then echo "  (--soft: skipping backend tests)"; return 0; fi
  if [ -n "$TESTFILTER" ]; then
    step "backend unit tests (filter: $TESTFILTER)" dotnet test csharp/test/backend/PostAG.Logistics.Mad.UnitTests --filter "$TESTFILTER"
  else
    step "backend unit tests (Mad.UnitTests)"  dotnet test csharp/test/backend/PostAG.Logistics.Mad.UnitTests
  fi
  if [ "$RUN_IT" = 1 ]; then
    step "backend integration tests (needs Docker)" dotnet test csharp/test/backend/PostAG.Logistics.Mad.API.IntegrationTests
  fi
}
case "$TARGET" in
  frontend) verify_frontend;;
  backend)  verify_backend;;
  all)      verify_frontend; verify_backend;;
  *) echo "usage: verify.sh frontend|backend|all [--jest <pattern>] [--filter <expr>] [--it] [--soft]"; exit 2;;
esac
echo; if [ "$FAIL" = 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; exit 1; fi
