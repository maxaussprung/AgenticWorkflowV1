---
name: mock-implementation-slice
description: After pick-implementation-slice implements a slice and before complete-implementation-slice, decide per requirement whether the slice needs a local-only mock to be testable by a human clicking through the frontend, and add a mock adapter and/or local-DB seed only when it is needed, frontend-observable, and faithfully buildable. Everything is wired behind the local-only ASPNETCORE_ENVIRONMENT=Mock so no other environment changes, and a mock never marks a requirement done. Use between pick-implementation-slice and the testing hand-off / complete-implementation-slice.
---

# Mock Implementation Slice

Use this skill after `pick-implementation-slice` has implemented a slice and before the testing
hand-off and `complete-implementation-slice`. It can also be run manually at any point after the
slice is implemented.

The single purpose is to make a slice testable by a human clicking through the frontend on a local
machine when a real backend dependency it needs is not yet available. It does this by adding mock
adapters and/or local-database seed data that are active only in the local-only `Mock` environment.

Be conservative: most slices need no mock. Add one only when the gate in "Decide whether a mock is
needed" says you must. A mock is a local testing aid, never a substitute for the real integration.

## Required context

Read these before acting:

- `AGENTS.md`
- `docs/architecture/implementation-slice-workflow.md`
- `openspec/track.md` (the slice's row)
- `openspec/changes/<change-name>/proposal.md` and `tasks.md`
- Each affected `docs/requirements/requirements/REQ-*.md` (acceptance criteria and GUI description)
- The Mock harness if it already exists:
  `csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Mock/`,
  `csharp/src/backend/{BACKEND-API-PROJECT}/appsettings.Mock.json`, the `IsMock()` host-environment
  extension, `docker-compose.mock.yml`, and `csharp/tools/local-dev/start-mock-docker.sh`.
- The existing WireMock setup (the project's standard HTTP-dependency mock): the `wiremock` service
  in `csharp/docker-compose.yml` and its stubs under `csharp/src/frontend/tests/wiremockSetup`
  (`mappings/` + `__files/`). See an existing `mappings/<name>.json` as the reference pattern; the
  address/{EXTERNAL-API} adapter is already routed there via a configurable base URL env var.
- **The mock catalog (read this first — it saves you the analysis):**
  `csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Mock/AGENTS.md` (the index), plus the
  matching `Mock/<Service>/AGENTS.md` for any external service your slice touches. The catalog maps
  every requirement (`REQ-*`) to the external service it needs, what to mock, the UI branches it
  unblocks, and whether it is mockable today (or blocked / out-of-scope, and why).

## Preconditions

- Run only after the slice is implemented by `pick-implementation-slice`, and before the testing
  hand-off and `complete-implementation-slice`.
- The current branch must be the slice's implementation branch named in `openspec/track.md`.
- `git status --porcelain` must be clean apart from your own in-progress work; never stash, clean,
  or overwrite unrelated user changes.
- Never edit `to_be_migrated_repo/` or `legacy-sql/`.

## Scope

In scope:

- A backend port/adapter the slice calls (external customer/identity API, address service, and the
  like) that cannot be reached locally yet, where mocking its response lets a human open the
  frontend and click through the slice's pages. When the port is an HTTP client, prefer a WireMock
  stub over a hand-written C# mock (see "Add the mock").
- Reference or seed data missing from the local database that blocks a frontend flow, supplied as
  idempotent INSERT SQL executed on startup.

Out of scope:

- Anything not observable by clicking the frontend, such as outbound or fire-and-forget effects
  (publishing Kafka events, message producers, webhooks, audit emissions). Do not mock these.
- Unit or integration test doubles (those live in `csharp/test/`), CI behavior, or anything that
  runs outside the local `Mock` environment.
- Changing real behavior. Mocks must be invisible to `Development`, `Test`, `Production`, and
  `SystemIntegration`.

## Decide, per requirement, whether a mock is needed

**First, consult the mock catalog** (`Mock/AGENTS.md` + the relevant `Mock/<Service>/AGENTS.md`). Look
up each requirement's `REQ-ID`:

- Under a **mockable-now service** — the analysis is already done. That service's `AGENTS.md` row gives
  you what to mock, the UI branches, and the caveats; implement the mock **in that service's folder**
  (see "Add the mock"). Still confirm the four conditions below.
- Under **needs-contract-first** or **out-of-scope** — do not mock; record the decision and the
  catalog's blocker reason in `tasks.md`.
- **Not in the catalog** — a newly-discovered dependency. Evaluate the gate below; if you add a mock,
  also add a catalog entry (a new `Mock/<Service>/AGENTS.md` + a row in the `Mock/AGENTS.md` index).

For each requirement in the slice, add a mock only if all four conditions are true. Evaluate them in
order; the first condition that is false is enough to decide no mock for that requirement.

1. Frontend-observable. A human can reach the behavior by clicking through the frontend and see a
   result: a page renders, a list or row appears, a validation or rejection message shows. If the
   behavior is outbound-only or has no visible UI effect (for example, publishing a Kafka event),
   stop: no mock.
2. Blocked locally today. The flow is not exercisable end-to-end on a local machine right now
   because a real dependency is missing: an external API/adapter with no local access, or data
   absent from the local database. If the flow already works locally without a mock, stop: no mock.
3. Faithful mock is feasible. You can build the mock from types and contracts that already exist in
   the repo (the port interface and its response DTO). You may seed plausible test values, but you
   must not invent the shape of an unavailable external contract. A provisional field is allowed
   only under the "Honesty" rule below.
4. Real thing not yet implemented. The mock substitutes for something genuinely not built or wired
   (a stub, a `TODO`, a missing integration). Never mock over a real, working implementation.

Record each per-requirement decision (`mock` or `no mock`, plus a one-line reason) in
`openspec/changes/<change-name>/tasks.md` under a `Local mock (frontend testing)` subsection. For a
no-mock decision this `tasks.md` subsection is the only edit; do not touch the requirement `.md`
pages. If no requirement passes the gate, that subsection is the entire output: commit it and go to
the Finish condition.

## Ensure the Mock harness exists (create once if absent)

The `Mock` environment is a local-only ASP.NET environment. If the harness below is not already in
the branch, create it once; it must change nothing outside `Mock`:

- `IsMock()` host-environment extension next to the existing `IsTest()` and `IsSystemIntegration()`
  (`IsEnvironment("Mock")`).
- `csharp/src/backend/{BACKEND-API-PROJECT}/appsettings.Mock.json`, inheriting `appsettings.json`,
  with external integrations pointed at local or no-op values so the app boots with no cloud or
  broker access.
- A `Mock` profile in `csharp/src/backend/{BACKEND-API-PROJECT}/Properties/launchSettings.json`
  (`ASPNETCORE_ENVIRONMENT=Mock`).
- A DI switch in `{BACKEND-INFRASTRUCTURE-PROJECT}/DependencyInjection.cs`:
  `if (hostEnvironment.IsMock()) { /* register Mock* */ } else { /* existing real registrations, unchanged */ }`.
- `docker-compose.mock.yml`, the Mock override layered onto the base compose (api forced to
  `ASPNETCORE_ENVIRONMENT=Mock`, cloud-only deps dropped), and `csharp/tools/local-dev/start-mock-docker.sh`
  — a thin wrapper over `start-docker.sh` that sets `{PROJECT}_MOCK=1` and reuses the normal start flow
  (HTTPS cert, image build, health waits) to bring the full stack up in Mock with one command.

Make the offline gating deterministic by mirroring, not hand-picking: grep `DependencyInjection.cs`
and the API startup for the existing `IsTest()` and `IsSystemIntegration()` guards and extend each
with `IsMock()`, mirroring whichever environment already boots offline rather than choosing services
yourself. This reliably gates off App Configuration, distributed cache/Redis, Kafka producers, and
blob/lock managers; watch registration order so no real producer or client is registered before its
no-op. Gotchas seen in practice:

- Extend environment-gated startup steps too (database migration, mock-data seeding), not just DI. A
  fresh-database seed step often guards on `IsDevelopment()` or `IsSystemIntegration()` and must
  include `IsMock()` or boot throws.
- `DependencyInjection.cs` is in namespace `Microsoft.Extensions.DependencyInjection`; reference mock
  types fully-qualified or add `using ...Infrastructure.Mock;` so `MockX` resolves correctly.
- `docker-compose.mock.yml` lives at the repo root and is layered explicitly by `start-mock-docker.sh`;
  a bare `docker compose up` would skip the HTTPS cert, NuGet build secrets, and env that
  `start-docker.sh` provides, so always start Mock through the wrapper.

Keep these harness files byte-stable across slices so they merge cleanly.

## Add the mock (only for requirements that passed the gate)

The goal is a mock that is live in the **locally-running Mock application a human clicks through**
(`bash csharp/tools/local-dev/start-mock-docker.sh`). Whatever mechanism you pick, it must be
reachable and return data when the app runs in `Mock` mode, so a human can click the frontend and
see the seeded data and every UI branch.

**Put the mock in its service folder.** Mock code lives in the matching
`csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Mock/<Service>/` folder, next to that
service's `AGENTS.md` (e.g. the example folders `Mock/EXAMPLE-SITE-MOCK/`, `Mock/EXAMPLE-CRM-MOCK/`, `Mock/EXAMPLE-DATABASE-MOCK/`, or your real per-service folders). After implementing,
update that `Mock/<Service>/AGENTS.md` (mark the requirement implemented) and the top-level
`Mock/AGENTS.md` index if the service's status changed — keep the catalog the single source of truth.
For a brand-new external service not yet in the catalog, create `Mock/<NewService>/AGENTS.md` (same
template as the existing ones) and add a row to the index.

Pick the minimal mechanism, in this order of preference:

1. HTTP-port dependency, prefer a WireMock stub. The repo already runs a `wiremock` service
   (`csharp/docker-compose.yml`) that mounts `csharp/src/frontend/tests/wiremockSetup` (`mappings/` +
   `__files/`), and HTTP adapters are routed to it by environment — for example
   a configurable base URL env var already points the address/{EXTERNAL-API} `HttpClient` at
   WireMock in the docker stack. To mock such a dependency, add a `mappings/<name>.json` stub (with a
   `__files/<name>.json` response body) returning the canned response for the exact request the
   adapter makes, following an existing `mappings/<name>.json` stub as the example. This is declarative
   (no C# class) and exercises the real adapter's HTTP and deserialization code (the most faithful
   mock). It uses the `wiremock` service in the docker stack. Crucially, make the stub reach the
   human's Mock run: while running in `Mock`, the adapter's base URL must point at the `wiremock`
   service and that service must be up. The base `docker-compose.mock.yml` drops the Typesense/AddressDomain (wiremock)
   wiring from the api for offline boot, so when you mock an HTTP dependency via WireMock you must
   re-add that adapter's `wiremock` base URL (and the `wiremock` service / `depends_on`) to the Mock
   run — otherwise the stub serves only the normal stack, not the Mock app a human clicks through.
   WireMock can only intercept a dependency that is already an HTTP client with a configurable base URL.
2. Non-HTTP port, or no HTTP adapter exists yet, use a C# `Mock<Service>` DI swap. When the
   dependency is not an HTTP call, or is still an in-process stub with no HTTP client to point at
   WireMock, add `Mock<Service>` in that service's folder
   `csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Mock/<Service>/` (namespace mirrors the
   folder; type name prefixed `Mock`). It implements the same port interface as the real adapter and returns
   faithful, seeded responses that cover every UI branch the requirement specifies (for example
   match, no-match, below-threshold). Register it under the `IsMock()` switch only. When the real
   integration will be an HTTP call, prefer building that HTTP adapter and stubbing it with WireMock
   instead.
3. Missing local-database data, seed it. First prefer extending an existing seed or initializer (for
   example the database data initializer that already runs under offline environments) under
   `IsMock()`. Only if no seed mechanism exists, add an idempotent `*.sql` INSERT script under
   `csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Mock/<Service>/Sql/` plus a hosted-startup runner
   that executes every `*.sql` there only under `IsMock()` after migrations (idempotent, so repeated
   boots are safe).

Keep seed data minimal: only what is needed to click through the requirement's UI branches. Use
obviously-fake but realistic values, and note the exact inputs that drive each outcome. If the
frontend filters or branches client-side (for example, it keeps only `level === '90'`), the mock
must still return the would-be-filtered rows so that branch is reachable. Match the existing
endpoint's empty-result contract (for example HTTP `204` versus `200` with `[]`).

## Honesty: a mock never makes a requirement done

- Do not set the feature `csharp_status: done`, set `status: done`, or remove a requirement's
  `in-progress` state on the basis of a mock. The requirement stays `status: in-progress`/blocked.
- In `tasks.md` (and `validation.md` if the slice has one), state plainly that the requirement is
  locally testable via Mock while the real integration is still pending, and keep the real-wiring
  item open as a deferred blocker.
- Any provisional field added to a real DTO to enable a mock must default to a value that produces
  no behavior change on the real path, and must carry a `// PROVISIONAL (mock only) ...` comment.

## Verify, debug, and report

If at least one mock was added:

1. Build the backend; resolve any build break before continuing.
2. Run the backend unit tests and confirm there is no regression from the harness or mock wiring.
3. Boot the full stack in Mock mode (`bash csharp/tools/local-dev/start-mock-docker.sh`) and confirm
   the mock is live for a human, which is the point of this skill: actually exercise the slice's
   frontend route — click through it, or curl the exact endpoint the frontend calls — and confirm the
   mocked data renders and every UI branch is reachable (`curl -k`; the local HTTPS dev-cert can fail
   a PowerShell `Invoke-WebRequest` handshake). (`dotnet run --launch-profile Mock` boots the backend
   alone for a quick DI/offline check, but only the full stack lets you click the frontend.)
4. If the slice's frontend was touched by the mock wiring, run the frontend typecheck and lint.
5. Fix anything that does not build, test, or run cleanly before finishing. A mock that leaves the
   app red is worse than no mock.

Do not add unit tests that merely assert on invented seed data; that is throwaway coverage. Add a
test only if it guards the `Mock` wiring contract itself and is durable.

Document what you did: the per-requirement decision subsection in `tasks.md`, any harness changes,
each mock added, and the exact frontend test triggers (which input produces which UI outcome) so a
human can click through it. Commit with explicit paths and push.

A pure no-mock run has nothing to build or boot; skip this section apart from committing the
`tasks.md` decision subsection.

## Running the app in a chosen mode

- Local backend only: `dotnet run --launch-profile Mock` (or `Development`, `Test`, and so on).
- Full stack, normal: `bash csharp/tools/local-dev/start-docker.sh`.
- Full stack, Mock (one command): `bash csharp/tools/local-dev/start-mock-docker.sh` — reuses the
  normal start (HTTPS cert, image build, health waits) and layers `docker-compose.mock.yml`. Do not
  start Mock with a bare `docker compose up`: it skips the cert, NuGet build secrets, and env the
  start script provides.

## Finish condition

Report:

- Per requirement: mock added or not, with the gate reason.
- Harness changes, if any.
- Each mock added and the exact local frontend test triggers.
- Build, test, and Mock-boot results.
- Confirmation that no requirement was marked done on the basis of a mock.

Hand off to the testing subagent (if present), then to `complete-implementation-slice`. Mocked
requirements remain `status: in-progress`/blocked; `complete-implementation-slice` must not mark
them done on the basis of a mock.
