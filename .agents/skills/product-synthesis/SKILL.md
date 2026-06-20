---
name: product-synthesis
description: >
  For a given {PROJECT-NAME} product (PRODUCT-ID / type code, e.g. "PRODUCT-002 / ASG"), extract
  relevant information from all three primary sources — legacy codebase ({LEGACY-CODEBASE-DIR}/),
  specification document (docs/requirements/source-import/),
  and Azure Boards user stories (reports/evaluations/azure-boards/{project}-stories/) — and
  synthesize a unified per-product feature specification document under
  reports/evaluations/product-analyses/PRODUCT-<NNN>-<CODE>.md.
  Use this skill when asked to "analyse product X", "synthesize product X",
  or "run the product synthesis pipeline for product X".
---

# Product Synthesis Pipeline

Deterministic process for synthesising a product-level feature specification from the three
canonical {PROJECT-NAME} sources. Run it once per product. The output drives or validates the FEAT-* and
REQ-* pages for that product.

## When to use

- User asks to analyse or synthesise a specific {PROJECT-NAME} product.
- You are verifying coverage before authoring new FEAT/REQ files for a product.
- You want to find discrepancies between the legacy implementation, the specification document, and the
  agreed user stories.

## Inputs

| Input | Where to find it |
|---|---|
| Product ID and type code | `docs/requirements/products/PRODUCT-<NNN>.md` — see `spec_codes` |
| Legacy codebase | `{LEGACY-CODEBASE-DIR}/` — search for `<type_code>` (case-insensitive) in filenames and in `auftrag_type` assignments |
| Specification document | `docs/requirements/source-import/` — read the chapter for the product type. If the PDF cannot be rendered, use existing references in `docs/requirements/features/` and `docs/requirements/requirements/` (the `source:` field) |
| Azure Boards user stories | `reports/evaluations/azure-boards/{project}-stories/` — grep for the type code in filenames and story text |
| Existing requirements | `docs/requirements/features/` and `docs/requirements/requirements/` — grep for the product tag or PRODUCT-ID to see what is already mapped |

## Step 1 — Identify legacy codebase artefacts

1. `Glob("{LEGACY-CODEBASE-DIR}/**/*<code>*")` — list files whose name contains the type code (case-insensitive).
2. `Grep("AUFTRAG_TYPE.*<code>|auftrag_type.*<code>", "{LEGACY-CODEBASE-DIR}/", "-i")` — find all places where the legacy code branches on this product type.
3. Read each matching file. Extract:
   - **DB table(s)** the product writes to or reads from.
   - **Form fields** with `maxlength` attributes → field name, max length, mandatory flag.
   - **Business rules** encoded in conditional branches: type-specific validation, conditional sections, defaults.
   - **Status values** (for the product's lifecycle state machine).
   - **Import / migration scripts** if any — they reveal the legacy data model.
4. Record findings in the synthesis document under **Source 1 — Legacy Codebase**.

## Step 2 — Identify specification document content

1. Try to read the specification document under `docs/requirements/source-import/`. If renderable, locate the chapter for the product type code and extract:
   - Section number and title.
   - Form field definitions (labels, mandatory flags, validation rules).
   - Business rules and exceptions.
   - Incompatibility rules specific to this product.
   - Duration/validity constraints.
2. If the document is not renderable, fall back to:
   - `Grep('SRC-{SPEC-DOCUMENT-ID}', "docs/requirements/", "-r")` — find every requirement that cites a specification source; their `section:` values reveal which chapters were already processed.
   - The product page `docs/requirements/products/PRODUCT-<NNN>.md` for the `mapping_note`.
3. Record findings in the synthesis document under **Source 2 — Specification Document**.
4. Mark any sections not yet processed as `TODO: specification pass needed`.

## Step 3 — Identify Azure Boards user stories

1. `Grep("<CODE>", "reports/evaluations/azure-boards/{project}-stories/", "-i", "--include=*.md")` — list stories that mention the type code.
2. Look for the **orchestrator story** (the "Create a <product name>" story that lists all sub-steps).
3. For each sub-story: read the file and extract:
   - Story number (used in `azure_story_ids`).
   - State (Accepted / Specified / Estimated / New).
   - Phase (from Tags field).
   - Story points.
   - Acceptance criteria — copy verbatim; these are the contract.
   - Specific field constraints mentioned in the description (max chars, mandatory, validation rules).
4. Record findings in the synthesis document under **Source 3 — Azure Boards User Stories**.

## Step 4 — Cross-check existing requirements

1. `Grep("PRODUCT-<NNN>|<code>", "docs/requirements/features/", "-i", "--include=*.md", "--files-with-matches")` — list features already mapped to this product.
2. For each matched feature, read it and note which requirements it owns.
3. Build a **coverage table**: for each product feature identified in Steps 1–3, record whether a FEAT-* and REQ-* page already exist.
4. Record gaps (features without a requirement page) and conflicts (requirement text disagrees with a source).

## Step 5 — Synthesise

For each product feature:

1. Place the three source extractions side by side.
2. Identify:
   - **Agreements** — all three sources say the same thing.
   - **Conflicts** — sources disagree (e.g. different max lengths). **Azure Boards is first-priority** when sources conflict, unless the specification document explicitly overrides it. Flag conflicts with `⚠ CONFLICT`.
   - **Gaps** — a source mentions something the others do not. Flag with `⚠ GAP — source only`.
3. Write the unified specification for each feature.
4. Note whether the existing REQ-* page (if any) needs correction.

## Output format

Write the result to:

```
reports/evaluations/product-analyses/PRODUCT-<NNN>-<CODE>.md
```

Use the template structure:

```markdown
# Product Synthesis: PRODUCT-<NNN> — <CODE> (<Full name>)

_Generated: <date> | Sources: Legacy Codebase, Specification Document, Azure Boards_

## Product identity
## Source 1 — Legacy Codebase
## Source 2 — Specification Document
## Source 3 — Azure Boards User Stories
## Unified feature map
  ### F<n>: <feature name>
  (per feature: Source comparison table → Unified spec → Existing REQ-* mapping → Open questions)
## Cross-reference to existing FEAT-* and REQ-*
## Discrepancies requiring requirement fixes
## Open gaps (no requirement page yet)
```

## Rules

- **Do not modify any file under `to_be_migrated_repo/`** — read only.
- **Do not modify source-import PDFs or XLSXs** — read only.
- Set `status: draft` on any new requirement or feature page you create as a result of this synthesis.
- If you discover a conflict that requires changing an existing REQ-* file, record it in the synthesis under **Discrepancies requiring requirement fixes** and fix the REQ-* file. Append a `change_history` entry.
- Use `TODO` for every PFH section you could not read directly.
- The synthesis document itself goes in `reports/evaluations/product-analyses/` — it is a derived evaluation, not a source document. Do not reference it from mkdocs nav or from a `source:` field in requirements pages.
