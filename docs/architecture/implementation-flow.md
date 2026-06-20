# Implementation flow (for humans)

> Replace `{PROJECT-NAME}` and `{CLIENT-NAME}` with your actual project and client names
> throughout this document.

How a piece of work goes from "we want to build this" to "it's on the board and verified".

**Three places, one rule:** the **repo** (`docs/requirements/`) owns *what is true*, the
**site** (mkdocs) is the *read-only view*, the **board** (e.g. Azure Boards) owns *where we are*.
You author in the repo; the board updates itself. See [`tracking.md`](tracking.md) for the
sync mechanics and [`requirements-site.md`](requirements-site.md) for the site.

## Worked example: implementing a product capability

The example below shows a generic product capability (`{PRODUCT-NAME}`) — replace with your
project's actual product and feature names.

| # | Step | Where | Who |
|---|---|---|---|
| 1 | **Add the product page** — `products/PRODUCT-0NN.md` (`type: product`, `Priority`, `tags`, `source`). This is the top-level item; it becomes an **Epic** on the board. | repo | requirements engineer |
| 2 | **Break it into features** — `features/FEAT-0NN.md`, each with `Product: PRODUCT-0NN` (entry mask, search, audit, print, …). | repo | requirements engineer |
| 3 | **Write requirements** — `requirements/REQ-{PRODUCT}-00N.md` under each feature: `status: draft`, `tier: 1`, a "*system shall…*" statement, Given/When/Then acceptance criteria, and a `source:` back-link. | repo | requirements engineer |
| 4 | **Preview** — `mkdocs serve`; the product → features → requirements tree and the source traceability matrix render automatically. | site | anyone |
| 5 | **Architecture & decisions** — fill each requirement's **Architecture** section; for a cross-cutting choice spanning the product, add an ADR (`decisions/DEC-00N.md`) and reference it with `decisions: [DEC-00N]`. | repo | architect |
| 6 | **Test cases** — `test_cases/TC-{PRODUCT}-00N.md` naming the requirement(s) it verifies. | repo | test-case designer |
| 7 | **Promote (the gate)** — in PR review, flip the agreed Tier-1 requirements `status: draft → approved`. **This is the only gate**; nothing reaches the board until it's `approved`. | repo (PR) | team / reviewer |
| 8 | **Board appears — automatically** — on merge to `master`, the reconcile pipeline creates the **Epic** (PRODUCT-0NN), its **Features**, and a **User Story** per approved requirement, parented and linked back to the page. Nobody hand-creates them. | board | pipeline |
| 9 | **Implement & verify** — write the application code under `csharp/` (or equivalent), open a PR linked to the work item, CI runs the tests; mark the test case / `implementation_status` **verified** once UAT passes. | code + board | developer |
| 10 | **Show progress** — stakeholders see the filtered site (Tier-1 approved + test status) and the board delivery dashboard. | site + board | — |

## Agent-selected implementation slices

When an agent or developer asks the repository to pick the next implementation slice, use
[`implementation-slice-workflow.md`](implementation-slice-workflow.md). The workflow is driven by
three skills:

- `pick-implementation-slice` — must start on `master`; selects the next feature/requirement
  slice, writes and pushes the claim to `openspec/track.md`, creates the project claim ticket,
  then creates the implementation branch and OpenSpec change before coding.
- `mock-implementation-slice` — runs after implementation and before the testing hand-off; decides
  per requirement whether a local-only mock is needed for human frontend testing (a real dependency
  is not yet available) and adds a mock adapter and/or local-DB seed **only when** needed. Mocks
  live only in the `Mock` environment and never mark a requirement done.
- `complete-implementation-slice` — runs after automated checks and manual developer validation;
  records validation evidence, moves implemented requirement/feature pages from
  `status: in-progress` to `status: done`, marks the feature coverage done in MkDocs, updates
  the board and `openspec/track.md`, and opens the PR.

The claim row in `openspec/track.md` is a coordination lock, not a replacement for approved
requirements or board delivery state. The requirement/feature page `status: in-progress` and
`status: done` values are repo-visible implementation-slice markers, while the project board
remains the delivery state owner. The claim is committed and pushed before branch work starts so
parallel agents can see it.

## The shortcut to remember

```text
author in repo  →  approve (status: draft → approved)  →  merge  →  board updates itself
```

If it's not in the repo, it isn't real. If it's not `approved`, it isn't on the board yet.
Board delivery state, owners, sprints, and progress live on the project board; the repo only
records implementation-slice markers such as `status: in-progress` and `status: done` through the
slice workflow.
