---
name: complete-implementation-slice
description: Complete a claimed {PROJECT-NAME} implementation slice after automated checks and manual developer validation by verifying OpenSpec traceability, updating MkDocs completion metadata, updating openspec/track.md and Azure DevOps, and creating the pull request. Use after pick-implementation-slice has implemented a slice and the developer has approved manual validation.
---

# Complete Implementation Slice

Use this skill after a claimed implementation slice has passed automated checks and the developer
has manually validated the behavior. This skill closes the coordination loop and opens the PR.

## Required context

Read these before acting:

- `AGENTS.md`
- `docs/architecture/implementation-slice-workflow.md`
- `docs/architecture/implementation-flow.md`
- `docs/architecture/tracking.md`
- `docs/requirements/AGENTS.md`
- `tools/{project}-work/config.yaml`
- `openspec/track.md`
- `openspec/changes/<change-name>/proposal.md`
- `openspec/changes/<change-name>/design.md`
- `openspec/changes/<change-name>/tasks.md`

## Preconditions

- Do not run this until the developer explicitly approves manual validation.
- The current branch must be the implementation branch named in `openspec/track.md`.
- The branch must contain the OpenSpec artifacts and implementation commits.
- The slice must have an active row in `openspec/track.md`.
- `mock-implementation-slice` has already run (or was consciously not needed). Any local-only mocks
  it added do not count as real implementation.
- Never edit `to_be_migrated_repo/` or `legacy-sql/`.

## Verify before completion

Check that:

1. `tasks.md` has no unchecked implementation or validation tasks, unless explicitly deferred.
2. `proposal.md` contains capability -> `REQ-*` forward links.
3. Every affected requirement contains `openspec_change: <change-name>`.
4. Every affected requirement has non-placeholder `### Architecture` and `#### Technical Dependencies`.
5. Test cases exist or were updated for the affected requirements where required.
6. The testing subagent hand-off has completed, or the absence of the testing subagent is recorded
   as a blocker.
7. Manual developer validation is recorded in the change or PR notes.
8. No requirement is marked done solely because a local-only Mock makes it testable; the
   `openspec/track.md` row for a slice backed only by a `Mock` stays `in-progress`/`blocked` (never
   `done`) with the real integration tracked as deferred.

Run or confirm the relevant checks:

- `.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml --strict`
- Backend build/tests when backend changed.
- Frontend lint/typecheck/tests when frontend changed.
- Coverage review for meaningful business logic.

If a required check cannot run, record why and do not mark the slice done unless the developer
explicitly accepts that risk.

## Record validation evidence

Create or update `openspec/changes/<change-name>/validation.md` with:

- Automated command results.
- Testing subagent result or placeholder blocker.
- Manual validation result and approver.
- Requirement-by-requirement evidence.
- Deferred items with rationale.

## Verify the OpenSpec change

After validation evidence is recorded and before changing MkDocs/Azure/track metadata, call the
`openspec-verify-change` skill for `<change-name>`.

Use the OpenSpec change name, feature ID, requirement IDs, changed files, validation evidence, and
any deferred items as input. Verification must pass before the change is archived (next section).

If `openspec-verify-change` is unavailable in the current environment or verification fails, stop
and report that completion is blocked until verification can run.

## Archive the OpenSpec change (before the PR)

Once `openspec-verify-change` passes and the developer has confirmed the slice is done, archive the
change **before opening the PR**, so the archive move is part of the PR diff and merges atomically
with the implementation.

Call the `openspec-archive-change` skill for `<change-name>` to move the completed change from
`openspec/changes/<change-name>/` to `openspec/changes/archive/`. Commit the archive move on the
implementation branch together with the completion metadata (see "Update track file" and
"Completion metadata gate") so it is included in the PR.

Do not archive before verification passes, and do not open the PR with the change still unarchived.
If the PR later needs review changes, update the archived change in place and keep it archived.

## Mark MkDocs completion

Update the selected MkDocs pages:

- Completion is recorded by setting the `openspec/track.md` row's `Status` to `done` (step below)
  — that ledger row is the **single source of truth** for implementation status and owner, and the
  requirement page + product dashboard render "Implemented"/owner from it. Do **not** set
  `status: done` or an owner name in requirement frontmatter (`mkdocs build --strict` rejects it).
  A requirement that is only exercisable via a local-only `Mock` (the real dependency is still
  unavailable) is **not** done — do not mark its ledger row `done`; record the pending real wiring
  as a deferred item in `validation.md` and keep the row `in-progress`/`blocked`.
