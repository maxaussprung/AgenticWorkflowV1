# Mock catalog — EXAMPLE-DATABASE-MOCK (example: {ExternalServiceC} — reference-data service, DB-seed mock)

> Catalog entry for agents running `mock-implementation-slice`. If a requirement in your slice is
> listed below, its reference-data mock belongs **in this folder**. This file is a MAP — implement
> the mock here only when your slice owns one of these requirements. See the top-level
> [`Mock/AGENTS.md`](../AGENTS.md).

## The external service

- **What it is:** {ExternalServiceC} — {domain-entity} master data — the list of {domain-entities}
  used for drop-downs, {domain-entity} resolution by {domain-field}, and {domain-entity} lists
  (e.g. branch locations, pickup points, reference sites).
- **Real seam in repo:**
  - Port: `{ClientName}.{ProjectName}.Application/Abstractions/Repositories/I{ServiceC}Repository.cs`
  - Backing store: local `{Entity}` EF table, populated **only** by an inbound event consumer
    (`{ClientName}.{ProjectName}.ConsumersWorker` → `{Entity}MessageMiddleware`).
- **Mock mechanism:** **DB seed under `IsMock()`** (skill mechanism #3). This is *not* an HTTP
  adapter — under `Mock` the event consumer is a no-op, so the `{Entity}` table is **empty**;
  seed plausible {domain-entity} rows (prefer extending the existing offline DB initializer; else
  an idempotent `*.sql` under `Mock/EXAMPLE-DATABASE-MOCK/Sql/` run on startup under `IsMock()`).
- **Why blocked locally:** the {domain-entity} list arrives via an event stream (e.g. Kafka), which
  is disabled in `Mock`, so the table is empty and every {domain-entity}-backed drop-down/picker
  is unusable without a seed.
- **Status:** **mockable now** via DB seed (the repository + table exist).

## Requirements that need this mock

| REQ-ID | What to mock (seed → behavior) | UI branch(es) unblocked | Caveat |
|---|---|---|---|
| {REQ-ID} | active {domain-entities}, some flagged with {domain-attribute} | {domain-entity} drop-down populated vs empty-list message | may need a provisional flag if not on the row yet |
| {REQ-ID} | {domain-entities} keyed by {domain-field} | {domain-entity} picker populated after {domain-field} entry | — |
| {REQ-ID} | 0 / 1 / many {domain-entities} per {domain-field} | auto-select single / multi-picker / "no result" error | — |
| {REQ-ID} | {domain-entity} directory by {domain-field} | "no valid {domain-entity}" rejection + {domain-entity} display | — |
| {REQ-ID} | {domain-entity} list with {domain-field}/{domain-field} | loading notice → populated/sorted dropdown → selection display | verify the real source seam before seeding |

> Replace placeholder rows above with the actual requirement IDs and descriptions for this project.

## How to implement (when your slice needs it)

1. Seed `{Entity}` rows under `IsMock()` covering every {domain-entity} the requirement's UI
   branches need (0 / 1 / many results per {domain-field} so empty, single-auto-select, and
   multi-pick paths are all reachable).
2. Prefer extending the existing offline DB data initializer; only add an idempotent `*.sql` if no
   seed mechanism exists. Make it idempotent so repeated boots are safe.
3. Record per-requirement decisions in `tasks.md`; keep the real event-driven master-data feed as
   the deferred source. A mock/seed never marks the requirement done.

## Known caveats / related needs

- The {domain-entity} row may lack certain **attribute flags** needed by specific requirements —
  add these as provisional fields until the real event feed carries them.
- If there are related location/reference master-data needs (e.g. postbox or provider-location data)
  whose exact backing seam is unconfirmed (local table vs. address/provider service), verify the
  seam before mocking; if it is a local table, the same DB-seed mechanism applies — otherwise a
  contract is needed first. Track these in the top-level index.
- Document any additional project-specific caveats here.
