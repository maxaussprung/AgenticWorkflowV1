# AGENTS.md

Multi-agent project. Pick a role, read **only** that role's required files, then do the task.

## Project context

MkDocs (Material) site used as the requirements management framework for the **`{PROJECT-NAME}`** project. Pages are typed via YAML frontmatter; the theme renders one card per type.

- [tools/requirements-site/README.md](../../../tools/requirements-site/README.md) — humans + authoring guide (page types, badges, quick start)
- [docs/architecture/requirements-site.md](../../../docs/architecture/requirements-site.md) — build pipeline (cross-refs hook, theme overrides, mkdocs config)
- [docs/requirements/index.md](../../../docs/requirements/index.md) — business framing (Tier 1 / Tier 2 / governance)
- [docs/requirements/source-import/](../../../docs/requirements/source-import/) — source material (Excel workbook, PDFs, deck) being extracted page-by-page into `docs/requirements/`

The framework was adapted from an earlier program. The **application catalogue** (`docs/requirements/applications/`) and **domain catalogue** (`docs/requirements/domains/`) describe the project's domain model.

## Roles

| Role | File | Owns |
|---|---|---|
| Sitebuilder | [agent_sitebuilder.md](agent_sitebuilder.md) | `tools/requirements-site/mkdocs.yml`, `tools/requirements-site/overrides/`, `tools/requirements-site/hooks/`, `docs/requirements/stylesheets/` |
| Requirements engineer | [agent_requirements_engineer.md](agent_requirements_engineer.md) | hand-authored content under `docs/requirements/` (epics, features, requirements, applications, framing) |
| Architect | [agent_architect.md](agent_architect.md) | `docs/architecture/` — solution designs derived from approved Tier 1 requirements; the `### Architecture` section inside each requirement page |
| Test case designer | [agent_test_case_designer.md](agent_test_case_designer.md) | `docs/requirements/test_cases/` — UAT and integration test cases that verify requirements |
| Frontend test author | [agent_test_author_frontend.md](agent_test_author_frontend.md) | `csharp/src/frontend/**/__tests__/` — Jest/RTL unit + component tests; `reports/test-coverage/frontend/` — per-requirement frontend coverage data |
| Backend test author | [agent_test_author_backend.md](agent_test_author_backend.md) | `csharp/test/backend/**/*Tests/` — xUnit unit + backend integration tests; `reports/test-coverage/backend/` — per-requirement backend coverage data |
| Migration requirements | [agent_migration_requirements.md](agent_migration_requirements.md) | `docs/requirements/migration-consolidated/` — source-backed diagnostic migration requirements; does not promote canonical requirements or implement code |
| Generalist | [agent_generalist.md](agent_generalist.md) | Fallback for tasks no specialist owns — top-level framing files, cross-cutting work, ad-hoc tooling |

## Shared rules

- `mkdocs build` must succeed after any change that affects the rendered site.
- One source of truth per fact: link, don't restate.
- Stay inside your role's scope. If a task crosses roles, hand off explicitly (see each role file).
- Don't load files outside your role's *Required reading* unless the task demands it.
- **Record every meaningful change in a page's `change_history`** — see [Change history convention](#change-history-convention).
- **Requirement content changes propagate to feature changelogs.** When text, scope, metadata,
  architecture notes, or any other content changes in `docs/requirements/requirements/*.md`, append
  `change_history` entries to both the changed requirement and its parent feature page.
- **Test-case changes propagate to requirement and feature changelogs.** When a test case under
  `docs/requirements/test_cases/` is added, removed, or substantively updated, append a matching
  `change_history` entry to every requirement listed in that test case's `requirements:` field and
  to each affected requirement's parent feature. If several changed test cases touch the same
  requirement or feature in one session, one concise entry per touched page is enough.
- Source material under `docs/requirements/source-import/` is **read-only** — never modify the original Excel / PDF / PPTX files. Extract into `docs/requirements/` markdown; if the source itself is wrong, flag it for the user.
- **Canonical specification document citations.** When a feature/requirement cites a specification document (`{SPEC-DOCUMENT}`), the `source:` entry must reference a real section from the project's section index. The coverage matrix keys off this id; free-text sections are not counted.
- **Frontmatter must be valid YAML.** A page whose front matter fails to parse is silently dropped from the cross-reference registry and the coverage matrix (even if `mkdocs --strict` passes). Quote a `title:` containing `: ` and avoid unescaped `"` inside a double-quoted `section:`.

## Change history convention

