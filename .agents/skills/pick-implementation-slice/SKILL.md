---
name: pick-implementation-slice
description: >-
  Select and claim the next {PROJECT-NAME} feature or requirement slice for implementation with a hybrid
  workflow: use the bundled selector script for deterministic candidate scoring, then apply LLM
  reasoning over the shortlist before claiming. Update openspec/track.md on master, create the
  Azure DevOps claim ticket with browser/MFA fallback, create the implementation branch, generate
  OpenSpec artifacts, commit them, and begin TDD implementation. Use when a developer or agent asks
  to pick, claim, start, or autonomously implement the next {PROJECT-NAME} slice.
---

# Pick Implementation Slice

Use this skill to start a {PROJECT-NAME} implementation slice in a way that supports parallel agents.
The hard lock is the committed and pushed `openspec/track.md` change on `master`; branch work
starts only after that push succeeds.

## Required context

Read these before acting:

- `AGENTS.md`
- `docs/architecture/implementation-flow.md`
- `docs/architecture/implementation-slice-workflow.md`
- `docs/architecture/tracking.md`
- `docs/requirements/AGENTS.md`
- `docs/requirements/page-types/feature.md`
- `docs/requirements/page-types/requirement.md`
- `tools/{project}-work/config.yaml`
- `openspec/track.md`
- `.agents/skills/pick-implementation-slice/scripts/select_next_slice.py`

## Preconditions

- The workflow ultimately claims on `master`.
- First inspect `git status --porcelain`. If there are any uncommitted changes, including
  untracked files, stop and report them. Do not stash, commit, clean, or overwrite user work.
- If the working tree is clean but the current branch is not `master`, ask the developer whether
  to check out `master` and continue. If they approve, run `git checkout master` and continue the
  workflow automatically. If they decline, stop.
- Once on `master`, run `git pull --ff-only` before selection.
- Never edit `to_be_migrated_repo/` or `legacy-sql/`.

## Selection

Before selecting anything new, check `openspec/track.md` for a row already claimed by the current
owner whose claim is incomplete (Azure work item still `TBD`/`TODO`, branch missing, or OpenSpec
artifacts missing). If one exists, resume that claim from the first incomplete step instead of
selecting a new slice.

Use a hybrid selection model: the script supplies deterministic evidence and ordering; the LLM
reviews that shortlist against requirement semantics, current code shape, and implementation
practicality before claiming. Do not bypass the script or choose from memory. Run:

```bash
.venv/bin/python3 .agents/skills/pick-implementation-slice/scripts/select_next_slice.py --top 25
```

Treat the script's top rows as the candidate queue, not as an automatic final answer. The selector parses
`openspec/track.md`, expands shorthand requirement references such as `REQ-PROD-001, -002`, applies
the active statuses from `tools/{project}-work/config.yaml`, skips active locks, resolves dependencies,
and ranks atomic requirement candidates by this stable score:

1. `priority: must`, then `should`, then `could`; skip `wont`.
2. `tier: 1` before other tiers.
3. Lower implementation risk: narrow product scope, no DB/API/migration burden, fewer external
   integrations, functional before non-functional, fewer acceptance criteria, shorter requirement
   body.
4. Lower independence cost: fewer resolved dependencies, fewer unresolved reverse dependents, no
   active reverse dependents.
5. Existing C# context: `csharp_status: partial`, then leftover requirement gaps in
   `csharp_status: done` features, then `not-started`, then empty.
6. Higher source confidence: `gold`, then `silver`, then `bronze`.
7. Lowest `REQ-*` ID as the final deterministic tie-breaker.

Important: a parent feature's `csharp_status: done` is dependency evidence, not by itself
requirement-level completion evidence. A requirement remains selectable until it has requirement
evidence such as a `done` track row, `status: done`, a `done` tag, or an `openspec_change`. A
requirement or feature with page-level `status: in-progress` is treated as actively claimed and
must not be selected again. This prevents leftover atomic gaps in already-covered features, such as
{PROJECT-NAME} sub-feature handling, from being suppressed only because their broad parent feature is marked done.

To inspect a surprising candidate, run:

