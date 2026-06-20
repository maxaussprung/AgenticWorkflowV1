# Backend Agent Instructions

This file applies to `csharp/src/backend`.

Read the repository root `AGENTS.md` and `docs/architecture/csharp-source-architecture.md` before making backend changes.

## Architecture Rules

- Preserve existing confirmed {PROJECT-NAME} behavior unless a ticket or requirement explicitly changes it.
- Treat the backend as Clean Architecture with DDD aggregate modeling, CQRS-style MediatR handlers, and hexagonal ports/adapters.
- The intended dependency direction is `API -> Application`, `API -> Infrastructure`, `Infrastructure -> Application`, `Application -> Domain`, `Application -> Contracts`, `Contracts -> SharedKernel`, and `Domain -> SharedKernel`.
- Keep API endpoint files thin. Route handlers should map requests, send MediatR commands/queries, and translate results to HTTP responses.
- Put use-case orchestration in `{ClientName}.{ProjectName}.Application`.
- Put domain identity, invariants, and behavior in `{ClientName}.{ProjectName}.Domain` aggregates/value objects when the rule is truly domain behavior.
- Put EF Core, Azure, Kafka, Redis, Graph, Typesense, HTTP clients, and other external integrations in `{ClientName}.{ProjectName}.Infrastructure`.
- Declare repository/service abstractions in application before adding infrastructure implementations.
- Keep contracts in `{ClientName}.{ProjectName}.Contracts`; do not put persistence or infrastructure concerns there.
- Keep shared enums/constants/extensions in `{ClientName}.{ProjectName}.SharedKernel` only when they are genuinely cross-cutting.
- Keep the worker as an outer adapter. It may use infrastructure registrations, but shared business rules still belong in Domain/Application.
- Watch for architecture drift: avoid framework or infrastructure package dependencies leaking into Domain/Application unless the existing local pattern already requires it.

## Database Entity Guardrails

Multiple requirements and user stories reference the same target tables/entities — e.g. several
stories may each say "Create table `BatchImportErrors`". A table is created exactly once, by
whichever slice lands first. Therefore, before acting on any "create table/entity" instruction
from a requirement, ticket, or its Database Implementation section:

1. **Check whether the entity already exists**: Domain aggregates/entities, EF configurations
   under `{ClientName}.{ProjectName}.Infrastructure/Data/Configuration`, DbContext `DbSet`s, and the
   migration model snapshots under `Infrastructure/Migrations`. Also check the SQL Landscape
   target model (`docs/requirements/legacy-coverage-landscape.md`) for the canonical name — do not
   create a near-duplicate under a different name (e.g. `ImportError` when `BatchImportErrors`
   is the documented target).
2. **If it exists, extend instead of recreate**: never drop, rename, or re-create an existing
   table because a story says "create". Compare the existing columns/keys against the
   requirement's documented schema and add only the missing columns/indexes/FKs via a new EF
   migration that preserves existing data.
3. **If it does not exist, create it once** with the full documented schema (columns, types,
   PK/FK) from the requirement's Database Implementation section, so later stories find it
   complete and only need to verify.
4. **Acceptance criteria mapping**: a "migration creates table X" criterion counts as satisfied
   when the table already exists with the documented columns — verify and record that instead of
   writing a redundant migration.

## Backend Request Flow

- Typical HTTP flow: endpoint receives DTO, maps to command/query, sends via MediatR, handler performs use case, endpoint maps result to typed HTTP response.
- Use FluentValidation pipeline behavior for request validation instead of ad hoc endpoint checks.
- Use repository/service interfaces as application ports, with SQL Server, Kafka, Redis, Typesense, Graph, {ExternalServiceA}, {ExternalServiceB}, and Azure details implemented in Infrastructure.
- Keep ProblemDetails, auth, OpenAPI, CORS, JSON serialization, localization, and composition-root wiring in the API layer.

## Coding Conventions

- Follow existing C# style: file-scoped namespaces, PascalCase public types/members, `I`-prefixed interfaces, primary constructors where already used.
- Preserve local naming patterns: `*Command`, `*Query`, `*Handler`, `*Validator`, `*Mapping`, `*Repository`, and `<Feature>Endpoints.cs`.
- Current async repository/service methods generally omit the `Async` suffix. Do not mix naming styles in the same area without an approved cleanup.
- Use `TimeProvider` for time-dependent behavior instead of direct `DateTime.UtcNow` in application code.
- Use `ErrorOr` and FluentValidation where the surrounding use case already follows that pattern.
- Add EF configurations under `{ClientName}.{ProjectName}.Infrastructure/Data/Configuration`.
- Add EF migrations only for real schema/data changes and keep them under `{ClientName}.{ProjectName}.Infrastructure/Migrations`.
- Do not commit secrets, personal tokens, or environment-specific configuration values.

## Testing

- Place backend tests under `csharp/test/backend`.
- Use xUnit, FakeItEasy, and FluentAssertions for unit tests.
- Use Testcontainers/WireMock integration tests when behavior depends on SQL Server, Kafka, Typesense, Azure storage, or external HTTP systems.
- Prefer tests that verify behavior against confirmed requirements and ticket acceptance criteria.
- Run the smallest relevant test project first; use `dotnet test csharp/{ClientName}.{ProjectName}.sln` for broader verification when feasible.
- Put generated test output under `reports/test-results` or existing generated report folders, not source folders.
