# Agent Instructions

AI coding agents such as Codex, Claude Code, and similar tools must read this file before making changes in this repository.

How the agent configuration is wired across tools (rules, skills, subagents — what lives where and why) is documented in [`docs/architecture/agent-config.md`](docs/architecture/agent-config.md).

## First run: set up the template before anything else

This repository ships as a **template**. If it still contains `{PLACEHOLDER}` tokens — e.g.
`{PROJECT-NAME}`, `{CLIENT-NAME}` in file contents, or placeholder/example **paths** such as
`Dockerfile.{project-name}-ui`, `csharp/src/backend/Example/Infrastructure/Mock/EXAMPLE-CRM-MOCK/`, or
`docs/requirements/sources/SRC-EXAMPLE-001.md` — it has **not yet been set up** for a concrete
project. Before doing any implementation work:

1. Run the **`setup-repo-structure`** skill (`/setup-repo` in Claude Code / OpenCode). It asks for
   the real values and replaces every placeholder across the repo — both **file contents** and
   **file/folder names**.
2. The complete placeholder reference (every token, where it lives, and which paths must be
   renamed on disk) is [`docs/architecture/project-placeholders.md`](docs/architecture/project-placeholders.md).
3. Verify with `find . -path ./.git -prune -o -name '*{*' -print` and `grep -r "{PROJECT-NAME}" .` —
   both should return nothing once setup is complete.

Do not hand-edit individual placeholders ad hoc; run the skill so contents and filenames stay in sync.

## Project Context

This repository supports the `{PROJECT-NAME}` application. Replace `{PROJECT-NAME}` with your actual project name throughout this file.

The client already started implementing the application under `csharp/`. Work in this repository extends that implementation through tickets and confirmed requirements.

## Implementation Goal

The goal is to extend `{PROJECT-NAME}` while preserving existing confirmed behavior unless a ticket or requirement states otherwise.

TODO: Add measurable implementation success criteria and acceptance tests when available.

## Repository Structure

- `csharp/src/` - production C# source code.
- `csharp/test/` - automated tests for C# code.
- `to_be_migrated_repo/` - frozen, read-only legacy codebase source. A **secondary** reference for behavior parity and requirements, alongside customer documents and tickets. Never edit, build, or refactor it.
- `legacy-sql/` - frozen, read-only client-provided legacy SQL reference. A **secondary** reference for data structures, stored behavior, and requirements discovery. Do not treat it as active migrations or deployable database code.
- `.agents/skills/` - reusable agent skills (`SKILL.md`); read natively by Codex/OpenCode where supported, and exposed to tool-specific discovery through symlinks such as `.claude/skills`, `.codex/skills`, and `.opencode/skills`.
- `.agents/subagents/` - specialized agent definitions and role instructions.
- `docs/architecture/` - architecture notes, decisions, requirements-site architecture, and implementation design.
- `docs/requirements/` - confirmed requirements, source imports, and requirements traceability.
- `reports/test-results/` - generated test results, coverage reports, and CI test output.
- `reports/evaluations/` - implementation analyses, comparison reports, and assessment documents.
- `tools/requirements-site/` - MkDocs tooling for rendering the structured requirements site from `docs/requirements/`.

## Expected Agent Workflow

1. **On a fresh template clone, set up the repo first** (see "First run" above) — replace all
   placeholders via the `setup-repo-structure` skill before implementation work.
2. Read `README.md`, this file, and any relevant documents under `docs/`.
2. Inspect existing code and tests before making changes.
3. Keep changes small, focused, and reviewable.
4. Preserve existing behavior unless a requirement explicitly changes it.
5. Add or update tests for behavior changes.
6. Update documentation when architecture, requirements, or implementation assumptions become clearer.
7. Clearly mark unknowns with `TODO` instead of inventing details.

## OpenSpec Changes and Requirements Traceability

Implementation work is organised as **OpenSpec changes** under `openspec/changes/<name>/`
(proposal, design, specs, tasks; archived to `openspec/changes/archive/` after apply). The
confirmed requirements under `docs/requirements/` are the **durable** record of *what* the
system must do; an OpenSpec change is an **ephemeral** unit of work describing *how* a slice
gets built. Keep the two linked in both directions so a requirement can always be traced to the
work that implemented it, and vice-versa.

1. **Propose** — the change's `proposal.md` carries a `Requirements:` mapping (each capability →
   the `REQ-*` IDs it satisfies). This is the **forward link** (change → requirements). Cite
   requirements by ID, never by restating them. In addition, **every** authored artifact
   (`proposal.md`, `design.md`, `tasks.md`) MUST open with a one-line **`> **Requirements
   (traceability):**`** blockquote at the very top, listing the `REQ-*` IDs the change touches
   (grouped by capability, noting any partial coverage). This keeps "which requirements does this
   work serve" visible the moment anyone opens any artifact — not buried in one section of one
   file.