```bash
.venv/bin/python3 .agents/skills/pick-implementation-slice/scripts/select_next_slice.py --top 25 --explain REQ-ERF-022
```

Then perform the LLM review:

1. Inspect at least the top five selector rows, plus any user-mentioned candidate.
2. Open each serious candidate's requirement page and parent feature page. Inspect code/tests when
   the page metadata is ambiguous or the selector score looks suspicious.
3. Check semantic fit: the slice must be application-implementable, independently testable, not
   mostly external/network/board/process work, not blocked by an unresolved PO decision, and not
   hiding a large unencoded dependency chain.
4. Prefer the highest-ranked candidate that passes that review. If a lower-ranked candidate is
   chosen, record each skipped higher-ranked candidate and the repo-backed reason it was skipped.
5. Record the selection rationale in the `openspec/track.md` notes: selector rank/score, why the
   slice is independent enough, and any script-ranked candidates skipped by LLM review.

After selecting the requirement, group additional requirements into the same slice only when
they are necessary to satisfy that requirement, their dependencies are already resolved or in the
same small bundle, and the result remains reviewable as one PR. Otherwise keep the slice atomic.

If no eligible slice exists, stop and report that no unclaimed implementation slice was found.

## Claim on master

1. Get the owner from `git config user.name`; if blank, use `git config user.email`; if both are blank, stop.
2. Derive a kebab-case OpenSpec change and branch name from the selected feature title. The branch
   must use the configured prefix from `tools/{project}-work/config.yaml`; the expected prefix is
   `feature/`. Do not create implementation branches under `codex/`.
3. Update `openspec/track.md` with one row for the claim:
   - Feature ID
   - Requirement IDs
   - OpenSpec change name
   - Owner
   - Branch
   - Azure work item placeholder (`TBD` until created)
   - Status `claimed`
   - ISO date
   - Blocker/notes
4. The `openspec/track.md` row from step 3 is the **single source of truth** for the slice's
   implementation status and owner — the site renders both from it (the `cross_refs` hook exposes
   `req_impl_status` / `req_impl_owner`; the requirement header and product dashboard read those).
   Do **not** copy status/owner into requirement or feature frontmatter — that duplication drifts
   and `mkdocs build --strict` now rejects it:
   - **Affected requirement pages**: leave `owner: TBD` and `status: draft` (governance value).
     Do **not** set `owner: <git user>`, `status: in-progress`, or an `in-progress` tag — the
     ledger row already conveys this.
   - **Feature page**: you may set `implementation_owner: <git user>` and
     `implementation_claim: <change-name>` (feature-level claim metadata), but do **not** add an
     `in-progress` status tag and leave `csharp_status` unchanged (its vocabulary is only
     `done | partial | not-started`; `complete-implementation-slice` advances it at completion).
   - Append factual `change_history` entries to every edited page recording the claim (owner,
     OpenSpec change name, branch, ISO date).
5. Run `.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml --strict` and fix any
   breakage the claim edits introduced. Never push a claim that breaks the strict site build.
6. Commit only the claim changes on `master`.
7. Push `master`.

If push fails:

1. Reset only your failed claim commit, without touching unrelated user changes.
2. Pull latest `master`.
3. Re-read `openspec/track.md`.
4. If the slice is now claimed by someone else, go back to selection and pick the next candidate
   rather than re-contending for the same slice.
5. Otherwise retry the claim commit and push.

Do not create or switch to the implementation branch until the claim commit is pushed.

## Azure DevOps claim ticket

Use `tools/{project}-work/config.yaml` for the Azure DevOps URL, project/team labels, and default work
item type. Do not hard-code URLs in the skill.

Create or update an Azure claim ticket using available Azure DevOps MCP tools. If the MCP flow
requires MFA or interactive login, open the configured Azure DevOps URL in the browser and ask the
developer to complete login before continuing.

Before creating or updating the ticket, resolve the Azure assignee:

1. If the Azure DevOps MCP/browser session exposes the signed-in user, use that identity as the
   calling user.
2. Otherwise search Azure DevOps identities using `git config user.email`, then
   `git config user.name`.
