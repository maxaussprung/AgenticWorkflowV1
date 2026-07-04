#!/usr/bin/env bash
# READ-ONLY backend orientation snapshot for a fresh agent — a LIVE complement to the prose in
# docs/architecture/csharp-source-architecture.md. Shows: dotnet SDK, solution projects, target
# frameworks, DbContext(es), EF migrations, dotnet-ef availability, test projects. Changes nothing.
# RUN:  bash .memory/tools/scripts/backend_info.sh
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
SLN="csharp/PostAG.Logistics.Mad.sln"

echo "=== dotnet SDK ==="; dotnet --version 2>/dev/null || echo "  dotnet not on PATH"
echo "=== solution projects ($SLN) ==="; dotnet sln "$SLN" list 2>/dev/null | sed 's#^#  #' || echo "  (sln list failed)"
echo "=== target frameworks (csproj) ==="; grep -rhoE "<TargetFramework[s]?>[^<]+</" csharp/src --include=*.csproj 2>/dev/null | sort -u | sed 's#^#  #'
echo "=== DbContext / IdentityDbContext classes ==="; grep -rlE ":\s*(Identity)?DbContext\b" csharp/src --include=*.cs 2>/dev/null | sed 's#^#  #' || echo "  none found"
echo "=== EF migrations (latest 10 filenames) ==="; find csharp/src -path "*Migrations*" -name "*.cs" ! -name "*ModelSnapshot*" -printf "%f\n" 2>/dev/null | sort | tail -10 | sed 's#^#  #'
echo "=== dotnet-ef tool ==="; dotnet ef --version 2>/dev/null | tail -1 | sed 's#^#  #' || echo "  not installed (dotnet tool install --global dotnet-ef)"
echo "=== backend test projects ==="; find csharp/test -name "*.csproj" 2>/dev/null | sed 's#^#  #'
echo; echo "Prose architecture + conventions: docs/architecture/csharp-source-architecture.md ; build/test via verify.sh."