2. **Apply** — as the work is implemented, the **architect** populates each cited requirement's
   `### Architecture` and `#### Technical Dependencies` sections with the *distilled, durable*
   decisions (not a copy of `design.md`) and adds an `openspec_change: <name>` field to the
   requirement's frontmatter. This is the **backward link** (requirement → change). The
   requirements site renders this field as an **"Implemented by"** row on the requirement page
   (see `tools/requirements-site/overrides/partials/requirement-header.html`), so the link is
   visible in MkDocs. Because the change doc is ephemeral, the requirement must stand on its own
   and merely *cite* the change as provenance — never depend on the change doc still existing in
   active form.
3. **Validate** — `mkdocs build -f tools/requirements-site/mkdocs.yml --strict` must still pass.

The `openspec_change` field is rendered today but not yet *enforced*: a build-time validation
hook that checks both links resolve (the change exists; its proposal cites the requirement back)
is **planned, not yet built** — add it the first time a link rots in practice.

For agent-selected implementation work, use the standard slice workflow in
[`docs/architecture/implementation-slice-workflow.md`](docs/architecture/implementation-slice-workflow.md):
`pick-implementation-slice` claims the slice on `master`, creates the Azure claim ticket and
OpenSpec change, then starts TDD implementation; `mock-implementation-slice` then adds local-only
mocks **only when** a slice needs them to be testable by a human in the frontend (a real backend
dependency is not yet available); `complete-implementation-slice` records validation, updates
MkDocs/Azure/`openspec/track.md`, and opens the PR after manual developer validation.

The `Mock` environment (`ASPNETCORE_ENVIRONMENT=Mock`) is **local-only**, exists solely for human
frontend testing while a real dependency is unavailable, and never changes other environments. A
mock never makes a requirement "done" — the real integration stays an open item.

## Coding Guidelines

- Follow existing project conventions once implementation code exists.
- Prefer simple, explicit code over premature abstraction.
- Do not rewrite unrelated code.
- Do not add implementation code until the project structure and requirements justify it.
- Keep generated files out of source folders; generated output belongs in `reports/`.
- **Scripts:** place reusable scripts next to what they serve — `tools/<purpose>/` or the
  relevant area (e.g. `csharp/azure/scripts/`, `tools/requirements-site/hooks/`) — and review
  them like any code. Do **not** create a catch-all root `scripts/` directory.
- **Throwaway/exploratory scripts** an agent writes while working must not be committed: run
  them, then delete. Promote a script into `tools/`/the relevant area only if it is reusable.

## Testing Expectations

- Place C# tests under `csharp/test/`.
- Add tests for ticket-backed behavior, bug fixes, and any behavior-preserving refactors.
- Prefer tests that verify behavior against confirmed requirements and ticket acceptance criteria.
- When adding or updating requirements-site test cases under `docs/requirements/test_cases/`, also
  append `change_history` entries to every covered requirement and each affected parent feature so
  the rendered requirement/feature changelogs record the test coverage change.
- Put generated test output in `reports/test-results/`.
- Build the requirements site with MkDocs after installing its deps (`pip install -r tools/requirements-site/requirements.txt`), e.g. `mkdocs build -f tools/requirements-site/mkdocs.yml --strict`. The recommended convention is a single repository-local virtualenv at `.venv/` — create it once (`python -m venv .venv`) and use `.venv/bin/mkdocs` (Windows: `.venv/Scripts/mkdocs`); do **not** create a second venv under `tools/requirements-site/`.
- TODO: Define the test framework and required test commands.

## Documentation Rules

- Put architecture material in `docs/architecture/`.
- Put confirmed requirements and source material observations in `docs/requirements/`.
- Put implementation evaluations, comparison reports, and assessment documents in `reports/evaluations/`.
- Keep documentation practical and current.
- Update docs when architecture or requirements become clearer.
- When changing text, scope, metadata, architecture notes, or any other content in a requirement
  page under `docs/requirements/requirements/`, also append `change_history` entries to that
  requirement and its parent feature.
- Use `TODO` markers for unknown project-specific details.

## Constraints for Agents

- Do not invent requirements.
- Never modify anything under `to_be_migrated_repo/` — it is a frozen, read-only legacy reference. CI rejects any PR that touches it (`azure-pipelines-guardrails.yml`).
- Treat imported SQL under `legacy-sql/` as frozen, read-only legacy reference material. Do not edit, refactor, reformat, or execute it as deployment code unless an explicit owner-approved task changes that status.
- Treat reports as generated or derived artifacts unless explicitly documented otherwise.
- Do not treat files in `reports/` as source of truth unless explicitly documented.
- Do not rewrite unrelated code.
- Do not remove existing behavior without explicit approval.
- Prefer small, reviewable changes.
- Do not commit secrets, credentials, or environment-specific configuration.
- Ask for clarification when a change depends on unknown business behavior.