3. If no Azure identity resolves and `claims.assign_to_caller` is true, ask the developer for their
   Azure DevOps display name or e-mail before creating the ticket.
4. Do not silently leave the ticket unassigned. If assignment still fails because of board
   permissions or identity lookup, record the blocker in the work item and in `openspec/track.md`.

The work item must include:

- Title: `{PROJECT-NAME} | <feature title>`; keep the feature ID in tags/description, not as an
  "Implement ..." title prefix.
- A **description** in this exact structure:
    1. An opening paragraph: "This claim covers the {PROJECT-NAME} <feature title> feature for the C#
       application. The implementation should ..." — summarize in business language what the
       slice adds and why, written from the feature and affected requirement pages.
    2. An **Implementation scope** block listing one item per line:
       Feature (`FEAT-*` + title), Requirement(s) (`REQ-*`), OpenSpec change path
       (`openspec/changes/<change-name>/`), Owner, Branch, and
       "Repo lock and progress ledger: openspec/track.md".
    3. Closing boundary sentences naming what stays outside the slice (external system
       ownership, excluded flows), e.g. "{EXTERNAL-SYSTEM}-side processing remains owned by
       {EXTERNAL-SYSTEM}. The manual ID data entry path remains outside this slice."
    4. A **Database impact** section whenever any affected requirement carries DB necessities
       (its `### Database Implementation` section, or DB reads the slice depends on): list each
       action as `Create tables ...` / `Extend ...` / `Use existing ...` / `Reads ...` with the
       target tables and the key fields, mirroring the requirement's summary table. If no
       requirement has DB impact, state "No database changes."
- **Acceptance criteria** in Given/When/Then form, one criterion per line, derived from the
  affected requirement pages. Preserve concrete business values, field names, and messages.
  Example shape:
  "Given the {PROJECT-NAME} application starts at a terminal, when initialization completes, then the
  {EXTERNAL-SYSTEM} connection state is determined as connected or not connected and reflected in the
  session information panel."
  When a requirement has DB necessities, include its database acceptance criteria as
  Given/When/Then items too (migration applied, data persisted and read back end-to-end,
  constraints enforced), e.g. "Given the migration has run, when a CSV row is imported
  successfully, then the corresponding record with the created FK is persisted and can be
  read back."
- Tags: `{project}-claim`, `{project}-claim:<FEAT-ID>`, `openspec:<change-name>`
- Feature ID and requirement IDs
- Owner
- Assigned To set to the resolved calling user.
- Branch
- OpenSpec change path
- Link or note pointing back to `openspec/track.md`
- State set to the configured active state from `claims.active_work_item_state` (`Approved`).
  Do not leave the claim ticket in a new or backlog-only state once work starts.

After the work item exists, update the claim row in `openspec/track.md` with the Azure work item
ID, **and link the work item on the MkDocs pages**: set `implementation_work_item: <id>` in the
frontmatter of every affected requirement page and the feature page (the headers render it as a
linked "Implementation ticket"), and append a `change_history` entry to each. Do **not** add the
claim ticket to `azure_story_ids` — that field is source provenance and bumps `source_tier` to
gold. Run `.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml --strict` and fix any
breakage. Commit and push that small `track.md` + page update on `master` before branching. If the
Azure ticket cannot be created after MFA/login, leave the claim pushed, set the Azure field to
`TODO`, leave `implementation_work_item` empty, and record the blocker in the track row.

## Branch and OpenSpec

1. Create and check out the branch from current `master`, using the configured prefix. The branch
   name must start with `feature/`; stop and fix the config if it would start with `codex/`.
2. Push the branch with upstream tracking as soon as it exists when Azure DevOps needs a remote ref
   to create the branch link.
3. Link the Azure claim ticket to the implementation branch (`refs/heads/<branch>` or the
   equivalent Azure branch relation) and confirm the work item is in the configured active state.
   If branch linking is blocked by MFA/tooling, record the blocker in the ticket and track row.
