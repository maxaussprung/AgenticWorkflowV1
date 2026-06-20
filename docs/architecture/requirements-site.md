# Architecture

How the documentation site is built, not what it documents. This is the reference for anyone
(human or agent) extending the theme or build pipeline.

## What this repo is

A static site built with **MkDocs Material**. Pages are hand-authored Markdown with YAML front
matter declaring a `type`; the theme renders a type-specific header card and the cross-references
hook joins pages together by ID.

Source material for `{PROJECT-NAME}` lives under
[`docs/requirements/source-import/`](../requirements/source-import/) (specification documents,
PDFs, decks). Extraction into this site is manual/iterative — not driven by an automated
importer.

The requirements-site framework is reusable across projects. When adapting it to a new project:
the framework components (page-type partials, hooks, theme, estimation roll-up) are kept as-is;
the program-specific imported content (visions, activities, features, epics) is replaced with the
new project's content. Any existing **application catalogue**
(`docs/requirements/applications/`) and **domain catalogue** (`docs/requirements/domains/`) that
describe the client organization can be retained if they apply.

## Pipeline

```
Source material
(docs/requirements/source-import/)
       │
       │   manual extraction
       ▼
   Hand-authored .md
   under docs/requirements/<type>/
       │
       ▼
   mkdocs build
       │
   ┌───┴───┐
   ▼       ▼
 on_config  on_env
 build xref  expose xref
 + expand    to Jinja
 nav
       │
       ▼
 tools/requirements-site/overrides/main.html
   dispatches on
   page.meta.type
       │
       ▼
 reports/evaluations/requirements-site/ (HTML)
```

## Components

### 1. Cross-references hook — [`tools/requirements-site/hooks/cross_refs.py`](../../tools/requirements-site/hooks/cross_refs.py)

A single mkdocs hook that, by reading every doc page's YAML front matter once per build, drives
several things:

