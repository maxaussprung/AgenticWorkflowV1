#!/usr/bin/env bash
# Start the full local {PROJECT-NAME} stack with the backend in the local-only offline Mock environment.
#
# Thin wrapper over start-docker.sh: it reuses the exact same flow (HTTPS dev-cert generation,
# NuGet/PAT build-secret resolution, image build, container startup, API/frontend health waits) and
# only layers the Mock override (docker-compose.mock.yml) so the API boots with
# ASPNETCORE_ENVIRONMENT=Mock (no Azure, Redis, Kafka or blob access). Use it for local human
# frontend testing of a slice whose real backend dependency is not yet available; see
# .agents/skills/mock-implementation-slice/SKILL.md.
#
# Usage (same env/args as start-docker.sh):
#   bash csharp/tools/local-dev/start-mock-docker.sh
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

export PROJECT_NAME_MOCK=1
exec "$SCRIPT_DIR/start-docker.sh" "$@"
