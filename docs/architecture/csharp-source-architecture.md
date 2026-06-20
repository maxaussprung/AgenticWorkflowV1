# csharp/src Architecture Analysis

> Replace `{PROJECT-NAME}` and `{CLIENT-NAME}` with your actual project and client names
> throughout this document. Replace project-specific namespace prefixes (e.g.
> `{ClientName}.{ProjectName}`) with the namespaces used in your implementation.

Last reviewed: 2026-06-05.

Scope: `csharp/src/backend` and `csharp/src/frontend`. Generated EF Core migrations were
considered only as evidence for database tooling, not for naming or code-style conventions.

## Summary

The source tree is a split backend/frontend implementation for `{PROJECT-NAME}`.

The backend is a Clean Architecture-inspired layered design with DDD and CQRS patterns: API
endpoints are thin, application handlers own use cases, repositories and service abstractions are
declared in the application layer, domain aggregates model core concepts, and infrastructure
contains EF Core, Kafka, Azure, Redis, Graph, Typesense, and external API implementations.

It is not a strict Clean Architecture or Onion Architecture implementation. The dependency
direction is mostly inward, but the application layer directly uses contracts and some
infrastructure-adjacent packages, the API references infrastructure directly for composition, and
the messaging worker references infrastructure directly. Treat the current architecture as a
pragmatic layered/Clean hybrid and preserve its current dependency style unless an intentional
refactor is approved.

The frontend is a Next.js pages-router application with a Redux Toolkit model architecture. Pages
select feature components, feature folders contain UI workflows, `models/*` hold
slices/actions/epics/selectors/types, `services/*` isolate REST calls, and
redux-observable/RxJS owns asynchronous effects.

For migration planning, treat the application as a domain/workflow migration rather than a simple
CRUD rewrite. The risky behavior is concentrated in core workflow creation, compatibility rules,
lookup-driven behavior, external service integrations (address/contacts/graph/search/messaging),
EF Core persistence, and UI state transitions across the capture/order workflow. Routes are few;
business state and DTO polymorphism carry most of the behavior.

## Tech Stack

### Backend

| Area | Current stack |
|---|---|
| Runtime | .NET 8 for API/core projects; confirm worker target |
| API | ASP.NET Core minimal APIs, route groups, typed results, Swagger/Swashbuckle |
| Application flow | MediatR commands/queries and pipeline behaviors |
| Validation/errors | FluentValidation, ErrorOr, ASP.NET ProblemDetails |
| Mapping | AutoMapper profiles |
| Persistence | EF Core 8, SQL Server, EF Core migrations |
| Messaging | KafkaFlow, Confluent schema registry/Avro, `{ClientNamespace}.Events` |
| Background work | `{ClientNamespace}`.Distribution worker host queues, messaging worker service, `BackgroundService` |
| Search/indexing | Typesense |
| External systems | Microsoft Graph, Azure App Configuration, Azure Key Vault, Azure Storage locking, Redis cache, external HTTP services |
| Observability | Azure Monitor OpenTelemetry |
| Deployment | Dockerfiles, docker-compose, Azure Pipelines, Helm/Bicep assets under `csharp/azure` |

### Frontend

| Area | Current stack |
|---|---|
| Runtime/build | Node >= 18.19.1, pnpm 8.9.2, Next.js 14 standalone output |
| UI | React 18, Next.js pages router, `{CLIENT-NAME}` design system (e.g. Amarillo UI), Emotion, notistack |
| State | Redux Toolkit, React Redux, next-redux-wrapper |
| Async effects | redux-observable, RxJS |
| Forms/validation | react-hook-form, zod, `@hookform/resolvers` |
| I18n | next-intl, `translations/{locale}/common.json` |
| API mocking | MSW |
| Tests | Jest, React Testing Library, Playwright |
| Code quality | TypeScript strict mode, ESLint, Prettier, Husky/lint-staged |

The frontend declares pnpm and has `pnpm-lock.yaml`, but a large `package-lock.json` is also
present. Standardize on one lockfile strategy before automated dependency migration or
reproducibility work.

### Test Stack

| Area | Current stack |
|---|---|
| Backend unit tests | xUnit, FakeItEasy, FluentAssertions |
| Backend integration tests | `Microsoft.AspNetCore.Mvc.Testing`, Testcontainers for SQL Server/Kafka/Azurite/Typesense, WireMock.Net |
| Frontend unit tests | Jest, Testing Library, jest-dom |
| Frontend browser tests | Playwright projects for integration, system integration, and e2e |
| Coverage/reporting | coverlet, Jest coverage, junit/sonar reporters, Playwright HTML/JUnit/Azure reporter |

## Backend Architecture

### Project Roles