Every content page (epic, feature, requirement, test_case, application, domain, design — anything *except* auto-generated `index.md` pages) carries a `change_history` field at the bottom of its YAML frontmatter. Each entry is a single string with a bold ISO date, a colon, and a one-sentence factual description of what changed and why. The list is **chronological with the newest entry at the bottom**.

```yaml
---
type: requirement
id: REQ-ADDR-001
title: Fuzzy address search returns close matches
feature: FEAT-006
applications: [APP-001]
owner: {team-owner}
status: draft
priority: must
tier: 1
kind: functional
change_history:
  - "**YYYY-MM-DD**: Initial extraction from {SPEC-DOCUMENT} §<section> — <title>."
---
```

**Rules**

- One entry per logical change. If you do several edits in one session that share a single rationale, a single entry is fine; if they're independent, write one each.
- For requirement content edits, the requirement and its parent feature both need a
  `change_history` entry. The feature entry should summarize that one or more linked requirements
  changed; do not duplicate the full requirement detail there.
- For test-case edits, the test case itself, each referenced requirement, and each affected parent
  feature all need a `change_history` entry. The requirement/feature entry should say that test
  coverage was added, removed, or updated; do not change requirement or feature content unless the
  task explicitly asks for it.
- Date format `YYYY-MM-DD`, wrapped in `**…**` so it renders bold once a partial picks it up.
- Past tense, factual. Mention the *why* — the entry is read by the next agent or human, not by you.
- Skip auto-generated `index.md` pages.
- Do **not** delete or rewrite older entries, even if the change was later reverted; add a new entry describing the revert.

**Rendering**

`change_history` is rendered on the page automatically. Each type-header partial (`tools/requirements-site/overrides/partials/<type>-header.html`) includes `partials/change-history.html`, which emits a "Change history" section listing every entry verbatim — entries are rendered as inline markdown so the leading `**date**` shows up bold. Adding the field to the YAML is enough; no extra wiring is needed.

## Backlog

Open work lives in [todo.md](todo.md), grouped by `## Owner: <role>` headings. Closed work is archived in [done.md](done.md) under the same headings. Approach a todo only when explicitly instructed. Closed: `[x]`. Open: `[ ]`.

### Backlog hygiene

Every agent maintains the backlog as part of its work — these rules apply regardless of role:

- **Log unlisted work.** If you do something the user asked for in chat that wasn't on the list, add it to `todo.md` (or directly to `done.md` if you've already finished) under the right `## Owner:` heading. Keep it short — the task line plus a one-line sub-bullet of what you did. The point is "this happened", not a detailed history.
- **Note what you did when you close a task.** When ticking `[ ]` → `[x]`, append an indented sub-bullet under the task summarising what was done and, if non-obvious, why. One or two sentences. Don't duplicate detail that already lives in `change_history` — link or reference it instead.
- **Keep at most 5 closed items per section in `todo.md`.** After you tick a task off, leave it in place. Then look at its section (`## Owner:` or `###` subsection): if there are now more than 5 closed `[x]` entries, move the oldest ones — from the top — to [done.md](done.md) under the matching heading, appended at the bottom (oldest above, newest below). Both files share the same structure; only `todo.md` is capped, `done.md` accumulates history.

## Platform adapters

The canonical role specs live in this directory as `agent_<role>.md`. Each platform adapter points to the canonical file:

- **Claude Code**: `.claude/agents/<role>.md` — invoked automatically when the description matches the task, or explicitly with `/agents`.
- **GitHub Copilot**: `copilot/prompts/<role>.prompt.md` — invoked in Copilot Chat with `/<role>`. Repo-wide instructions live at `copilot/copilot-instructions.md` and point back here.

When updating a role, edit `agent_<role>.md`. The adapters are short stubs and rarely change.

## Adding a new role

1. Create `agent_<role>.md` using the template below.
2. Add a row to the **Roles** table above.
3. Add an `## Owner: <role>` section to `todo.md` if there is work for it.
4. Add the platform adapters at `.claude/agents/<role>.md` and, when exposing the role to Copilot, `copilot/prompts/<role>.prompt.md` (copy a sibling, change the name and description).

### Role file template

Each role file uses these sections, in this order:

- `# Role: <Name>` — title
- `## Mandate` — one or two sentences; what this role exists to do
- `## Scope` — files and directories this role owns (explicit globs)
- `## Out of scope` — what to leave alone (explicit)
- `## Required reading` — the minimum files this role needs
- `## Conventions` — role-specific rules
- `## Outputs / Done` — what "done" looks like for this role's work products
- `## Hand-off` — when to defer to another role
