# Mock catalog — EXAMPLE-CRM-MOCK (example: {ExternalServiceB} — customer & identity / CRM service)

> Catalog entry for agents running `mock-implementation-slice`. If a requirement in your slice is
> listed below, its customer/identity mock belongs **in this folder**. This file is a MAP — implement
> the mock here only when your slice owns one of these requirements. See the top-level
> [`Mock/AGENTS.md`](../AGENTS.md).

## The external service

- **What it is:** {ExternalServiceB} — customer master + identity service — {domain-entity} search,
  SSO customer number, online-customer **{business-threshold}** (e.g. a level or tier value), and
  {customer-classification} (e.g. PRIVATE vs. business).
- **Real seam in repo:**
  - Port: `{ClientName}.{ProjectName}.Application/Abstractions/Services/I{ServiceB}.cs`
  - Adapter: `{ClientName}.{ProjectName}.Infrastructure/Services/{ServiceB}Adapter.cs` — currently
    a **static in-memory stub** (returns canned responses), not a real integration.
  - DTO: `{ServiceB}Response` (Contracts/{Domain}/…) — carries `SSO{identifier}`; **`{business-threshold}`
    and a `{customer-classification}` field may not be present yet.**
- **Mock mechanism:** C# `Mock{ServiceB}` (DI swap) — the adapter is an in-process call, not HTTP,
  so there is no base URL to point at WireMock. Extend the seeded {domain-entity} data to drive the
  branches.
- **Why blocked locally:** the real {ExternalServiceB} is unreachable; the adapter is only a stub,
  so candidate lists / {business-threshold} / {customer-classification} needed by the UI branches
  are not produced without seeding.
- **Status:** **mockable now** (port + DTO + stub seam exist) — but `{business-threshold}` /
  `{customer-classification}` fields must be added to drive the gate branches (see caveats).

## Requirements that need this mock

| REQ-ID | What to mock (input → response) | UI branch(es) unblocked | Caveat |
|---|---|---|---|
| {REQ-ID} | {domain-entity} lookup by identifier (match / no-match) | validation error on unknown ID | — |
| {REQ-ID} | {domain-entity} search → no-match / 1–N candidates incl. {business-threshold} | result widget + confirm/link | needs `{business-threshold}` on response DTO |
| {REQ-ID} | {customer-classification} lookup | classified type admitted / rejected / lookup-failure error | needs a classification/type value |
| {REQ-ID} | name search → {business-threshold} candidates (and below-threshold, and none) | candidate list; "no match" msg; "below threshold" msg; select → proceed | needs `{business-threshold}` on response DTO |
| {REQ-ID} | contact/customer search → name, level, addresses | search-bar results + select-to-session | — |

> Replace placeholder rows above with the actual requirement IDs and descriptions for this project.

## How to implement (when your slice needs it)

1. Add / extend a `Mock*` adapter implementing `I{ServiceB}`, registered only under `IsMock()`.
2. Seed {domain-entity} records that cover every branch: match / no-match / multiple candidates /
   below-threshold / lookup-failure. Return the would-be-filtered rows even if the frontend filters
   client-side (e.g. keep `{business-threshold} !== <threshold>` rows so the "below threshold"
   message is reachable).
3. Any new field on the response DTO (e.g. `{business-threshold}`, `{customer-classification}`)
   added to enable a mock must default to a no-op value on the real path and carry a
   `// PROVISIONAL (mock only)` comment.
4. Record per-requirement decisions in `tasks.md`; keep real {ExternalServiceB} wiring deferred. A
   mock never marks the requirement done.

## Known caveats / contract gaps

- The response DTO may lack **`{business-threshold}`** and **`{customer-classification}`** fields.
  These are provisional additions until the real {ExternalServiceB} contract delivers them.
- The adapter may be a static stub returning no real candidates — the actual lookup may be
  integration-blocked and stay in-review/blocked regardless of the mock.
- Document any additional contract gaps specific to this project here.