- Set the feature `csharp_status: done` when the new C# implementation substantially covers the
  slice (its vocabulary is `done | partial | not-started`). Do not let a mock inflate
  `csharp_status`. The feature page no longer carries an implementation `status`/`in-progress` tag.
- Leave requirement frontmatter `status: draft` (governance) and `owner: TBD`. The implementation
  status/owner come from the ledger, not the page.
- **Keep `implementation_work_item`** on the requirement and feature pages — it stays the link to
  the Azure claim ticket (now in the review state, `Done` later) and is rendered as the
  "Implementation ticket". Do not clear it on completion; only `pick`/abandonment overwrites it.
- Append factual `change_history` entries to edited feature and requirement pages.

Do not set feature `implementation_status: verified` unless the team explicitly confirms that
field is now used for the new C# implementation rather than legacy/Phase-1 verification.

After these MkDocs edits, **re-run** `.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml
--strict` and fix any breakage before committing — the completion metadata must keep the strict
site build green.

## Update Azure DevOps

Use `tools/{project}-work/config.yaml` for Azure DevOps configuration. Update the Azure claim ticket via
available MCP tools; if MFA is required, open Azure DevOps in the browser and ask the developer to
complete login.

Record:

- Status set to the configured review state (`azure_devops.review_state`, usually `Review`).
  Do not move the claim ticket to `Done`; that happens only after PR review/merge if the team
  chooses to do it later.
- PR link once created.
- Manual validation result.
- Test summary.
- Deferred items.

## Update track file

Update `openspec/track.md` in two steps, both on the implementation branch:

1. Before any completion push and before creating the PR: set the slice row status to `done`, add
   the validation summary, set the completion date, and set the PR field to a `pending`
   placeholder.
2. After the PR exists: backfill the PR link or identifier in the final metadata commit (see
   "Create PR").

Do not directly push completion metadata to `master`; the PR merge carries it back.

## Completion metadata gate

Before pushing the implementation branch for PR creation, verify that all completion metadata is
already updated and committed on the branch:

- The `openspec/track.md` row records completion (`Status: done`) when real C# implementation
  covers the slice; requirement frontmatter is untouched (`status: draft`, `owner: TBD`) — the
  page renders "Implemented"/owner from the ledger.
- The selected feature page has `csharp_status: done` when the slice substantially covers it.
- The Azure DevOps claim ticket is in the configured review state (`azure_devops.review_state`,
  usually `Review`), not `Done`.
- `openspec/track.md` has status `done`, completion date, validation summary, and PR `pending`.
- The OpenSpec change has been archived (moved to `openspec/changes/archive/`) and that move is
  committed on the branch.

If any of these cannot be updated, stop before pushing/PR creation and report the blocker. Do not
create the PR while the repo ledger, requirement pages, or Azure claim ticket still show the slice
as merely in progress.

## Create PR

Create the PR using the configured repository target. The PR body must include:

- Feature ID.
- Requirement IDs.
- OpenSpec change name/path.
- Azure work item ID/link.
- Automated checks and coverage notes.
- Manual validation approval.
- Deferred items.

Add required Azure DevOps PR reviewers from `tools/{project}-work/config.yaml`
(`azure_devops.pull_request.required_reviewers`):

- Always add every reviewer listed under `always` as a required reviewer.
- If the work item or implementation touches frontend behavior, also add every reviewer listed
  under `frontend` as a required reviewer.

The config file is the single source of truth for reviewer names; do not hard-code reviewers in
this skill.

Treat the slice as frontend-touching when any of these are true:

- Changed files are under `csharp/src/frontend/`.
- Changed tests are under `csharp/src/frontend/`.
- `proposal.md`, `design.md`, or `tasks.md` includes frontend/UI work.
- Any affected requirement's acceptance criteria describe user-visible frontend behavior.

If a required reviewer cannot be resolved in Azure DevOps, stop and report the unresolved reviewer
instead of creating a PR without the required reviewer.

After the PR exists, update Azure and `openspec/track.md` with the PR link, commit that final
metadata update, and push the branch.

## Finish condition

Report:

- PR link or ID.
- Azure work item updated.
- Track row status.
- Checks run.
- Any remaining risks or deferred items.
- Confirmation that the OpenSpec change was archived (via `openspec-archive-change`) and the archive
  move is committed on the branch and included in the PR.