| Project | Role |
|---|---|
| `{ClientNamespace}.{Project}.API` | Presentation/composition layer. Configures JSON, CORS, auth, Swagger, problem details, middleware, and minimal API route groups. |
| `{ClientNamespace}.{Project}.Application` | Use-case layer. Contains MediatR commands/queries/handlers, validators, AutoMapper profiles, repository/service abstractions, and pipeline behaviors. |
| `{ClientNamespace}.{Project}.Domain` | Domain model. Contains aggregates, entities, value objects, IDs, and domain behavior for core business concepts. |
| `{ClientNamespace}.{Project}.Infrastructure` | Infrastructure adapters. Contains EF Core DbContext/configurations/migrations/repositories, external service implementations, messaging producers, worker host jobs, search/cache/Azure configuration. |
| `{ClientNamespace}.{Project}.Contracts` | API and message contracts: requests, responses, queue messages, and serialization-facing abstractions. |
| `{ClientNamespace}.{Project}.SharedKernel` | Cross-cutting enums, constants, and small extensions shared by domain/contracts/application. |
| `{ClientNamespace}.{Project}.ConsumersWorker` | Separate messaging consumer worker. Uses messaging middleware and the infrastructure repository implementation to ingest domain events. |

### Dependency Direction

Current references form this practical shape:

```text
API
  -> Application
  -> Infrastructure

Infrastructure
  -> Application

Application
  -> Contracts
  -> Domain

Contracts
  -> SharedKernel

Domain
  -> SharedKernel

ConsumersWorker
  -> Infrastructure
```

This supports dependency inversion at the use-case boundary: application handlers depend on
repository and service interfaces, while infrastructure supplies EF Core and external service
implementations. The API remains responsible for composition and can reference infrastructure
directly.

### Request Flow

Typical API flow:

1. A minimal API endpoint maps a route group in `{ClientNamespace}.{Project}.API/Endpoints`.
2. The endpoint maps request DTOs to an application command/query where needed.
3. The endpoint sends the command/query through `ISender`.
4. MediatR pipeline behaviors apply cross-cutting behavior such as validation, caching, and
   queueing an indexing message.
5. A handler coordinates domain model creation/rules, repositories, external services, and
   mapping to response DTOs.
6. The endpoint converts `ErrorOr` results to typed HTTP results.

### Data Flow

EF Core is isolated in infrastructure:

- `{Project}DbContext` exposes aggregate DbSets and applies configurations from the infrastructure
  assembly.
- Entity configurations live under `Infrastructure/Data/Configuration`.
- SQL Server migrations live under `Infrastructure/Migrations`.
- Repository interfaces live in application; EF implementations live in infrastructure.
- The worker host uses an EF-backed queue.
- `Infrastructure/Data/InitialData.cs` is lookup-heavy and migration-critical. Treat lookup
  values, translations, entity settings, and compatibility data as source data, not incidental
  seed code.
- Generated EF migrations dominate backend source volume. Separate generated migration history
  from hand-written business code when estimating or planning data-model migration work.

### Event and Async Processing

There are two asynchronous paths:

- Application writes enqueue messages through a MediatR pipeline behavior when a request
  implements `IIndexableDocumentRequest`. Infrastructure job handlers process queue messages and
  index documents in the search backend.
- The `ConsumersWorker` consumes domain events from the messaging broker, maps them to the
  relevant aggregate, compares row hashes, and creates or updates records.

The domain base types expose domain-event storage, but current production behavior mainly uses
pipeline-driven queueing and messaging producer services rather than a full domain event
dispatcher.

Search indexing has both initial/batch indexing and per-entity indexing behavior. Preserve both
paths unless a migration explicitly redesigns search freshness and rebuild semantics.

## Frontend Architecture

### Source Layout

| Folder | Role |
|---|---|
| `src/pages` | Next.js routes and static props. Pages are thin and delegate to components. |
| `src/components` | Feature/workflow components such as landing, primary workflow screens, layout, snackbar. |
| `src/common` | Reusable components, hooks, constants, and shared assets. |
| `src/models` | Redux model folders with `slice.ts`, `actions.ts`, `epics.ts`, `selectors.ts`, and `types.ts`. |
| `src/services` | REST service adapters and API payload/response types. |
| `src/core` | Cross-cutting helpers: action creators, effect model, API request creation, HOCs, intl utilities, error boundary. |
| `src/store` | Redux store setup, root reducer, root epic, typed hooks. |
| `src/mock-server` | MSW server/browser mocks. |
| `tests` | Playwright integration/system/e2e tests, fixtures, page objects, WireMock setup. |

### Frontend Flow

Typical UI/data flow:

1. A Next.js page imports a feature component and provides translation namespaces through
   `getStaticProps`.
