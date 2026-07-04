# Testing Patterns & Gotchas (backend xUnit + frontend Jest/RTL)

Verified test-writing recipes for both stacks — consolidated here so a testing learning has ONE home
(don't scatter it into 08/09). Prod-code patterns stay in [08](08-backend-patterns.md) (backend) and
[09](09-frontend-patterns.md) (frontend); this file is only about **tests**. Run gate for both:
[`tools/scripts/verify.sh`](tools/scripts/verify.sh) `frontend|backend|all` (targeted runs below).

## Run ONE test fast (save time — don't run the whole suite each iteration)
- **Frontend (Jest):** `bash tools/scripts/verify.sh frontend --jest <pattern>` (pattern = file path or
  `-t` name substring), or directly `pnpm --dir csharp/src/frontend test <pattern>`.
  For exact files with Jest flags, use `pnpm --dir csharp/src/frontend run test -- --runTestsByPath <file...>`.
  Do **not** add `--runInBand` there: the package script already sets `--maxWorkers=50%`, and Jest rejects
  both options together. If someone writes/says `--runInBank`, treat it as the same typo-prone issue:
  do not add any run-in-band flag unless you bypass the package script's `--maxWorkers`.
- **Backend (xUnit):** `bash tools/scripts/verify.sh backend --filter <expr>` — passes `--filter` to
  `dotnet test` (e.g. `--filter FullyQualifiedName~OpenCollectionCases` or `--filter Name~ReturnsOnlyOpen`).
- Use the targeted run while iterating; run the FULL `verify.sh` once before declaring done / proof / PR.

## Backend (xUnit + FakeItEasy + FluentAssertions + FakeTimeProvider)
- **Projects:** unit `csharp/test/backend/PostAG.Logistics.Mad.UnitTests`; integration
  `...API.IntegrationTests` (Testcontainers SQL → **needs Docker**, not on this dev box, so IT is
  *written + compiled* here but RUN in CI).
- **DbContext harness = EF InMemory (not sqlite).** A repo/query-handler test that needs a real
  `DirectivesDbContext` builds it with
  `new DbContextOptionsBuilder<DirectivesDbContext>().UseInMemoryDatabase(Guid.NewGuid().ToString())`
  (see `UnitTests/Infrastructure/Repositories/BranchSiteRepositoryTests.cs`). InMemory does **NOT enforce
  FK/unique constraints** — a persistence round-trip + query-filter test works there, but the
  FK-enforcement "failing write" test MUST live in `...API.IntegrationTests` (SQL, CI).
- **FakeItEasy can't build a default `ErrorOr<T>` dummy** — full detail + fix in
  [08 §GOTCHA: FakeItEasy ErrorOr dummy](08-backend-patterns.md). When you add a ctor param to a
  widely-constructed handler, grep ALL its construction sites in the test project and stub the new fake.

### GOTCHA: deserialize API responses in integration tests with the app's JSON options (string enums)
An integration test that does `httpResponse.Content.ReadFromJsonAsync<T>()` with the **default**
`System.Text.Json` options throws `JsonException: The JSON value could not be converted to <Enum>` when
`T` has an enum property — because the API serializes enums as **strings** (`JsonStringEnumConverter`),
which the default reader can't parse. Always pass `JsonSerializationHelper.JsonSerializerOptions` (in
`...IntegrationTests.Helpers`) — as `DirectiveOrdersEndpointsTests` does. This is **CI-only** (a real HTTP
round-trip); unit tests that call the repo/handler directly get the enum object and never hit it. Bit us on
REQ-COLL-001 `GetOpen_Endpoint` (`$[0].status` → `DirectivePaymentStatus`).

