#!/usr/bin/env bash
# Bring up the LOCAL VVF stack, or run the backend integration tests, INSIDE WSL (Ubuntu) — the ONLY
# place Docker/Testcontainers work on this machine (Docker lives inside WSL, NOT on the Windows host).
#
# SLOW (minutes to build+boot). This is NOT part of the normal per-slice loop. Run it ONLY when:
#   - the user explicitly asks for local integration testing / a running local stack, OR
#   - a failed pipeline's failing step IS the backend integration tests and you must reproduce locally
#     (triage the build first with az_build.py; see 07 + 03 "WSL + Docker integration tests").
#
# Secrets: loads NuGet creds from PATS/NUGET-PAT.json (no echo) and forwards them into WSL via WSLENV
# (keeps the token off the wsl command line). Repo is reached inside WSL via /mnt/c (wslpath).
#
# RUN (from repo root, Git bash):
#   bash .memory/tools/scripts/integration_stack.sh up             # start the Mock stack (start-mock-docker.sh)
#   bash .memory/tools/scripts/integration_stack.sh test [args]    # dotnet tests via backend-test.sh (add --filter ...)
set -euo pipefail
ACTION="${1:-up}"; shift || true
ROOT="$(git rev-parse --show-toplevel)"

export NUGET_POSTAT_USERNAME="jonas.hauser@accenture.com"
export NUGET_POSTAT_CLEAR_TEXT_PASSWORD="$(jq -r .pat "$ROOT/.memory/PATS/NUGET-PAT.json")"
export PAT="$NUGET_POSTAT_CLEAR_TEXT_PASSWORD"
export WSLENV="NUGET_POSTAT_USERNAME:NUGET_POSTAT_CLEAR_TEXT_PASSWORD:PAT"

WSLROOT="$(wsl.exe wslpath -a "$ROOT" | tr -d '\r')"
case "$ACTION" in
  up)   CMD="cd '$WSLROOT' && bash csharp/tools/local-dev/start-mock-docker.sh" ;;
  test) CMD="cd '$WSLROOT' && bash csharp/tools/local-dev/backend-test.sh test $*" ;;
  *)    echo "usage: integration_stack.sh up|test [args]"; exit 2 ;;
esac
echo ">> (WSL Ubuntu) $ACTION  — secrets forwarded via WSLENV (values hidden); this is SLOW."
exec wsl.exe -d Ubuntu bash -lc "$CMD"
