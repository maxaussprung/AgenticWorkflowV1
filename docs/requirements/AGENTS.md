# docs/requirements/ Agent Instructions

Applies to `docs/requirements/` — the typed Markdown content (applications, domains, epics,
features, requirements, test cases, sources) that the MkDocs site renders.

**This area is governed by role files**, not by inline rules. Pick a role and read its spec:

- [`requirements-engineer`](../../.agents/subagents/requirements-site/agent_requirements_engineer.md) — products, features, requirements, applications, framing
- [`test_case_designer`](../../.agents/subagents/requirements-site/agent_test_case_designer.md) — UAT / integration test cases under `test_cases/`
- [`architect`](../../.agents/subagents/requirements-site/agent_architect.md) — the `### Architecture` section inside requirement pages, and cross-cutting ADRs under `decisions/`
- [`generalist`](../../.agents/subagents/requirements-site/agent_generalist.md) — fallback for cross-cutting / framing files

Shared rules (change_history, source-import freeze, backlog hygiene, role table) live in
[`../../.agents/subagents/requirements-site/AGENTS.md`](../../.agents/subagents/requirements-site/AGENTS.md) — read it before authoring.

## Page-Type Contracts (authoritative)

Each page type has a contract under [`page-types/`](page-types/) describing the required
frontmatter, body structure, and ID pattern:

| Type | ID pattern | Contract |
|---|---|---|
| Product | `PRODUCT-<NNN>` | [`page-types/product.md`](page-types/product.md) |
| Epic | `EPIC-<NNN>` | [`page-types/epic.md`](page-types/epic.md) |
| Feature | `FEAT-<NNN>` | [`page-types/feature.md`](page-types/feature.md) |
| Requirement | `REQ-<AREA>-<NNN>` | [`page-types/requirement.md`](page-types/requirement.md) |
| Decision | `DEC-<NNN>` | [`page-types/decision.md`](page-types/decision.md) |
| Test case | `TC-<AREA>-<NNN>` | [`page-types/test_case.md`](page-types/test_case.md) |

`id` MUST match the filename. Frontmatter drives rendering; the build hook is in
[`../../tools/requirements-site/hooks/cross_refs.py`](../../tools/requirements-site/hooks/cross_refs.py).

## Hard Rules (repeat-of-shared, surfaced here for safety)

- **`source-import/` is read-only** — never modify the original Excel / PDF / PPTX files. Extract into Markdown under the matching type folder.
- **Requirement `status` is governance-only** (`draft` → `review`/`approved`); `review` and
  `approved` are governance-controlled, so author new requirements at `status: draft` and do not
  set the others yourself. **Never put an implementation state (`in-progress`/`done`) in
  requirement frontmatter, and never set `owner` to a real name — leave `owner: TBD`.**
  Implementation status + owner live ONLY in `openspec/track.md` (the single source of truth); the
  requirement page and product dashboard render them from the ledger via the `cross_refs` hook.
  `mkdocs build --strict` fails if a requirement carries an implementation status or a non-`TBD`
  owner.
- **Every content edit appends a `change_history` entry** (bottom of frontmatter, chronological, newest last). Never delete or rewrite older entries; record reverts as new entries.
- **Every requirement content edit also updates its feature changelog** — when changing text,
  scope, metadata, architecture notes, or any other content in a page under `requirements/`, append
  a matching `change_history` entry to the requirement and to its parent `feature: FEAT-…` page.
- **Every test-case edit also updates linked changelogs** — when adding or changing a page under
  `test_cases/`, append a matching `change_history` entry to each referenced requirement and to
  each affected parent feature. Limit those requirement/feature edits to changelog entries unless
  the task explicitly asks for content changes.
- **Do not run the importer.** It is intentionally blocked; see [`../../.agents/subagents/requirements-site/done.md`](../../.agents/subagents/requirements-site/done.md).
- **`mkdocs build -f tools/requirements-site/mkdocs.yml --strict` must succeed** after any change here.

Site rendering / template / hook changes belong to the **sitebuilder** role under
[`../../tools/requirements-site/AGENTS.md`](../../tools/requirements-site/AGENTS.md) — do not edit
templates from this area.