### GOTCHA: integration tests share ONE non-reset DB — do NOT perturb per-type counts (CI-only failure)
The `...API.IntegrationTests` all share `[Collection(TestCollections.VVFTestsCollection)]`: the
`TestWebApplicationFactory` runs `MigrateAsync()` + `DirectiveTestDataSeeder.InitializeDbForTests` **once**
and the DB is **NOT reset between tests**. So rows one test persists are visible to every other test in
the run — and this only fails in **CI** (no Docker locally, so `verify.sh` can't catch it). Concretely:
`FormulaNumber = "{GetDirectiveOrderCount(type)+1}/{code}{yy}"`, and `DirectiveOrdersEndpointsTests`
asserts an **exact** FormNumber (`"3/0124"` = seed count 2 + its own). A new test that persists synthetic
`DirectiveOrder`s of that **same type** inflates the per-type count and breaks those sibling assertions
(`3/0124` → `6/0124`, +1 per extra order). **Rule:** a synthetic order created purely to exercise your
feature MUST use a directive **type that no sibling test count/FormNumber-asserts** — mirror
`DirectiveOrderSapDebtorNumberPersistenceTests`, which uses `DirectiveType.PostOfficeBoxShipping` (only
`DropOffAuthorization` is FormNumber-asserted). Assert on your own rows **by id** (`ContainSingle(x =>
x.Id == mine)`), never on absolute list counts, so other tests' rows don't break you. (Bit us on
REQ-COLL-001 `OpenCollectionCasesTests`: 3 synthetic `DropOffAuthorization` orders → 3 CI failures. Fixed
by switching to `PostOfficeBoxShipping`.)

## Frontend (Jest + React Testing Library)
- **Custom render is `test-utils`** (`render(ui, { store })` / `{ preloadedState }`) — wraps
  Provider + NextIntl(**EN**) + amarillo Theme. So assert against the **EN** `common.json` labels.
- **Seed state** by dispatching slice actions on a `createStore()` (like `TrefferListe.test.tsx` does with
  `searchSuccess`). Mock `next/router` locally
  (`{ __esModule:true, default:{push:jest.fn()}, useRouter:()=>({locale:'en'}) }`) to assert `router.push`.
- **Fetch-on-mount page:** `jest.mock('services/<feature>')` so the epic's request is a `jest.fn` (avoids
  the MSW `onUnhandledRequest:'error'`), AND seed the store, so assertions don't depend on epic timing.

### GOTCHA: jsdom lacks `ResizeObserver` → amarillo DataTable throws on mount in tests
`ReferenceError: ResizeObserver is not defined` (from `DataTable2/.../LoadingOverlay`). Stub it in the
test file BEFORE rendering (or mock the whole DataTable, as `AddressTable.test.tsx` does):
```ts
class RO { observe(){} unobserve(){} disconnect(){} }
globalThis.ResizeObserver = RO as unknown as typeof ResizeObserver;
```
Keep the polyfill AFTER the imports (eslint `import/order` forbids a statement between import groups);
assign unconditionally (`globalThis.X ?? RO` trips `no-unnecessary-condition`).

### GOTCHA: fetch-on-mount flips `loading` async → tests must WAIT for the settled UI (determinism)
A page that dispatches `fetchX()` in `useEffect` on mount sets `loading = true` first; the mocked request
resolves on a later tick. If a test renders and immediately queries rows / clicks, it races the loading
overlay (which shows NO body rows, so a delegated row-click resolves to nothing, and the empty-state
assertion fires while data is still in-flight). Make the tests deterministic:
- Await settling before interacting: `await screen.findByTestId(...)` / `await screen.findByText(...)`
  (findBy retries until the mocked resolve lands), THEN act.
- Wrap the post-click assertion in `await waitFor(() => expect(router.push).toHaveBeenCalledWith(...))`.
- For the empty-state test, mock the service to resolve `{ data: [] }` and `await findByTestId('…-empty')`
  so `loading` has flipped back to false before asserting.

### Lint MISSES test files with `next lint --file` (run full lint before done)
`next lint --file <path>` only checks the named files — it passes while the full `pnpm lint` fails on a
sibling **test** file (`import/order` "no empty line within import group"; `no-unnecessary-condition` on
`?? []` where the type is already non-nullable). Run the full `pnpm lint` / `verify.sh frontend` before
declaring done. Strip `?? default` / `x ? y : z` where the type is already non-nullable; type a partial
lookup map as `Record<string, V | undefined>` so a `?` fallback is legitimate.

### GOTCHA: `getByLabelText`/`getByRole(name)` matches a Button's `aria-label` too — new buttons break loose label regexes
RTL's `getByLabelText(/foo/i)` and `getByRole('button', { name: /foo/i })` match an element's
**accessible name**, which for a `<button aria-label="...">` is that aria-label. So ADDING a button
whose aria-label contains a substring another field's label matches will make a previously-unique
`getByLabelText` throw "Found multiple elements". Bit us on #2209: adding the shared `BackButton` with
`ariaLabel='order-holder-back'` made a pre-existing `screen.getByLabelText(/Ord/i)` (targeting the
"Ord.Nr." companyId field) ALSO match the back button ("**ord**er-holder-back"). Fix = tighten the
query to the precise label already used by sibling tests (`/Ord.Nr./i`) — NOT weakening, just
disambiguating. Lesson: when you add a button with an `aria-label`, grep the feature's tests for loose
`getByLabelText`/`name:` regexes that could now also match it, and tighten them.

## Feed tester/UX findings back here
When a tester (Tobias) or UX (Yujiao) finding turns out to be a **test gap** (a case we should have
covered), add the missing test AND record the pattern here so the next slice covers it up front — same
"contribute back" rule as everywhere. A finding that is a prod-code gotcha goes to 08/09; a *testing*
gotcha goes here.