2. Feature components connect to Redux using the local `withModelProps` HOC or typed hooks.
3. UI events dispatch reducer actions or effect actions.
4. Epics listen for effect actions, call `services/*`, and emit success/failure actions.
5. Slices update state; selectors expose state back to components.
6. Global API errors are converted into notifications through core epics.

The app intentionally disables Redux thunk and uses redux-observable for async work.

API calls are service modules over the shared fetch wrapper. `NEXT_PUBLIC_API_BASE_URL` defaults
to `https://localhost:7098` (update to match your local backend port).

The primary workflow form submission maps UI workflow state into backend DTOs through explicit
mapper modules. This mapper layer is a migration boundary because it encodes
frontend/backend contract assumptions. Do not rebuild pages/components without preserving the
state transitions across the capture/workflow models.

## Naming Conventions

### Backend

- Nullable reference types and implicit usings are enabled; C# `LangVersion` is `Latest`.
- `.editorconfig` prefers file-scoped namespaces, explicit types over `var`, PascalCase public
  symbols, `_camelCase` private fields, braces, sorted usings, readonly fields, and static local
  functions where applicable.
- Warnings-as-errors is present but commented out, so the codebase signals strictness but does
  not currently enforce it globally.
- Projects use `{ClientNamespace}.{Project}.*` names.
- Namespaces mirror folders.
- C# types use PascalCase; interfaces use the `I` prefix.
- Application use cases follow `Feature/Commands/<UseCase>` or `Feature/Queries/<UseCase>`.
- MediatR types use `*Command`, `*Query`, and `*Handler` suffixes.
- FluentValidation validators use `*Validator`.
- AutoMapper profiles use `*Mapping`.
- API endpoint extension files use `<Feature>Endpoints.cs` and expose `Map<Feature>()`.
- Repository interfaces live under `Application/Abstractions/Repositories` and use
  `I<Aggregate>Repository`.
- Repository implementations live under `Infrastructure/Repositories` and use
  `<Aggregate>Repository`.
- Domain folders are aggregate-oriented: `<Aggregate>Aggregate`, with nested `Entities`,
  `ValueObjects`, and `Events` where needed.
- Current async repository/service method names usually do not use an `Async` suffix. Preserve
  the local convention unless a broader naming cleanup is approved.

### Frontend

- Components are functional React components in feature folders, usually with colocated styles,
  tests, and `index.ts` exports.
- Higher-order composition with `compose`, `withModelProps`, and `withTranslations` is used
  heavily to connect components to Redux selectors/actions and i18n.
- Forms prefer react-hook-form controllers/uncontrolled registration with Zod schemas.
- Side effects use action triplets and epics rather than thunks.
- UI domain text is centralized in translation JSON, and pages statically pick the required
  namespaces.
- Formatting and style enforcement appear through ESLint/Prettier scripts.
- Feature/component folders use lower camelCase, for example `directiveOrdersPage`.
- React component files and component names use PascalCase.
- Model folders use lower camelCase and standard files: `slice.ts`, `actions.ts`, `epics.ts`,
  `selectors.ts`, `types.ts`.
- Service folders use lower camelCase and standard files: `service.ts`, `types.ts`, optional
  `enums.ts`.
- Barrel exports use `index.ts`.
- Redux slice names match model names.
- Selectors and action creators use lower camelCase.
- Tests live near source as `__tests__/*.test.ts(x)` for unit/component tests, while Playwright
  tests live under `tests/*`.
- Imports use TypeScript path aliases from `tsconfig.json` rather than long relative chains where
  possible.

## Design Principles in Use

- Preserve existing confirmed behavior unless a ticket or requirement explicitly changes it.
- Keep presentation thin and push business workflows into application handlers or frontend models.
- Use dependency inversion between application handlers and infrastructure adapters.
- Keep persistence and external systems outside the domain model.
- Model domain identity and equality explicitly with aggregate IDs and value objects.
- Prefer declarative validation through FluentValidation and typed DTOs.
- Centralize cross-cutting backend behavior in MediatR pipeline behaviors.
- Centralize frontend asynchronous behavior in epics rather than component-local effects where it
  is application state.
- Use integration tests with real infrastructure substitutes for behavior that depends on SQL
  Server, messaging, search, Azure storage, or external HTTP systems.

## Design Patterns Observed

