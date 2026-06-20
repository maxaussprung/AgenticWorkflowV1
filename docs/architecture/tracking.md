# Work tracking: repo ↔ project board

> Replace `{PROJECT-NAME}` and `{CLIENT-NAME}` with your actual project and client names
> throughout this document. Replace `{BOARD-TOOL}` with the team's issue tracker (e.g.
> Azure Boards, Jira, GitHub Issues).

How the requirements in `docs/requirements/` become work items on the board, and how
that link is **enforced**. This is the "workflow to board" reference for the team.

## Principle

**One fact, one owner.** The repo owns *what is true* (the requirement text, acceptance
criteria, dependencies, architecture, ADRs). The project board owns *where we are* (owner,
sprint, state, % done, blockers). They are linked by ID — never by copying content.

```text
REPO (source of truth)                 PROJECT BOARD (status of truth)
docs/requirements/**/*.md      ──link──▶  work items
  text, acceptance, links                 owner, sprint, state, %, blockers
```

The project board cannot natively enforce "every product has an Epic" — board config only
does required fields, state rules, and branch policies. So enforcement lives as a
**repo-driven reconciliation** run by a pipeline (see [Enforcement](#enforcement)).

## Mapping

| Repo page (`type:`) | Board work item | Becomes eligible when |
|---|---|---|
| `product`      | **Epic**        | the product page exists (the catalogue is the plan) |
| `feature`      | **Feature**     | the feature page exists; parented to its product's Epic |
| `requirement`  | **User Story**  | `status: approved` (the governance gate) |
| `test_case`    | *(not synced)*  | tracked in the repo / pipeline test results, not as a board item |
| `decision`     | *(not synced)*  | ADRs are repo-only context, linked from the items they govern |

Hierarchy mirrors the repo: **product Epic → feature Feature → requirement Story**.

## The link

Each work item carries the repo ID so the sync is **idempotent** (find-or-create, never
duplicate):

- **Tag** `repo-id:<ID>` (e.g. `repo-id:PRODUCT-001`) — the lookup key.
- **Tag** `{project}-sync` — marks the item as managed by the reconciler.
- A hyperlink back to the rendered page on the requirements site.

### What the sync writes — and what it never touches

The reconciler writes only: **Title, work-item type, parent link, the two tags, and the
back-link.** It **never** writes `State`, `AssignedTo`, `IterationPath`, or effort — those
are owned by the team on the board. Re-running only repairs a missing item, a missing
parent link, or a stale title.

## Implementation claims

Agent-picked implementation work has a separate coordination layer documented in
[`implementation-slice-workflow.md`](implementation-slice-workflow.md). A claim row in
`openspec/track.md` is committed and pushed to `master` before implementation branches are
created. That row is the repo-side lock for parallel agents.

The claim row and the board claim ticket are coordination metadata only. They do not replace the
repo-to-board sync mapping above, and they do not give the reconciler permission to write delivery
fields such as `AssignedTo`, `State`, `IterationPath`, or effort on synced product/feature/story
items.

During an active claim, agents set transient MkDocs claim metadata (`owner` and
`status: in-progress` on affected requirements, `implementation_owner` /
`implementation_claim` and `status: in-progress` on the feature) so the rendered requirement pages
and source files are easy to inspect. Completion moves real implementation coverage to
`status: done` on the affected requirement pages, uses `csharp_status: done` (or equivalent) for
new feature coverage, and keeps `implementation_status` governed by the feature page contract.

## Enforcement

Two pipeline stages (see [`tools/azure-sync/`](../../tools/azure-sync/) or the equivalent sync
tooling for your board):

1. **Drift check — on every PR.** Runs `sync.py --check`. Fails the PR if an approved
   requirement (or any product/feature) has no work item, wrong parent, or stale title.
   This is the gate that stops the board diverging from approved repo content.
2. **Reconcile — on merge to `master`.** Runs `sync.py --apply`. Creates the missing
   Epics/Features/Stories and fixes links. This is what *creates* work items — nobody
   hand-creates them on the board.

```text
author/approve in repo ──PR──▶ drift check (--check, warn/fail)
                          └─merge─▶ reconcile (--apply, create+link)  ──▶ Board
```

### Prerequisite (one-time, manual)

CI writing work items needs a service identity or PAT in a secret variable with
**Work Items: read & write** permission. Until that is granted, run the reconciler locally
in `--check` mode only. Do a `--dry-run` (alias of `--check`) against the real project
before the first `--apply`.

## Board queries (views)

Saved queries that make the link visible:

- **Unsynced approved requirements** — approved REQ pages with no `repo-id` work item
  (drift; should be empty after a reconcile):
  ```
  SELECT [Id], [Title] FROM workitems
  WHERE [WorkItemType] = 'User Story' AND [Tags] NOT CONTAINS '{project}-sync'
  ```
- **Ready for an agent/dev** — synced Stories in `New`/`Approved` state with no assignee.
- **Release readiness per product** — Stories grouped by their parent Epic (product),
  filtered to the current iteration.

## Out of scope

Test cases and ADRs are not board items. Test outcomes surface via pipeline test results;
ADRs surface as links on the items they govern. See [`requirements-site.md`](requirements-site.md)
for how the repo content itself is rendered.
