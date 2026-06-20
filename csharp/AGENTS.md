# csharp/ Agent Instructions

Applies to `csharp/` — the active {PROJECT-NAME} application (backend + frontend + Azure deployment assets).

Read the repository root [`AGENTS.md`](../AGENTS.md) first. For layer-specific rules, see
[`src/backend/AGENTS.md`](src/backend/AGENTS.md), [`src/frontend/AGENTS.md`](src/frontend/AGENTS.md),
and [`azure/AGENTS.md`](azure/AGENTS.md). Architecture overview lives in
[`../docs/architecture/csharp-source-architecture.md`](../docs/architecture/csharp-source-architecture.md).

## Layout

```
csharp/
├── {ClientName}.{ProjectName}.sln    # solution aggregates backend projects only
├── docker-compose.yml                # local multi-service orchestration
├── codeCoverage.runsettings          # used by `dotnet test --settings` in CI
├── nuget.config                      # {AZURE-DEVOPS-ORG} feed; needs PAT env var locally
├── azure-pipelines*.yml              # main + kafka-consumers + typesense pipelines
├── azure/                            # pipeline templates, Helm charts, Bicep IaC
├── src/backend/                      # 7 .NET projects (API, Application, Domain, Infrastructure, Contracts, SharedKernel, ConsumersWorker)
├── src/frontend/                     # Next.js pages-router app (pnpm)
└── test/backend/                     # 4 test projects + 1 TestUtilities project
```

## Target Frameworks (mixed — do not unify without approval)

- **net8.0** — default via [`src/backend/Directory.Build.props`](src/backend/Directory.Build.props). API, Application, Domain, Infrastructure, Contracts, SharedKernel, and main test projects.
- **net9.0** — `{ClientName}.{ProjectName}.ConsumersWorker` and both `ConsumersWorker.*Tests` projects override this.

When adding projects, inherit `Directory.Build.props` (no explicit `<TargetFramework>`) unless the project must align with the worker.

## Architecture Summary

- Backend: Clean Architecture with DDD aggregate modeling, CQRS-style MediatR handlers, and hexagonal ports/adapters.
- Frontend: Next.js layered modular frontend with Redux model modules, RxJS epics, REST services, i18n, and a client UI library.
- Keep frontend and backend boundaries explicit: frontend services call backend REST APIs; backend endpoints translate HTTP requests into MediatR commands/queries.
- Preserve the migration direction from the legacy {CLIENT-NAME} codebase; do not introduce a new architectural style unless a requirement or cleanup ticket asks for it.
- `obj`, build outputs, generated reports, and local dependency caches are not source architecture and should not be treated as migration material.

## Cross-Cutting Development Rules

- Use English for technical documentation, code comments, API summaries, and developer-facing names.
- Put customer-facing UI copy in frontend translation files and preserve the client's domain terminology where the business uses it.
- Prefer existing project conventions over new abstractions: MediatR/FluentValidation/ErrorOr on backend, Redux Toolkit/redux-observable/React Hook Form/Zod on frontend.
- Keep external systems behind clear boundaries: backend infrastructure adapters for SQL Server, Kafka, Redis, Typesense, Microsoft Graph, {ExternalServiceA}, {ExternalServiceB}, Azure; frontend REST calls through `src/services` and `src/core/api/rest`.

## Build / Test / Run (canonical)

```bash
# Backend (run from csharp/)
dotnet build {ClientName}.{ProjectName}.sln
dotnet test  {ClientName}.{ProjectName}.sln                    # all backend tests (xUnit)
dotnet test test/backend/{ClientName}.{ProjectName}.UnitTests/{ClientName}.{ProjectName}.UnitTests.csproj
dotnet format                                                   # CI runs --verify-no-changes

# With coverage like CI:
dotnet test <project>.csproj --collect "Code Coverage" --settings codeCoverage.runsettings

# Local multi-service (requires PAT env var — see csharp/README.md)
docker-compose up --build

# Run individual services
dotnet run --project src/backend/{ClientName}.{ProjectName}.API/{ClientName}.{ProjectName}.API.csproj
dotnet run --project src/backend/{ClientName}.{ProjectName}.ConsumersWorker/{ClientName}.{ProjectName}.ConsumersWorker.csproj
```

