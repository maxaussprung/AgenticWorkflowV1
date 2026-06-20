# {PROJECT-NAME} Requirements

MkDocs (Material) site used as the requirements management framework for any software
migration or greenfield project. Pages are typed via YAML frontmatter (`product`,
`feature`, `requirement`, `test_case`, `application`, `domain`) and rendered with
structured header cards. The application catalogue (`docs/requirements/applications/`)
and domain catalogue (`docs/requirements/domains/`) can be seeded from an existing
system inventory; all other content is authored fresh from your project's source material.

For the architecture of the site itself — build pipeline, theme overrides, cross-references
hook — see [docs/architecture/requirements-site.md](../../docs/architecture/requirements-site.md).
For the per-type frontmatter contracts and body templates, see the **Page types** section
of the rendered site or `docs/requirements/page-types/`.

## Quick start

Use the repository-local virtual environment at `.venv/` (do **not** create a second venv here):

```bash
.venv/bin/pip install -r tools/requirements-site/requirements.txt
.venv/bin/mkdocs serve -f tools/requirements-site/mkdocs.yml          # http://127.0.0.1:8000
.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml --strict # static output in reports/evaluations/requirements-site
```

## Repository layout

```
tools/requirements-site/
  mkdocs.yml                     # site config + nav
  requirements.txt               # Python deps (mkdocs, material)
  hooks/cross_refs.py            # builds xref registry, expands sidebar
  overrides/
    main.html                    # dispatch on page.meta.type
    partials/<type>-header.html  # one per type
    partials/index-of.html       # dynamic (ID, title) tables
docs/requirements/
  index.md                       # framing: Tier 1 / Tier 2 / governance
  stylesheets/extra.css          # cards & status/priority badges
  products/     PRODUCT-NNN.md   # top-level product catalogue
  features/     FEAT-NNN.md      # one per feature area
  requirements/ REQ-AREA-NNN.md  # atomic "the system shall…" statements
  decisions/    DEC-NNN.md       # cross-cutting architecture decisions (ADRs)
  test_cases/   TC-AREA-NNN.md   # UAT and integration tests verifying requirements
  applications/ <Display-Name>.md  # application landscape
  domains/      D015.md ...      # domain catalogue
  page-types/                    # frontmatter contracts and body templates per type
  estimation/                    # derived sprint estimate roll-ups per feature
  source-import/                 # source material (specs, PDFs) — read-only
```

## Page types

| Type | ID format | Required frontmatter | Header partial |
|---|---|---|---|
| product | `PRODUCT-NNN` | `id, title, Priority` | `product-header.html` |
| feature | `FEAT-NNN` | `id, title, Product` | `feature-header.html` |
| requirement | `REQ-AREA-NNN` | `id, title, feature, applications, owner, status, priority, tier, kind` | `requirement-header.html` |
| decision | `DEC-NNN` | `id, title, status` | `decision-header.html` |
| test_case | `TC-AREA-NNN` | `id, title, requirements, owner, status, test_type` | `test_case-header.html` |
| application | `<Display-Name>` | `id, title` | `application-header.html` |
| domain | `D<NNN>` | `id, title` | `domain-header.html` |
| source-document | `SRC-<NAME>` | `id, title, file` | `source_document-header.html` |

Templates degrade gracefully — any missing optional frontmatter key is rendered as empty
(`| default("")`). See `docs/requirements/page-types/` for the full per-type contracts
and body templates.

### Source attribution

Features and requirements carry up to three source tiers, rendered as a **Source Tier**
tag and a **Sources** block (priority order Azure > Spec > Legacy):

- `azure_story_ids: []` — Azure Boards user stories (**gold**)
- `source: [{document: SRC-<NAME>, section: "<chapter>"}]` — Primary specification (**silver**)
- `cf_source: []` — legacy source files (**bronze**); each entry should include a rationale
- `sql_source: []` — legacy database objects; supporting evidence, not active migration code

### Status & priority badges

| Field | Value | Colour |
|---|---|---|
| status | approved | green |
| status | review | amber |
| status | in-progress | blue |
| status | done | green |
| status | draft | grey |
| priority | must | green |
| priority | should | amber |
| priority | could | grey |
| priority | wont | red |

## Authoring a new requirement

1. Create `docs/requirements/requirements/REQ-<AREA>-<NNN>.md`.
2. Fill in the frontmatter — keep `id` matching the filename. `status: draft` is the
   authoring default; promotion to `review`/`approved` is a governance step.
3. Use the section structure: User Story → Formal Requirement → Acceptance Criteria →
   *(optional GUI / API / Database / Data Migration sections)* → Exclusions →
   **Architecture** *(architect-owned)*.
4. The cross-link footer (Parent Feature, Linked Applications, Depends on, Required by,
   Verified by Test Cases) is rendered automatically — don't write it by hand.
5. The page appears in the requirements index automatically — no `mkdocs.yml` edit needed.

## Adoption checklist

When adopting this framework for a new project, replace these placeholders:

- `mkdocs.yml`: `site_name`, `site_description`, `site_author`, `site_url`, `logo`, `favicon`
- `mkdocs.yml` nav: `Analyses > Product Analyses` entries and `Sources` entries
- `tools/azure-sync/sync.py`: `AZDO_ORG_URL`, `AZDO_PROJECT` (or use env vars)
- `tools/requirements-site/staticwebapp.config.json`: Azure AD tenant ID and app registration
- `tools/requirements-site/azure-pipelines-docs.yml`: service connection and SWA resource name