| Pattern | Where it appears |
|---|---|
| Layered architecture / Clean hybrid | Backend project split and dependency direction |
| Domain-driven design tactical patterns | Aggregate roots, entities, value objects, aggregate IDs |
| CQRS | Separate command/query types and handlers |
| Mediator | MediatR dispatch from endpoints to handlers |
| Pipeline behavior | Validation, caching, indexing queue behavior |
| Repository | Application interfaces with EF Core infrastructure implementations |
| DTO / contract mapping | Contracts project plus AutoMapper profiles |
| Dependency injection/composition root | `DependencyInjection.cs`, API `ConfigureServices`, worker `CreateApplicationBuilder` |
| Options/configuration | Typed configuration classes and `IOptions<T>` |
| Minimal API route group | `Map<Feature>()` endpoint extension files |
| Worker / consumer middleware | KafkaFlow handlers and middleware, hosted `BackgroundService` |
| Cache-aside | `ICacheService` and query caching pipeline |
| Distributed lock | Concurrency-sensitive sequential-number generation uses a distributed lock |
| Polymorphic serialization | JSON polymorphic converters for request/response/domain hierarchies |
| Redux slice | Frontend `models/*/slice.ts` |
| Epic/effect | Frontend redux-observable epics and `effectActionCreator` |
| Adapter service | Frontend `services/*` wrappers around REST endpoints |
| Higher-order component | `withModelProps`, `withTranslations`, `withLocales` |
| Page Object Model | Playwright page classes under `tests/pages` |

## Architecture Gaps and Guardrails

- The backend target frameworks may differ between projects. Keep new API/core backend code on the
  surrounding project target unless the project is intentionally upgraded.
- The application layer currently knows about some infrastructure-adjacent concepts such as search
  options, indexing queues, and contract marker interfaces. Do not present the codebase as strict
  Clean Architecture unless these dependencies are removed or inverted.
- Domain-event base types exist, but domain events are not yet a complete event-dispatch mechanism.
- Contract polymorphism is non-trivial. Backend JSON serialization depends on discriminator-based
  converters for polymorphic types; frontend payload builders must preserve those discriminator
  fields exactly.
- Sequential-number generation (or equivalent) is concurrency-sensitive because it uses a
  distributed lock and derives numbers from current entity counts. Preserve this behavior or
  deliberately redesign it with explicit acceptance criteria.
- Authentication has two layers: Azure AD JWT authentication and a custom permission policy
  provider backed by roles/permissions from the database. Verify broader endpoint protection
  before relying on it during migration.
- Local and SystemIntegration behavior differs from production: memory cache vs Redis, automatic
  DB migration in Development/SystemIntegration, WireMock stubs, a search container, and
  disabled/no-op producer behavior in SI.
- Verify concrete messaging consumer behavior before relying on the worker for migration parity.
  The worker is operationally split and may have no-op handlers in certain configurations.
- The root documentation states that test commands are still TODO. Until that is resolved, use:
  backend `dotnet test csharp/{Project}.sln`; frontend from `csharp/src/frontend`:
  `pnpm lint`, `pnpm typecheck`, `pnpm test`, and the relevant Playwright script.
- Generated test output belongs under `reports/test-results` or the existing frontend report
  folders, not source folders.

## Source Inventory

Migration-analysis inventory excluded build/vendor/generated noise: `bin`, `obj`,
`node_modules`, `.next`, coverage/report folders, binary assets, lockfiles, and generated
`mockServiceWorker.js`.

The inspected snapshot contained approximately 931 files and 61,645 `cloc` code lines after those
exclusions: ~346 C# files / 28,860 code lines, ~528 TypeScript/TSX files / 23,713 code lines,
31 JSON files / 8,317 code lines, plus smaller MSBuild, Dockerfile, Markdown, JavaScript, shell,
XML, and INI files. Backend-only was approximately 385 files / 34,740 code lines by `cloc`;
frontend-only approximately 546 files / 26,905 code lines. Excluding all migrations left ~326
C# files and about 12.9k nonblank physical lines.

## How to Extend Consistently

### New Backend API Capability

1. Confirm or document the requirement under `docs/requirements`.
2. Add or update contracts in `{ClientNamespace}.{Project}.Contracts`.
3. Add an application command/query, handler, validator, and mapping in the relevant feature
   folder.
4. Put domain rules on aggregates/value objects when they are genuine business behavior.
5. Add repository/service abstractions to application only when the use case needs a boundary.
6. Implement infrastructure concerns in `{ClientNamespace}.{Project}.Infrastructure`.
7. Expose the route through a thin minimal API endpoint file.
8. Add focused unit or integration tests under `csharp/test/backend`.

### New Frontend Capability

1. Keep route files thin and delegate to feature components.
2. Add feature UI under `src/components` or reusable UI under `src/common`.
3. Add model state as a folder under `src/models` when the state is shared or workflow-level.
4. Add REST adapters under `src/services`.
5. Use epics for asynchronous API flows.
6. Add translation keys in `src/translations`.
7. Add Jest/Testing Library tests for components, reducers, selectors, services, and epics; add
   Playwright coverage for user workflows.
