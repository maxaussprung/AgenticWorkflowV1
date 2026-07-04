#!/usr/bin/env bash
# Fast "where does this live + which conventions apply" navigator for one code area, so an agent
# jumps straight to the right dirs/files instead of re-discovering the layout (saves tokens/time).
# Complements find_route.sh (route+testid lookup) and backend_info.sh (live backend snapshot). Prints
# canonical dirs, the nearest AGENTS.md, the memory recipe file, and the key patterns for the area.
# RUN:  bash .memory/tools/scripts/code_map.sh <area>
#   areas: frontend | backend-api | backend-application | backend-domain | backend-infra |
#          backend-migrations | tests
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
AREA="${1:-}"
FE="csharp/src/frontend"; BE="csharp/src/backend"; TB="csharp/test/backend"
p() { printf '  %s\n' "$1"; }

case "$AREA" in
  frontend)
    echo "== FRONTEND (Next.js pages-router, Redux Toolkit + redux-observable, Amarillo UI) =="
    p "pages (thin routes)     $FE/src/pages"
    p "feature components      $FE/src/components/<feature>/  (Component.tsx + styles.ts + __tests__/)"
    p "shared UI/hooks         $FE/src/common"
    p "state (per model)       $FE/src/models/<model>/ (slice.ts actions.ts epics.ts selectors.ts types.ts)"
    p "REST adapters           $FE/src/services   (mechanics in src/core/api/rest)"
    p "store wiring            $FE/src/store/rootReducer.ts + rootEpic.ts   (register new model here)"
    p "i18n (de default, en)   $FE/src/translations/de|en/common.json"
    p "component barrel        $FE/src/components/index.ts"
    p "AGENTS.md               $FE/AGENTS.md"
    p "memory recipe           .memory/09-frontend-patterns.md  (+ 02 UX checklist, 10 tests)"
    p "route+testid lookup     bash .memory/tools/scripts/find_route.sh <keyword>"
    ;;
  backend-api)
    echo "== BACKEND API (thin endpoints -> MediatR; ProblemDetails/auth/OpenAPI/DI composition root) =="
    p "endpoints (thin)        $BE/PostAG.Logistics.Mad.API/Endpoints/<Feature>Endpoints.cs"
    p "pipeline/extensions     $BE/PostAG.Logistics.Mad.API/Extensions"
    p "AGENTS.md               $BE/AGENTS.md   |   memory: .memory/08-backend-patterns.md"
    ;;
  backend-application)
    echo "== APPLICATION (use cases: Commands/Queries + Handlers + Validators + ports) =="
    p "use cases               $BE/PostAG.Logistics.Mad.Application/<Area>/Commands|Queries"
    p "ports (abstractions)    $BE/PostAG.Logistics.Mad.Application/Abstractions/{Repositories,Services}"
    p "provisional events      $BE/PostAG.Logistics.Mad.Application/DirectiveOrders/Events/Provisional"
    p "memory recipe           .memory/08-backend-patterns.md (vertical-slice recipe, ErrorOr gotcha)"
    ;;
  backend-domain)
    echo "== DOMAIN (DDD aggregates, value objects, invariants) =="
    p "aggregates              $BE/PostAG.Logistics.Mad.Domain/<Aggregate>Aggregate"
    p "shared enums/constants  $BE/PostAG.Logistics.Mad.SharedKernel"
    p "memory recipe           .memory/08-backend-patterns.md (DirectivePaymentStatus open set, etc.)"
    ;;
  backend-infra)
    echo "== INFRASTRUCTURE (EF Core, Kafka, Redis, Typesense, Graph, KCRM/PERI, Azure, DI) =="
    p "composition root        $BE/PostAG.Logistics.Mad.Infrastructure/DependencyInjection.cs"
    p "DbContext + config      $BE/PostAG.Logistics.Mad.Infrastructure/Data (Configuration/, TableNames.cs)"
    p "repositories            $BE/PostAG.Logistics.Mad.Infrastructure/Repositories"
    p "services (Kafka/etc.)   $BE/PostAG.Logistics.Mad.Infrastructure/Services"
    p "Kafka settings/topics   $BE/PostAG.Logistics.Mad.Infrastructure/Configuration/KafkaSettings.cs"
    p "Mock env adapters/seed  $BE/PostAG.Logistics.Mad.Infrastructure/Mock  (ASPNETCORE_ENVIRONMENT=Mock)"
    p "memory recipe           .memory/08-backend-patterns.md"
    ;;
  backend-migrations)
    echo "== EF MIGRATIONS (DirectivesDbContext) =="
    p "migrations dir          $BE/PostAG.Logistics.Mad.Infrastructure/Migrations/DirectivesDb"
    p "model snapshot          .../Migrations/DirectivesDb/DirectivesDbContextModelSnapshot.cs"
    p "add a migration (VERIFIED flags): bash .memory/tools/scripts/ef_migration.sh add <Name>"
    p "list/script/remove:               ef_migration.sh list|script|remove"
    p "memory recipe           .memory/08-backend-patterns.md (exact dotnet ef command)"
    ;;
  tests)
    echo "== TESTS (frontend Jest/RTL + backend xUnit; conventions in root AGENTS.md) =="
    p "frontend unit/RTL       $FE/src/**/__tests__/<Name>.test.tsx"
    p "frontend Playwright     $FE/tests/{integrationtests,systemIntegration,e2e}"
    p "backend xUnit           $TB/<Project>/...Tests.cs   (TestUtilities in $TB/PostAG.Logistics.TestUtilities)"
    p "run ONE fast            bash .memory/tools/scripts/verify.sh frontend --jest <pat> | backend --filter <expr>"
    p "integration (WSL+Docker, slow, on-demand): bash .memory/tools/scripts/integration_stack.sh test"
    p "memory recipe           .memory/10-testing-patterns.md"
    ;;
  *)
    echo "usage: code_map.sh <area>"
    echo "areas: frontend | backend-api | backend-application | backend-domain | backend-infra | backend-migrations | tests"
    exit 2 ;;
esac
