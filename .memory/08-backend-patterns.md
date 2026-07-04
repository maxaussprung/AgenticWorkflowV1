# Backend Patterns & Gotchas (.NET vertical slices)

Distilled, verified recipes for adding backend features to `csharp/src/backend` (Clean Architecture +
DDD + CQRS/MediatR + EF Core). Complements `docs/architecture/csharp-source-architecture.md` and the
backend `AGENTS.md`; use `tools/scripts/backend_info.sh` for a live orientation snapshot. Reason from
this instead of re-deriving the layout each time.

## The vertical-slice recipe (new persisted entity + write + query + endpoint)
> **Before adding anything, reuse what exists** (core rule — see [README](README.md#core-principle--no-double-implementation-clean-architecture-follow-the-repos-own-guidelines)).
> Grep for an existing entity / enum / query / endpoint / service that already covers it and **extend**
> it — do NOT add a parallel handler, a second repo, or a duplicate DTO. Respect the Clean-Architecture
> layer boundaries (Domain → Application → Infrastructure → API) and the repo's own
> `docs/architecture/csharp-source-architecture.md` + the nearest `AGENTS.md`. No spaghetti, no
> double implementation, clean separation of concerns.

Order that compiles cleanly and matches the repo (mirror the **SamImports / BatchImport** slice — the
freshest full example):
1. **SharedKernel enum** (if needed) → `SharedKernel/Enums/*.cs`, `: byte` for status/action enums.
2. **Domain aggregate** → `Domain/<Name>Aggregate/<Name>.cs` + `ValueObjects/<Name>Id.cs`
   (`: AggregateRootId<Guid>`, private ctor, static `Create`/`CreateUnique`). For an **append-only /
   immutable** aggregate expose **no mutator** after `Create` (a reflection test can assert this).
3. **EF config** → `Infrastructure/Data/Configuration/<Name>Configuration.cs`
   (`builder.ToTable(TableNames.X)`, `HasConversion` on the id VO, `HasConversion<byte>()` on enums,
   `HasMaxLength(TextSizePresets.*)`, `HasIndex`). Add the table name to `Infrastructure/Data/TableNames.cs`.
4. **DbSet** on `Infrastructure/Data/DirectivesDbContext.cs` (configs auto-apply via
   `ApplyConfigurationsFromAssembly`).
5. **Application ports** → `Application/Abstractions/Repositories/I<Name>Repository.cs` (and a service
   port under `Abstractions/Services/`). Keep an **audit/append-only** repo `Create`+`Search` only.
6. **Infrastructure impl** → `Infrastructure/Repositories/<Name>Repository.cs` (ctor-inject
   `DirectivesDbContext`; `dbContext.Set.Add` + `SaveChangesAsync`; `.AsNoTracking()` for reads).
7. **Contracts** → `Contracts/<Feature>/Requests|Responses/*.cs`. **XML-doc every public member** —
   Contracts (and other projects) enforce CS1591 as it shows in build; missing docs = warnings.
8. **Query/Command + Handler** → `Application/<Feature>/Queries|Commands/...` returning
   `ErrorOr<T>`, `IRequest<>`; explicit `ToResponse()` mapping extension (AutoMapper is used for the
   big DirectiveOrder graph, but small responses are hand-mapped — see `SamImportResponseMapping`).
9. **Endpoint** → `API/Endpoints/<Feature>Endpoints.cs` (`namespace Microsoft.AspNetCore.Routing;`,
   `MapGroup`, `[AsParameters]` for GET filters, `TypedResults`), then register the `Map…()` call in
   `API/Extensions/WebApplicationExtensions.cs` (`ConfigurePipeline`).
10. **DI**: register repo in `Infrastructure/DependencyInjection.cs` `AddRepositories()`, service in
    `AddServices()`. MediatR/validators/AutoMapper auto-register by assembly scan.
11. **Mock seed** (optional, frontend-observable): `ITestDataGenerator<T>` in
    `Infrastructure/Data/TestData/Fake*DataGenerator.cs` (`Generate()` + `ShouldGenerate(db)` when
    empty). Auto-discovered by `DirectivesDbDataInitializer` when `GenerateMockData=true`.

## EF migration command (VERIFIED — the API startup project trips people up)
> Just run [`tools/scripts/ef_migration.sh`](tools/scripts/ef_migration.sh) `add <Name>` | `list` |
> `script` | `remove` — it applies these exact flags + auto-loads the NuGet PAT. The raw command below
> is what it runs (reference / one-off variants).

`dotnet ef` fails with *"startup project doesn't reference Microsoft.EntityFrameworkCore.Design"* if you
point `--startup-project` at the **API**. Use **Infrastructure as its own startup** (it has the
design-time factory `BaseDesignTimeDbContextPipelineFactory`):
```bash
export NUGET_POSTAT_USERNAME=jonas.hauser@accenture.com
export NUGET_POSTAT_CLEAR_TEXT_PASSWORD=$(jq -r .pat .memory/PATS/NUGET-PAT.json)
dotnet ef migrations add <Name> \
  --project        csharp/src/backend/PostAG.Logistics.Mad.Infrastructure/PostAG.Logistics.Mad.Infrastructure.csproj \
  --startup-project csharp/src/backend/PostAG.Logistics.Mad.Infrastructure/PostAG.Logistics.Mad.Infrastructure.csproj \
  --context DirectivesDbContext --output-dir Migrations/DirectivesDb
```
Migrations live in `Infrastructure/Migrations/DirectivesDb`. `dotnet ef` v9 is installed; the build must
succeed first. Migrations auto-apply on startup only in Development/SystemIntegration/Mock.

## DirectivePaymentStatus enum — the "open" set (VERIFIED)
`SharedKernel/Enums/DirectivePaymentStatus.cs` has exactly **`Unpaid, Paid, Pending`** (no Overdue/Cancelled
despite older doc wording that says "Open/Overdue"). So an "open collection case" = `PaymentStatus ∈ {Unpaid,
Pending}`; `Paid` is settled. `DirectiveOrder.PaymentStatus` already carries it and the count endpoint
`GET /directives/orders/{paymentStatus}/count` (`GetDirectivesCountByPaymentQuery`) already filters on it
(`CaseInsensitiveEnum<DirectivePaymentStatus>` route param). The SessionInformation "Unpaid count = 165"
badge reads `GET /directives/orders/Unpaid/count`.

## DirectiveOrder read model — join fields for a list projection (VERIFIED)
For a list row that needs Kundenname / Formularnummer / Auftragsdatum / Status, join `DirectiveOrder`:
- **Kundenname** → `CustomerIdentification.FirstName + " " + LastName` (entity `DirectiveOrderAggregate/Entities/CustomerIdentification.cs`, `.Include(o => o.CustomerIdentification)`).
- **Formularnummer** → `DirectiveOrder.FormulaNumber` (string, format `"{index+1}/{code}{yy}"`).
- **Auftragsdatum** → owned `Period.ValidFrom` (`ValidityPeriod`, owned type; there is no separate CreatedAt on the order).
- **Status/Id** → `PaymentStatus` / `Id` (`DirectiveOrderId`, HasConversion to Guid).
No FK-to-Orders precedent from a converted-Guid property except owned children; the SAM `BatchImport` slice
stores `OrderId`/`DirectiveId` as a **converted-Guid column with an index, NO DB-level FK** (EF can't target
an `AggregateRootId<Guid>` PK from a converted FK). Follow that for any new table referencing Orders.

## GOTCHA: converted value-object ids don't translate under `Contains` / join / `.Value` (SQL vs InMemory)
Unit tests use **EF InMemory** (client-eval) so they PASS queries that **do not translate to SQL** — the
break only surfaces in the **CI integration suite** (real SQL) as an **HTTP 500**. Verified on
REQ-COLL-001: filtering orders by `List<DirectiveOrderId>.Contains(order.Id)` compiled + passed all unit
tests but threw on SQL Server. These do **NOT** translate over converted VO ids:
- `List<DirectiveOrderId>.Contains(order.Id)` (a set filter over the converted key),
- a LINQ `join ... on billing.OrderId equals order.Id` (also fails InMemory with a key-type mismatch:
  `order.Id` is the base `AggregateRootId<Guid>`, not `DirectiveOrderId`),
- `record.OrderId.Value` inside the query (accessing the underlying Guid of a converted property).
What DOES translate: **single equality** `x.Id == DirectiveOrderId.Create(guid)` (see
`DirectiveOrderRepository.GetById`) and **enum `array.Contains(x.PaymentStatus)`** → an SQL `IN`
(`GetDirectiveOrderCount`). **Pattern for "rows whose converted-id is in a set":** filter each table by a
translatable predicate (e.g. the enum status `IN`), project primitives, `ToListAsync`, then **join in
memory by `id.Value` (Guid)** and compose strings there. Never trust unit-test green for a query shape —
if it uses a converted key in a `Contains`/join, it will 500 on SQL. See [10](10-testing-patterns.md)
(integration tests are CI-only, no Docker locally).

## Mock-only seed that depends on already-persisted rows
The generic `ITestDataGenerator<T>` auto-discovery (`DirectivesDbDataInitializer`) runs whenever
`GenerateMockData=true` — which is true in Development, base, Mock AND SystemIntegration (only Test=false), and
its `Generate()` has **no DB access** (only `ShouldGenerate(db)` does). So it's the wrong hook for a seed that
must be (a) Mock-only and (b) derived from existing open orders. Instead add a dedicated step in
`API/Extensions/WebApplicationExtensions.cs` `SeedMockData(app)` guarded by `app.Environment.IsMock()`
(`Infrastructure/Extensions/IHostEnvironmentExtensions.IsMock()` = `IsEnvironment("Mock")`): open a scope,
read the open orders, insert one BillingRecord each, save. Runs after `ApplyPendingMigrations` + the generic seed.

## Acting user / request context (REQ-IDM / audit)
There is **no `ICurrentUser` service**. Resolve the actor **at the endpoint** from the principal:
`httpContext.User.Identity?.Name ?? "unknown"` (the SAM-import + audit-log pattern), and the IP from
`httpContext.Connection.RemoteIpAddress?.ToString()`. Pass them on the command as extra properties
(default `"unknown"` so existing callers/tests keep compiling — additive, not a mapped request field).

## GOTCHA: FakeItEasy can't build a default `ErrorOr<T>` dummy
`A.Fake<ISomething>()` whose method returns `Task<ErrorOr<T>>` throws at call time:
*"Default construction of ErrorOr<TValue> is invalid. Please use provided factory methods."* So any
**existing** test that fakes a collaborator you newly call must stub it, or it breaks with a confusing
error (looks unrelated to your change). Fix: in the test ctor add
`A.CallTo(() => _fake.Method(A<...>._, A<CancellationToken>._)).Returns(Result.Success);`
(`using ErrorOr;`). When you add a ctor param to a widely-constructed handler
(e.g. `CreateDirectiveOrderCommandHandler`), grep **all** its construction sites across the test project
and add the fake arg + the default `Returns(Result.Success)` stub.

## Tests → see [10-testing-patterns.md](10-testing-patterns.md)
The backend test harness (EF-InMemory DbContext, unit vs Docker-only integration split, targeted
`verify.sh backend --filter`, the FakeItEasy `ErrorOr` stub above) lives in
[10-testing-patterns.md](10-testing-patterns.md). Write tests from there.
