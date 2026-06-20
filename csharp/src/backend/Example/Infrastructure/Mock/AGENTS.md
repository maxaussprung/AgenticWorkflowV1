# Mock Catalog — external-service mocks (index)

This folder is the **catalog of external-service mocks** for the local-only `Mock` environment
(`ASPNETCORE_ENVIRONMENT=Mock`). It is read by agents running the `mock-implementation-slice`
skill.

## What this is (read first)

When you implement a slice, a requirement may depend on an **external service** (address service,
customer system, …) that is not reachable on a local machine. To let a human click through the
slice in the frontend, that dependency is faked behind the `Mock` environment. This catalog tells
you **which requirements need which external service, what exactly to mock, and where the mock
lives** — so the mocks stay in one uniform per-service structure instead of scattered ad-hoc files.

**This catalog is a MAP, not an implementation.** Most entries are not implemented yet. Each
per-service `AGENTS.md` lists the requirements that need it; the mock code is added only when a
slice that owns one of those requirements is implemented (per `mock-implementation-slice`).

## How to use it (agent workflow)

1. Look up each requirement (`REQ-*`) in your current slice in the **Service → requirements** table
   below (Ctrl-F the REQ-ID).
2. If it appears under a **mockable-now** service, open that service's `AGENTS.md`
   (`Mock/<Service>/AGENTS.md`), find your REQ row (what to mock + UI branches + caveats), and
   implement the mock **in that same folder** following the `mock-implementation-slice` skill.
3. If it appears under **needs-contract-first** or **out-of-scope**, do **not** build a mock — record
   the per-requirement decision (and the blocker) in your change's `tasks.md` as the skill requires.
4. If your REQ-ID is in **none** of the tables, it needs no external-service mock.

## Folder layout (uniform)

```
Mock/
  AGENTS.md                        <- this index
  EXAMPLE-SITE-MOCK/     AGENTS.md <- example: address/location service (I{ServiceA} / {ServiceA}Adapter)
  EXAMPLE-CRM-MOCK/      AGENTS.md <- example: customer/identity (CRM) service (I{ServiceB} / {ServiceB}Adapter)
  EXAMPLE-DATABASE-MOCK/ AGENTS.md <- example: reference-data service (I{ServiceC}Repository)
  <Service>/             <Mock*.cs> <- mock code, when a slice implements it (one folder per service)
```

The `EXAMPLE-*-MOCK/` folders are **placeholders** showing the per-service structure. Rename them
to the actual external services for this project (e.g. `AddressService/`, `CustomerService/`), or
add/remove folders as needed — one folder per external service. The `setup-repo-structure` skill
renames these during repo setup.

When real mock code is added (e.g. `Mock{ServiceA}.cs`, `Mock{ServiceB}.cs`), it lives **inside
the matching service folder** next to that folder's `AGENTS.md`.

## Mockable-now services (existing repo seam → have a folder)

| Service | Real seam (interface · adapter · DTO) | Mock mechanism | Requirements | Folder |
|---|---|---|---|---|
| **{ExternalServiceA}** ({e.g. address service}) | `I{ServiceA}` · `{ServiceA}Adapter` (HTTP `{ServiceA}:ApiUrl`) · `{ServiceA}Response` | WireMock stub (preferred) or `Mock<…>` DI swap | {REQ-ID}, {REQ-ID}, … | [EXAMPLE-SITE-MOCK/](EXAMPLE-SITE-MOCK/AGENTS.md) |
| **{ExternalServiceB}** ({e.g. customer service}) | `I{ServiceB}` · `{ServiceB}Adapter` (static in-memory stub or HTTP) · `{ServiceB}Response` | `Mock<…>` DI swap / extend stub data | {REQ-ID}, {REQ-ID}, … | [EXAMPLE-CRM-MOCK/](EXAMPLE-CRM-MOCK/AGENTS.md) |
| **{ExternalServiceC}** ({e.g. reference data}) | `I{ServiceC}Repository` · local `{Entity}` table (fed by inbound event/Kafka) | DB seed under `IsMock()` (table is empty locally) | {REQ-ID}, {REQ-ID}, … | [EXAMPLE-DATABASE-MOCK/](EXAMPLE-DATABASE-MOCK/AGENTS.md) |

> **How to populate this table for a new project:**
> 1. Identify all external services that requirements depend on.
> 2. For each service, locate its port interface and adapter in the repo.
> 3. Determine the mock mechanism (WireMock stub for HTTP adapters; DI swap for in-process stubs;
>    DB seed for locally-backed repositories).
> 4. List the requirement IDs that need each service.
> 5. Create a folder and `AGENTS.md` for each service following the pattern in the sub-folders.

## Needs-contract-first (external service required, but NO repo port/DTO yet → not mockable today)

Do not mock these from thin air — building a faithful mock first needs a real port + DTO in the repo
(criterion 3 of the skill). Recorded here so the need is not lost. Build the adapter/contract, then
add a folder.

| Service | Requirements | Blocker |
|---|---|---|
| **{ExternalServiceD}** ({e.g. billing/counter system}) | {REQ-ID}, {REQ-ID}, … | No port/DTO in repo yet. |
| **{ExternalServiceE}** ({e.g. document store}) | {REQ-ID}, {REQ-ID}, … | No adapter/DTO. |
| **{ExternalServiceF}** ({e.g. printing/label service}) | {REQ-ID}, {REQ-ID}, … | No adapter/DTO. |
| **{Identity/Auth service}** | {REQ-ID}, {REQ-ID}, … | Auth/identity infra — verify before mocking. |

> Add rows here for any external service a requirement references but no repo seam exists yet.

## Out-of-scope (never mocked — fails the skill's gate)

- **Outbound event producers** (no UI effect): list requirement IDs here.
- **Inbound event consumers** (served from local DB; seed the table if a flow needs it, not a
  service mock): list requirement IDs here.
- **Search engine** (runs locally as a real container, not blocked): list requirement IDs here.
- **Pure local / NFR / CSS** (no external service): list requirement IDs here.

## Provenance

Populate this section after an initial pass over all requirements:
> Built from a full pass over all `docs/requirements/requirements/REQ-*.md` files. Re-run the pass
> when requirements change; keep the per-service tables in sync with the requirement pages (cite by
> REQ-ID, never restate the requirement text).