Frontend commands (pnpm) live in [`src/frontend/AGENTS.md`](src/frontend/AGENTS.md).

### Local backend testing behind the corporate proxy

On some developer laptops a web proxy (e.g. Digital Guardian) intercepts the **host** `dotnet`
and blocks `dotnet restore` against the NuGet feeds (symptom: `NU1301` / `401` even though the
`NUGET_{AZURE-DEVOPS-ORG}_*` credentials are correct — a direct `curl` to the feed with the same credentials
returns `200`). Containers have their own network path and **bypass** the proxy, so `dotnet`
works inside a container.

Use the wrapper [`tools/local-dev/backend-test.sh`](tools/local-dev/backend-test.sh) instead of
calling `dotnet` directly for tests:

```bash
# Start the reusable SDK container once per session (needs NUGET_{AZURE-DEVOPS-ORG}_* in your shell):
csharp/tools/local-dev/backend-test.sh
# Then run any dotnet command through it (args are passed verbatim, workdir = csharp/):
csharp/tools/local-dev/backend-test.sh test test/backend/{ClientName}.{ProjectName}.UnitTests/{ClientName}.{ProjectName}.UnitTests.csproj \
    --collect "XPlat Code Coverage" --results-directory /src/reports/test-results
```

- The repo is **bind-mounted** at `/src`, so test output (e.g. `reports/test-results/`) lands
  straight back in the working tree — nothing is copied in or out.
- The container (`{project-name}-dev`) is **reused** across runs; the restore cache persists.
- In **CI** the wrapper detects `TF_BUILD`/`CI` and runs `dotnet` natively (no proxy there).
- **Integration tests using Testcontainers** may not run from inside that container (Docker
  socket / sibling-container networking on Colima); run them in CI, or analyse them statically.
- Cold-starting the container needs `NUGET_{AZURE-DEVOPS-ORG}_*` in the **shell that runs the wrapper**; a
  non-interactive shell (e.g. an agent's) that has not sourced your profile cannot start it —
  start it once from your terminal, then any process can reuse it.

## Testing Stack

- **xUnit 2.9.3** + **Microsoft.NET.Test.Sdk 17.14.1** across all test projects.
- Unit: FakeItEasy + FluentAssertions.
- Integration: `Microsoft.AspNetCore.Mvc.Testing`, **WireMock**, **Testcontainers** (SQL Server, Kafka, Typesense, Azure).
- Place all backend tests under `test/backend/<ProjectName>/`; do **not** colocate tests next to production code.
- Shared test helpers belong in `test/backend/{ClientName}.{ProjectName}.TestUtilities/`.

## Solution Hygiene

- `{ClientName}.{ProjectName}.sln` aggregates **backend** projects only. The frontend and Helm/pipeline YAMLs are listed as solution items but not built by `dotnet build`.
- New backend projects MUST be added to the .sln so CI picks them up.
- EF migrations: see `csharp/README.md` for the exact `dotnet ef migrations add` invocation; place migrations under `src/backend/{ClientName}.{ProjectName}.Infrastructure/Migrations/DirectivesDb/`.

## Anti-Patterns (this area)

- Do not unify `net9.0` projects back to `net8.0` (or vice versa) without an approved cleanup ticket.
- Do not commit the PAT in `nuget.config` — credentials belong in env vars or pipeline secret variables only.
- Do not place generated coverage / TRX / lcov files under `src/` or `test/`. Emit to `reports/test-results/` or the project's `bin/`/`obj/` (which `.gitignore` already handles).
- Do not introduce a second solution file; one `.sln` per backend.
