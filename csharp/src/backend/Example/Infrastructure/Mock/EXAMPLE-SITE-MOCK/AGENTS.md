# Mock catalog — EXAMPLE-SITE-MOCK (example: {ExternalServiceA} — address / location service, HTTP/WireMock mock)

> Catalog entry for agents running `mock-implementation-slice`. If a requirement in your slice is
> listed below, its address-service mock belongs **in this folder**. This file is a MAP — implement
> the mock here only when your slice owns one of these requirements. See the top-level
> [`Mock/AGENTS.md`](../AGENTS.md) for the full picture.

## The external service

- **What it is:** {ExternalServiceA} — {description, e.g. domestic address search & validation},
  {domain-field} resolution, fuzzy matching, incremental address guidance, and any project-specific
  classification flags (e.g. delivery-area type, zone flag).
- **Real seam in repo:**
  - Port: `{ClientName}.{ProjectName}.Application/Abstractions/Services/I{ServiceA}.cs`
  - Adapter: `{ClientName}.{ProjectName}.Infrastructure/Services/{ServiceA}Adapter.cs` (HTTP client
    to `{ServiceA}:ApiUrl`, e.g. `api/{project-name}/search`, `GET /api/addresses/{id}`)
  - DTO: `{ClientName}.{ProjectName}.Contracts/{Domain}/Responses/{ServiceA}Response.cs`
- **Mock mechanism (in order of preference):**
  1. **WireMock stub** — the adapter is an HTTP client, so prefer a declarative stub. Check whether
     the repo ships a reference stub mapping file under
     `csharp/src/frontend/tests/wiremockSetup/mappings/`. NB: `docker-compose.mock.yml` may drop the
     adapter/wiremock wiring for offline boot — when you mock via WireMock you must re-add the
     adapter's `wiremock` base URL + the `wiremock` service to the Mock run (see skill).
  2. **C# `Mock{ServiceA}`** implementing `I{ServiceA}` (DI swap, registered only under `IsMock()`).
- **Why blocked locally:** under `ASPNETCORE_ENVIRONMENT=Mock` the real adapter points at a
  placeholder URL, so any {domain-field} lookup call fails — this is the genuine local blocker.
- **Status:** **mockable now** (port + DTO exist) — except any classification-flag branches that
  require new DTO fields (see caveats).

## Requirements that need this mock

| REQ-ID | What to mock (input → response) | UI branch(es) unblocked | Caveat |
|---|---|---|---|
| {REQ-ID} | search → exactly one canonical result above threshold | silent-accept: entered text replaced by canonical form | — |
| {REQ-ID} | search → multiple ranked candidates | pick-list of N; selection commits canonical form | — |
| {REQ-ID} | search → zero matches | no-match message + explicit free-text confirm + unvalidated flag | — |
| {REQ-ID} | `GET /api/{entities}/{id}` → full record + a no-result case | ID resolution pre-fills fields; graceful no-resolution | — |
| {REQ-ID} | fallback lookup → candidate (+ unavailable/error) | candidate offered accept/reject after no-match; graceful failure | — |
| {REQ-ID} | autocomplete suggestions for ≥N chars (+ none) | dropdown suggestions; selection fills fields; no-match fallback | — |
| {REQ-ID} | {domain-field} → {domain-field} resolution | {domain-field} auto-resolves related {domain-field} | — |
| {REQ-ID} | record with {classification-flag} (flagged vs non-flagged) | feature rejects flagged address / accepts non-flagged | **needs `{classification-flag}`** (see caveats) |
| {REQ-ID} | incremental {domain-field}/{domain-field} result lists | step-by-step incremental dropdowns | — |

> Replace placeholder rows above with the actual requirement IDs and descriptions for this project.

## How to implement (when your slice needs it)

1. Pick the mechanism above (WireMock stub preferred; C# `Mock{ServiceA}` if no HTTP seam fits).
2. Return faithful, seeded values covering **every UI branch** the requirement specifies (match,
   multi-candidate, no-match, error). If the frontend filters client-side, still return the
   would-be-filtered rows. Match the endpoint's empty-result contract (`204` vs `200 []`).
3. Register only under `IsMock()`; never change the real path.
4. Record per-requirement decisions in your change's `tasks.md`; keep the real {ExternalServiceA}
   wiring as a deferred blocker. A mock never marks the requirement done.

## Known caveats / contract gaps

- **Classification flag:** if a requirement depends on a classification flag (e.g. delivery-zone
  type, area flag), verify whether the delivered response DTO carries that field. If not, add a
  provisional `{classification-flag}` field (defaulting `false`/`null` on the real path,
  `// PROVISIONAL (mock only)`) until the real service exposes it.
- Document any additional contract gaps or out-of-scope sub-requirements specific to this project
  here.
