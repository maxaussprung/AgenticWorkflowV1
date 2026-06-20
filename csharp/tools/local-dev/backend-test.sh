#!/usr/bin/env bash
set -Eeuo pipefail

# Run `dotnet` for the {PROJECT-NAME} backend so it works on a developer laptop where the corporate
# proxy blocks `dotnet restore` against the NuGet feeds.
#
#   Locally  -> route dotnet through a persistent .NET SDK container ('{project-name}-dev'). The proxy
#               is bypassed inside containers, and the repo is bind-mounted at /src so test
#               output (e.g. reports/test-results/) lands straight back in the working tree.
#   In CI    -> dotnet reaches the feeds natively, so just run it directly.
#
# The container is started once and reused (the restore cache persists between runs).
#
# Usage:
#   csharp/tools/local-dev/backend-test.sh                       # just ensure the env is ready
#   csharp/tools/local-dev/backend-test.sh restore {ClientName}.{ProjectName}.sln
#   csharp/tools/local-dev/backend-test.sh test test/backend/{ClientName}.{ProjectName}.UnitTests/{ClientName}.{ProjectName}.UnitTests.csproj \
#       --collect "XPlat Code Coverage" --results-directory /src/reports/test-results
#
# Arguments are passed verbatim to `dotnet` (workdir = csharp/). Force native dotnet with
# USE_NATIVE_DOTNET=1; CI is auto-detected via TF_BUILD / CI.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CSHARP_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$(cd -- "$CSHARP_DIR/.." && pwd)"

CONTAINER="${PROJECT_DEV_CONTAINER:-{project-name}-dev}"
SDK_IMAGE="${PROJECT_DEV_SDK_IMAGE:-mcr.microsoft.com/dotnet/sdk:8.0}"

log() { printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# --- CI / native path -------------------------------------------------------------------
if [ -n "${TF_BUILD:-}" ] || [ -n "${CI:-}" ] || [ "${USE_NATIVE_DOTNET:-0}" = "1" ]; then
  command -v dotnet >/dev/null 2>&1 || die "dotnet not found on PATH (native mode)."
  [ "$#" -eq 0 ] && exit 0
  cd "$CSHARP_DIR"
  exec dotnet "$@"
fi

# --- local containerised path -----------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker not found and not in CI; cannot run backend dotnet (the proxy blocks the host)."

container_running() {
  [ -n "$(docker ps --filter "name=^/${CONTAINER}$" --filter "status=running" --format '{{.Names}}')" ]
}

if ! container_running; then
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true   # clear a stopped leftover with the same name
  : "${NUGET_FEED_USERNAME:?Set NUGET_FEED_USERNAME in your shell (see csharp/README.md) before first start.}"
  : "${NUGET_FEED_CLEAR_TEXT_PASSWORD:?Set NUGET_FEED_CLEAR_TEXT_PASSWORD in your shell before first start.}"
  log "Starting '$CONTAINER' ($SDK_IMAGE) with the repo bind-mounted at /src…"
  docker run -d --name "$CONTAINER" \
    -v "$REPO_ROOT":/src -w /src/csharp \
    -e NUGET_FEED_USERNAME="$NUGET_FEED_USERNAME" \
    -e NUGET_FEED_CLEAR_TEXT_PASSWORD="$NUGET_FEED_CLEAR_TEXT_PASSWORD" \
    "$SDK_IMAGE" sleep infinity >/dev/null
fi

if [ "$#" -eq 0 ]; then
  log "'$CONTAINER' is up. Pass dotnet arguments to run a command, e.g. 'test <project>.csproj'."
  exit 0
fi

# Pass args straight to dotnet inside the container; -w avoids any shell re-quoting of spaces.
exec docker exec -w /src/csharp "$CONTAINER" dotnet "$@"