| Lifecycle event | What it does |
|---|---|
| `on_config` | Scans `docs/requirements/**/*.md`, parses front matter, builds the registry, loads the **specification section index** (`docs/requirements/sources/{spec}-section-index.yaml`), and **walks `config['nav']` and expands** any section whose index page declares `index_of: <type>` *and* `nav_children: true` — appending one nav entry per page of that type, sorted by natural ID, labelled by the page `id`. |
| `on_env` | Exposes the registry as the Jinja global `xref` so templates can resolve `(type, id) → {title, url}`. Also exposes `spec_coverage` (see below) and registers a `markdown` Jinja filter so partials can render small Markdown snippets (e.g. each `change_history` entry's bold date). |

The registry shape is `xref = { type: { id: {title, url, meta} } }` with each `xref[type]` dict
iterating in natural ID order (`1`, `1.1`, `1.1.1`, `1.2`, …). `meta` holds the full parsed
front matter so templates can read arbitrary fields (e.g. `entry.meta.Priority` on an index).

This is the single point that makes title changes propagate everywhere on the next `mkdocs build`.

> **Frontmatter must parse.** A page whose YAML front matter fails to parse is silently dropped
> from the registry (and the coverage matrix), even though `--strict` may still pass. Common
> traps: a `title:` whose unquoted value contains `: `, and a double-quoted `section:` containing
> an inner straight `"`. Quote such values, or avoid embedded quotes.

#### Specification coverage (`spec_coverage`)

The hook also computes how completely the project's primary specification document (`{SPEC-DOCUMENT}`)
is reflected in requirements. It reads the canonical chapter list from
`docs/requirements/sources/{spec}-section-index.yaml` (every sub-chapter, with a
`coverage_expectation: required | informational` flag), then scans every feature/requirement
`source:` entry citing the specification, extracting the leading section ID. The result —
`spec_coverage = { sections: [...], stats: {required, covered, uncovered, pct} }` — is rendered
as a **coverage matrix on the specification source-document page** (report-only; a future
`--strict` gate can fail on any uncovered `required` leaf). A specification citation MUST use the
canonical form `section: "{SPEC-DOCUMENT} §<id> — <title>"` or it is **not** counted.

### 2. Theme overrides — [`tools/requirements-site/overrides/`](../../tools/requirements-site/overrides/)

`tools/requirements-site/mkdocs.yml` has `theme.custom_dir: overrides`, so any file here shadows
mkdocs-material's same-path file.

| File | Role |
|---|---|
| `main.html` | Extends mkdocs-material's `base.html`. Dispatches to the type-specific header partial via `page.meta.type`, then `{{ super() }}` to render the markdown body, then includes `index-of` if `page.meta.index_of` is set. Also dispatches the special page types `requirement-map`, `business-board`, and `source-traceability`. |
| `partials/<type>-header.html` | One per type (`product`, `feature`, `requirement`, `decision`, `application`, `domain`, `test_case`, `source_document`). Reads `page.meta.*` and renders the structured header card. Feature/product headers render a **Source Tier** tag (gold/silver/bronze) and a **Sources** block (board / specification / legacy codebase, in priority order); features also render an optional **Conflict Resolution** row from `source_conflict_note`. |
| `partials/index-of.html` | For any page with `index_of: <type>` in front matter, renders a sorted (ID, Title) HTML table from `xref[type]`. Reads `index_columns` to add extra columns (`Priority` and `source_tier` render as coloured tags). |
| `partials/linked-list.html` | Reusable cross-reference renderer. Caller passes `ids_raw`, `xref_type`, `heading` via `{% with %}`; partial parses the comma-list, resolves each via `xref[xref_type]`, and emits a heading + bullet list of links. |
| `partials/back-links.html` | Reverse direction of `linked-list`: iterates `xref[xref_type]` and lists every page whose `field:` names `target_id`. Used for "Referenced by …" sections. |
| `partials/product-feature-map.html` | On a product page, renders a *Features & Sources* table of every feature whose `Product` names this product, with each feature's source-tier tag and a board/specification/legacy-codebase summary. Also used by the global Source-traceability page. |
| `partials/source-traceability.html` | The site-wide overview page (`source-traceability.md`): walks every product and renders its feature/source table. |
| `partials/change-history.html` | Renders the `change_history` list as a "Change history" section. Each entry runs through the `markdown` filter so the bold date renders. |
| `partials/content.html` | Local override of mkdocs-material's content partial. One-line change: skip the auto-generated `<h1>` from `page.title` when `page.meta.type` is set, since the type-specific header partial already provides one. |
| `partials/features-estimation.html` / `partials/business-board.html` / `partials/requirement-map.html` / `partials/unknown-applications.html` | Specialised partials for derived/overview pages. |

The `source_document-header.html` partial additionally renders the **specification coverage
matrix** (see the hook section) when it is on the primary specification source page.

### 3. Stylesheet — [`docs/requirements/stylesheets/extra.css`](../requirements/stylesheets/extra.css)

Card colours per type (`.rm-card--feature`, `.rm-card--domain`, …), tag/status/priority colours,
and `.rm-meta__desc { white-space: pre-line }` so multi-line description cells render their
`Alt+Enter` line breaks. Also: `.tag--source-tier-{gold|silver|bronze}` (source-tier badges),
`.rm-sources`/`.rm-feature-map` (the per-feature source breakdown and product feature-map table),
and `.tag--cov-{covered|uncovered|informational}` (the specification coverage matrix).

### 4. mkdocs config — [`tools/requirements-site/mkdocs.yml`](../../tools/requirements-site/mkdocs.yml)

Standard mkdocs-material config plus:

- `docs_dir: ../../docs/requirements`
- `site_dir: ../../reports/evaluations/requirements-site`
- `hooks: [hooks/cross_refs.py]`
- `nav` lists each section's index page; section pages with `nav_children: true` are expanded by
  the hook so the section index doesn't have to list every page by hand.
- `not_in_nav: |` lists glob patterns for pages built but deliberately not navigable from the
  sidebar (e.g. `/domains/D*.md`).

## Page contract

Every typed page declares at minimum:

```yaml
---
type: <one of: product | feature | requirement | decision | test_case | application | domain | source-document>
id:   <unique-within-type identifier>
title: <human-readable title>
---
```

(Plus a few singleton "special" pages keyed by `type` but with no per-instance contract:
`requirement-map`, `business-board`, `source-traceability`.)

Optional flags the system understands:

- `index_of: <type>` — this page is an index of all pages of `<type>`; the table is rendered
  dynamically.
- `nav_children: true` — expand this section in the sidebar with one child per page of the
  matching `index_of` type.

For the per-type frontmatter contract (which optional fields each type supports and what they
mean), see the **Page types** section of the site (`docs/requirements/page-types/`).

## Adding a new type

1. **Theme**: add `tools/requirements-site/overrides/partials/<new-type>-header.html` (copy a
   sibling) and add the `elif page_type == "<new-type>"` branch to `main.html`.
2. **CSS**: add a `.rm-card--<new-type>` colour swatch in `extra.css`.
3. **Nav**: add a section to `tools/requirements-site/mkdocs.yml` pointing at `<subdir>/index.md`.
4. **Docs**: add `docs/requirements/page-types/<new-type>.md` describing the frontmatter contract
   and body structure.

No changes to the cross_refs hook are needed; it's generic over `type`.

## Building

Use the repository-local virtual environment at `.venv/` (do **not** create a second venv under
`tools/requirements-site/`):

```bash
.venv/bin/pip install -r tools/requirements-site/requirements.txt
.venv/bin/mkdocs serve -f tools/requirements-site/mkdocs.yml          # live preview at :8000
.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml --strict # static output in reports/evaluations/requirements-site
```

`--strict` is the CI gate — it must pass before merge.