4. Build an OpenSpec context bundle from the exact selected feature and requirement files before
   calling `openspec-propose`. Include the change name, feature/requirement IDs and titles, and
   the relevant frontmatter (`status`, `priority`, `tier`, `source_tier`, `depends_on`, `tags`, `source`,
   `cf_source`, `sql_source`, `azure_story_ids`, `screens`, `source_conflict_note`,
   `csharp_status`). Include the body sections that affect implementation: User Story, Formal
   Requirement, Acceptance Criteria, Exclusions, GUI/API/Database Description, Data Migration
   Considerations, Coexistence Scenarios, Source Atlas / Evidence blocks, Additional Context
   (Azure Wiki), Database Implementation, Architecture, and Technical Dependencies. Database
   Implementation and Azure Wiki context are mandatory when present; do not summarize them away in
   a way that loses table names, field names, event/topic names, validation values, or database
   acceptance criteria. If the pages are long, pass concise excerpts with file paths and headings,
   but preserve all concrete DB/wiki/source facts needed for design and tasks.
5. Generate the OpenSpec change under `openspec/changes/<change-name>/` by calling the
   `openspec-propose` skill with the change name and the context bundle above. Do not hand-author
   the artifact structure when the skill and `openspec` CLI are available.
6. The OpenSpec artifacts must include:
   - `proposal.md` with capability -> `REQ-*` forward links.
   - `design.md` with durable decisions and open questions, including persistence decisions drawn
     from `### Database Implementation`, `### Database Description`, and `sql_source` when present.
     Treat legacy SQL and Azure Wiki content as supporting context: it informs implementation but
     does not override the confirmed requirement text and is not deployable code by itself.
   - `tasks.md` with implementation and validation tasks, including migration, persistence,
     integration, and database acceptance-criteria tasks whenever the selected requirements carry
     DB necessities.
   - Delta specs when the OpenSpec workflow requires them.
7. Commit the OpenSpec artifacts before code changes.

If `openspec-propose` or the `openspec` CLI is unavailable, create the same artifact structure
manually and note that the skill/CLI was unavailable in the commit/summary.

## Implement with TDD

After OpenSpec is committed:

1. Start from acceptance criteria and use the `generate-tdd-tests` skill to write failing tests
   first where practical.
2. Implement the smallest code change that satisfies the tests.
3. Refactor only after tests pass.
4. Keep `tasks.md` current.
5. Add `openspec_change: <change-name>` to affected requirements.
6. Fill each affected requirement's `### Architecture` and `#### Technical Dependencies` sections.
7. Add or update test cases under `docs/requirements/test_cases/` when required.
8. If you are now implementing the real version of a dependency that an earlier slice mocked under
   the `Mock` environment (a `Mock<Service>` adapter or a Mock seed for this requirement), delete
   that mock together with its `IsMock()` registration and seed as part of this change — the real
   implementation supersedes it. A stale mock would mask the real wiring in `Mock` mode and rot.
   See `mock-implementation-slice` for where mocks live.

## Local mock for testing (run mock-implementation-slice)

After implementation and before the testing hand-off, run the `mock-implementation-slice` skill. It
decides, per requirement, whether the slice needs a local-only Mock to be testable by a human
clicking through the frontend (a real backend dependency is missing) and adds a mock adapter and/or
local-DB seed **only when needed** — most slices need none. Do not embed mock logic in this skill.
Mocked requirements stay `status: in-progress`/blocked; a mock never marks a requirement done.

## Testing hand-off placeholder

When implementation is ready for independent validation, call the testing subagent.

Placeholder until the testing-agent branch lands:

```text
TODO_TESTING_SUBAGENT_NAME
```

Pass it:

- OpenSpec change name
- Feature ID
- Requirement IDs
- Changed files
- Commands already run
- Coverage target: aim for 100% meaningful business logic coverage; ignore getters, setters,
  DTO boilerplate, generated code, and trivial mappings unless they encode business rules.

If the testing subagent is not available in the current environment, stop and report that the
testing hand-off is pending rather than pretending independent validation occurred.

## Finish condition

Do not create a PR from this skill. After implementation, run `mock-implementation-slice` (adds
local test mocks only if needed), then complete the testing hand-off, then ask the developer for
manual validation. After the developer approves, use `complete-implementation-slice`.
