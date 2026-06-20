# tools/requirements-site/ Agent Instructions

Applies to `tools/requirements-site/` — the MkDocs (Material) build pipeline that renders
`docs/requirements/` into a static site under `reports/evaluations/requirements-site/`.
This is a generic, reusable requirements management framework; all project-specific names
are placeholders (marked `{PROJECT-NAME}`, etc.) that you replace when adopting it.

This area is owned by the **sitebuilder** role. Read the canonical role spec first:
[`../../.agents/subagents/requirements-site/agent_sitebuilder.md`](../../.agents/subagents/requirements-site/agent_sitebuilder.md).
Site architecture in [`../../docs/architecture/requirements-site.md`](../../docs/architecture/requirements-site.md);
authoring rules (NOT this area) in
[`../../.agents/subagents/requirements-site/AGENTS.md`](../../.agents/subagents/requirements-site/AGENTS.md).

## Layout

```
requirements-site/
├── mkdocs.yml              # docs_dir → ../../docs/requirements, site_dir → reports/…
├── requirements.txt        # mkdocs + plugins (`pip install -r`)
├── hooks/
│   └── cross_refs.py       # single-scan xref registry; expands nav_children; markdown filter;
│                           #   computes spec section coverage from spec-section-index.yaml (spec_coverage)
└── overrides/
    ├── main.html           # dispatcher: includes partials/<page.meta.type>-header.html
    └── partials/           # one header partial per page type + index-of, linked-list,
                            # change-history reusable partials
```

## Build / Preview

```bash
pip install -r tools/requirements-site/requirements.txt
mkdocs serve -f tools/requirements-site/mkdocs.yml          # http://localhost:8000
mkdocs build -f tools/requirements-site/mkdocs.yml --strict # MUST pass before merge
```

`--strict` is the CI gate. Any broken link, missing nav entry, or template error fails the build.

## Conventions

- **One scan per build.** `cross_refs.py` reads every page's frontmatter in `on_config` and
  exposes `xref[type][id] => {title, url, meta}` to templates. New page types reuse the
  registry; do not introduce a second scanner.
- **Type dispatch in `overrides/main.html`.** Adding a page type = add a branch in `main.html`
  + new `partials/<type>-header.html` + (optional) CSS swatch in
  `../../docs/requirements/stylesheets/extra.css` + nav entry in `mkdocs.yml`. No hook change
  required.
- **Templates resolve IDs only.** Author pages reference IDs (`feature: FEAT-006`); partials
  resolve them via `xref`. Never hard-code titles in templates.
- **Index pages** declare `index_of: <type>` + `nav_children: true`; the hook auto-expands the
  sidebar. Do not list children manually in `mkdocs.yml` nav.
- **Reusable partials** — use `partials/linked-list.html` for ID lists, `partials/change-history.html`
  for histories. Do not duplicate their logic per page type.

## Anti-Patterns

- Do not edit content under `../../docs/requirements/` from this area — that is the
  requirements-engineer / test-case-designer scope. Sitebuilder changes are pipeline-only.
- Do not commit generated output. The site renders into `../../reports/evaluations/requirements-site/`
  which is generated (and present in repo for preview); never hand-edit those files.
- Do not bypass `--strict`. If a build is failing, fix the root cause; never relax the gate.
- Do not add a second hook that duplicates what `cross_refs.py` already does.
