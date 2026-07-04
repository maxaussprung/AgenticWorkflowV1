#!/usr/bin/env bash
# Wrap `dotnet ef` with the VERIFIED flags (see 08-backend-patterns.md): startup+project =
# Infrastructure (it has the design-time factory; the API lacks EF.Design → cryptic failure),
# --context DirectivesDbContext, --output-dir Migrations/DirectivesDb. Auto-loads the NuGet PAT.
# Build must succeed first. Complements the repo (EF is the repo's own tool) — not a new pipeline.
# RUN:
#   bash .memory/tools/scripts/ef_migration.sh add <Name>   # create a migration
#   bash .memory/tools/scripts/ef_migration.sh list          # list migrations (verify a new one applied)
#   bash .memory/tools/scripts/ef_migration.sh script        # idempotent SQL (review before commit)
#   bash .memory/tools/scripts/ef_migration.sh remove        # remove the last UNAPPLIED migration
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
CMD="${1:-list}"; NAME="${2:-}"
INFRA="csharp/src/backend/PostAG.Logistics.Mad.Infrastructure/PostAG.Logistics.Mad.Infrastructure.csproj"
: "${NUGET_POSTAT_USERNAME:=jonas.hauser@accenture.com}"
: "${NUGET_POSTAT_CLEAR_TEXT_PASSWORD:=$(jq -r .pat "$ROOT/.memory/PATS/NUGET-PAT.json")}"
export NUGET_POSTAT_USERNAME NUGET_POSTAT_CLEAR_TEXT_PASSWORD
# NOTE (self-heal 2026-07-02): the --project/--startup-project/--context flags MUST come AFTER the
# subcommand (`migrations add …`). Newer `dotnet ef` (9.0.5 here) ignores them when placed before the
# command and just prints generic help. So build the flag array separately and append it per-command.
EFFLAGS=(--project "$INFRA" --startup-project "$INFRA" --context DirectivesDbContext)
case "$CMD" in
  add)    [ -n "$NAME" ] || { echo "usage: ef_migration.sh add <Name>"; exit 2; }
          dotnet ef migrations add "$NAME" "${EFFLAGS[@]}" --output-dir Migrations/DirectivesDb;;
  list)   dotnet ef migrations list "${EFFLAGS[@]}";;
  script) dotnet ef migrations script --idempotent "${EFFLAGS[@]}";;
  remove) dotnet ef migrations remove "${EFFLAGS[@]}";;
  *) echo "usage: ef_migration.sh add <Name>|list|script|remove"; exit 2;;
esac
