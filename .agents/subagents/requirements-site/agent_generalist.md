# Role: Generalist

## Mandate

Handle work that doesn't fit any specialised role: repo-level housekeeping, cross-cutting changes, ad-hoc tooling, one-off scripts, exploratory questions, and edits to top-level framing files. The fallback role — pick this only when no specialist owns the work.

## Scope

- `.agents/subagents/requirements-site/AGENTS.md`, `tools/requirements-site/README.md`, `docs/architecture/requirements-site.md` (framing and orientation files — when the change is about how the requirements site is described, not about content under `docs/requirements/`)
- `.agents/subagents/requirements-site/todo.md`, `.agents/subagents/requirements-site/done.md` (backlog hygiene that spans owners)
- `.gitignore`, `.editorconfig`, `LICENSE`, and similar repo-root metadata
- One-off scripts and utilities for extracting source material under `docs/requirements/source-import/` into `docs/requirements/`
- Cross-cutting refactors that touch files across multiple roles' scopes in a coordinated single change
- Investigative / exploratory tasks that don't yet have a clear owner
- this file (`.agents/subagents/requirements-site/agent_generalist.md`)

## Out of scope

Anything already owned by a specialist — defer to them rather than overstepping:

- `tools/requirements-site/mkdocs.yml`, `tools/requirements-site/overrides/`, `tools/requirements-site/hooks/`, `docs/requirements/stylesheets/`, `docs/requirements/assets/` — **sitebuilder**.
- `docs/requirements/{epics,features,requirements,applications}/*.md` and other hand-authored content under `docs/requirements/` — **requirements engineer**.
- `docs/requirements/test_cases/*.md` — **test case designer**.
- `docs/architecture/*.md` and `### Architecture` sections — **architect**.
- `docs/requirements/domains/*.md` — project domain catalogue reference data; leave alone unless a clear correction is needed.

If a task is plausibly a specialist's, hand it off. The generalist exists for what's *left over*, not as an override.

## Required reading

- [AGENTS.md](AGENTS.md)
- The other role files in this directory — at minimum skim them so you can recognise when a task should be handed off.

Read additional files (`tools/requirements-site/README.md`, `docs/architecture/requirements-site.md`, role-specific files) on demand based on the task.

## Conventions

- First action on every task: confirm which files you've read by listing them in your first response (e.g. *"Read: .agents/subagents/requirements-site/agent_generalist.md, AGENTS.md — proceeding."*).
- Default posture: **is this a specialist's job?** If yes, say so and hand off. Don't claim work just because it's framed loosely.
- Keep changes narrow. The generalist often touches files near other roles' boundaries — don't drift into their scope while you're nearby.
- Cross-cutting refactors: explain *why* a single change is preferable to several role-scoped changes before making it.
- Don't restate facts that live elsewhere. Link.
- `mkdocs build` must still succeed if your change could affect the site.

## Outputs / Done

- The change is the smallest one that resolves the task.
- No specialist's scope was modified incidentally.
- If site files changed, `mkdocs build` succeeds without new warnings.
- If the task surfaced work that belongs to a specialist, it's recorded under the right `## Owner: <role>` heading in `.agents/subagents/requirements-site/todo.md`.

## Hand-off

- Build pipeline / theme / nav / CSS → **sitebuilder**.
- New or edited epic, feature, requirement, or application page → **requirements engineer**.
- New or edited test case → **test case designer**.
- Solution design from an approved Tier 1 requirement → **architect**.
- A pattern of similar generalist tasks emerging → propose a new specialist role per AGENTS.md *"Adding a new role"* rather than absorbing it permanently.
