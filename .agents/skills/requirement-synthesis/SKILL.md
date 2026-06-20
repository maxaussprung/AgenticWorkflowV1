---
name: requirement-synthesis
description: >
  For a given {PROJECT-NAME} product ({PRODUCT-NNN}), create one product-specific
  FEAT file as the home for all product-specific requirements, then write REQ-*.md files
  under it. Enrich existing shared FEAT files with source citations (additive only).
  Every file includes a Source Atlas showing what each source (Gold/Silver/Bronze) says.
---

# Requirement-Synthesis Pipeline

**One agent = one product. Read this file completely before touching anything.**

---

## Core principle

Each product gets **one new product-specific FEAT file** that owns all product-specific REQs.

Shared/cross-product FEAT files (e.g. FEAT-005 "common building blocks") still exist and
cover this product — but new REQs go under the product-specific FEAT, not under shared FEATs.
Shared FEATs only get source citations added (never new REQs attached).

Priority when sources disagree:
```
Gold   = {AZURE-BOARDS-SOURCE} User Story  (highest — use this value in formal requirements)
Silver = {SPECIFICATION-DOCUMENT}
Bronze = legacy codebase (BRONZE)   (lowest — document but flag for PO confirmation)
```

`source_tier` on each file = the **highest** tier found for that feature/requirement.

---

## 0 — Read your product entry from the manifest

File: `.agents/skills/requirement-synthesis/product-manifest.yaml`

Find the entry where `id:` matches your assigned `{PRODUCT-NNN}`. Record:

| Field | What you need it for |
|---|---|
| `code` + `spec_sections` | grep terms for legacy codebase and gap analysis |
| `spec_sections` | specification document section IDs to look up in the gap analysis |
| `legacy_primary_files` | legacy codebase files to scan |
| `cf_special_notes` | Pre-researched legacy codebase findings — include automatically |
| `azure_grep_terms` | Terms for searching Azure stories |
| `feat_id_range` | Available FEAT ID budget |
| `req_area` | Area code for new requirements (e.g. {PRODUCT-CODE}) |
| `existing_feat_ids` | Existing FEATs already covering this product |

---

## 1 — Check whether the product-specific FEAT already exists

Run:
```
Grep(pattern="Product: {PRODUCT-NNN}$", path="docs/requirements/features/",
     glob="*.md", output_mode="files_with_matches")
```

Also check `existing_feat_ids` from the manifest. Read every matching FEAT file.

**If a product-specific FEAT already exists** (a FEAT whose `Product:` is ONLY this product
and whose title clearly covers product-specific entry mask / capabilities):
→ That is the home FEAT. Use it. Do not create a duplicate.

**If no product-specific FEAT exists yet:**
→ You will create one in Step 6. Use the **next free ID** from `feat_id_range`
  (verify by listing `docs/requirements/features/`).

Also find all REQs already linked to existing FEATs for this product:
```
Grep(pattern="feature: FEAT-NNN", path="docs/requirements/requirements/",
     glob="*.md", output_mode="files_with_matches")
```

Read those REQ files. This tells you what is already captured.

---

## 2 — Harvest: {AZURE-BOARDS-SOURCE} User Stories (GOLD)

For each term in `azure_grep_terms`, search the stories directory:
```
Grep(pattern="<term>", path="reports/evaluations/azure-boards/{project}-stories/",
     glob="*.md", output_mode="files_with_matches", -i=true)
```

For every matching story file, read it fully and record:

```
Story ID:             (number from filename, e.g. 614840)
Title:                (verbatim)
State:                (Accepted / Specified / Estimated / New)
Parent Azure feature: (feature IDs referenced, e.g. #609539 "Feature title")

Acceptance Criteria (verbatim, numbered):
  AC-1: Given … when … then …

Field constraints:
  Field name | maxlength | mandatory | control type | validation rule | allowed values

Business rules:
  Every "must", "shall", "only if", "not allowed" statement
```

Stories with state "Accepted" have highest confidence. Flag "New"/"Estimated" as `⚠ state: <state>`.

---

## 3 — Harvest: {SPECIFICATION-DOCUMENT} via gap analysis (SILVER)

Primary file: `reports/evaluations/specification-document-vs-azure-boards-gap-analysis.md`

For each section ID in your manifest's `spec_sections`, find the row and record:

```
Section-ID:     (e.g. SPEC-045)
Doc §ref + page:(e.g. §11.10.1.7, p.94)
Description:    (verbatim)
Azure coverage: (story number if listed, or "Gap" / "Partial")
Legacy code column: (which legacy files listed)
```

Also scan:
- `## Legacy vs. specification document — Direct Conflicts` → CONF-NNN rows for your product
- `## Legacy codebase — Full Source Analysis` → Bronze rows for your product

---

## 4 — Harvest: legacy codebase (BRONZE)

For each file in `legacy_primary_files`, grep for your product codes then read relevant sections:
```
Grep(pattern="<code>", path="{LEGACY-CODEBASE-DIR}/<filename>",
     output_mode="content", context=4)
```

Record per finding:
```
Legacy file:  (exact filename)
Line approx:  (e.g. line ~229)
Field/rule:   (variable name, maxlength, condition, hardcoded value, error text)
Spec match?:  yes / no / partial
```

Always include all `cf_special_notes` from the manifest as Bronze findings.

**`{LEGACY-CODEBASE-DIR}/` is READ-ONLY — never write anything there.**

---

## 5 — Map sources to features

Group all findings from Steps 2–4 into logical feature areas
(e.g. "duration / validity", "new address entry", "person data", "shipment types").

For each area, note which sources cover it and where they agree/conflict:
```
Feature area: "Duration / validity period"
  → Gold:   #636365 AC-1: max 12 months; #692536 mentions admin override
  → Silver: specification document §11.4.2 p.89: max 12 months, no admin override mentioned
  → Bronze: legacy-module/validity.ext: 12 months normal users; admin/support ≈18 months (CONF-006)
  → Conflict: specification document silent on admin override; legacy code adds 18-month admin path → TODO: PO confirm
```

Check: does any area lack coverage in the existing shared FEATs AND in your product FEAT?
Those are candidates for new REQ files.

---

## 6 — Create (or verify) the product-specific FEAT file

**Naming convention (follow the pattern your colleague established):**
`[{PRODUCT-CODE}] — [product name] entry mask ([{PRODUCT-CODE}]-specific capabilities)`

Examples:
- `PROD-A — Example Product A entry mask (PROD-A-specific capabilities)`
- `PROD-B — Example Product B entry mask (PROD-B-specific capabilities)`

**If already exists** (from Step 1): read it fully, then augment it:
- Add missing `azure_story_ids:`, `cf_source:`, structured `source:` entries
- Add or update the Source Atlas section in the body
- Append `change_history` entry

**If creating new:**
Use frontmatter from `docs/requirements/page-types/feature.md` (read the contract first):

```yaml
---
type: feature
id: FEAT-NNN
title: "[{PRODUCT-CODE}] — [product name] entry mask ([{PRODUCT-CODE}]-specific capabilities)"
Product: {PRODUCT-NNN}          # singular — only this product
kind: functional
Phase: ""
implementation_status: ""
Priority: 1
source_tier: gold | silver | bronze   # highest tier found
Sprints: 0
tags:
  - <product-tag>
source:
  - document: SRC-SPEC
    section: "specification document §N.N — section title"   # one entry per relevant section
cf_source:
  - "{LEGACY-CODEBASE-DIR}/filename — what it implements"   # one entry per legacy file
azure_story_ids:
  - NNNNNN                                 # one entry per Azure story
System: ""
Accountable: []
Supported: []
Domain IDs: []
change_history:
  - "**2026-06-09**: Created — product-specific FEAT for {PRODUCT-NNN}. Sources: [list]."
---
```

Body structure:

```markdown
## Purpose

<2–3 sentences: what this product does for the end user>

## Key behaviour

<Bullet list of the most important product-specific behaviors, using the winning source value
for each. Mark Bronze-only items with ⚠.>

## Source Atlas

<!-- What each source says about this product's key aspects -->

| Aspect | Gold — US | Silver — specification document | Bronze — legacy codebase | Used | Notes |
|---|---|---|---|---|---|
| <field or rule> | <value + #story + AC-N> | <value + SPEC-NNN + §ref> | <value + legacy-file line ~N> | <winner> | Conflict? |

_"—" = source has no data for this aspect. Rows where USED ≠ Gold mean no Azure story covers it yet._

## Legacy codebase notes

<Only include if legacy code reveals behavior not in specification document or Azure. Bronze-only items. Mark each:>
> ⚠ Bronze-only — TODO: verify with PO before implementing.
```

---

## 7 — Write REQ files under the product-specific FEAT

One REQ per atomic testable "The system shall…" statement.

**Check existing REQ files first:**
```
Grep(pattern="REQ-<AREA>-", path="docs/requirements/requirements/",
     glob="*.md", output_mode="files_with_matches")
```

For each existing REQ that covers this product: **augment it** (add source citations, Source Atlas).
For each finding NOT yet covered by any REQ: **create a new REQ**.

**New REQ numbering:** Use the next free `REQ-<AREA>-NNN` number.

Read `docs/requirements/page-types/requirement.md` for the full contract. Key frontmatter:

```yaml
---
type: requirement
id: REQ-<AREA>-NNN
title: <concise title>
feature: FEAT-NNN              # the product-specific FEAT from Step 6
applications:
  - {PROJECT-NAME}
owner: TBD
status: draft
priority: must | should | could | wont
tier: 1
source_tier: gold | silver | bronze
kind: functional
nfr_category: ""
depends_on: []
source:
  - document: SRC-SPEC
    section: "specification document §N.N — section title"
cf_source:
  - "{LEGACY-CODEBASE-DIR}/filename — exact behavior (line ~N)"
azure_story_ids:
  - NNNNNN
tags:
  - <product-tag>
change_history:
  - "**2026-06-09**: Created. Sources: [list]. [Conflict note if any.]"
---
```

**Body — all sections mandatory (use placeholder if not applicable):**

```markdown
### User Story

**As** <role>
**I want** <capability>
**So that** <business value>

### Formal Requirement

> The system shall … [winning source language — if AC exists in Azure story, paraphrase it]

### Acceptance Criteria

> **Evidence** (highest tier: GOLD | SILVER | BRONZE):
>   - **Gold (Azure):** #NNNNNN "Story title" [State], …   ← omit if no Azure story
>   - **Silver (specification document):** SPEC §N.N — Section title           ← omit if no specification document source
>   - **Bronze (legacy codebase):** legacy-filename, …                     ← omit if no legacy source
>   - **Conflict resolved:** …                             ← only when source_conflict_note is set

1. **<Label>** *(Gold — #NNNNNN)*
   Given …, when …, then ….

2. **<Label>** *(Silver — specification document §N.N)*
   Given …, when …, then ….

[Annotate each AC with its tier in parentheses. Evidence block gives the full source summary.]

### Source Atlas

| Aspect | Gold — US | Silver — specification document | Bronze — legacy codebase | Used | Notes |
|---|---|---|---|---|---|
| <field/rule> | <value + #story + AC-N> | <value + SPEC-NNN + §ref> | <value + legacy-file line ~N> | <winner> | |

### Exclusions

- <what this requirement does NOT cover>

### Architecture

*Owned by the architect — populated after this requirement is approved.*

#### Technical Dependencies

*Owned by the architect — populated after this requirement is approved.*
```

---

## 8 — Enrich existing shared FEAT files (additive only)

For each shared/cross-product FEAT (like FEAT-005, FEAT-006) that already covers this product:

1. Add missing `azure_story_ids:`, `cf_source:`, `source:` entries to frontmatter
2. Add a `## Source Atlas ({PRODUCT-NNN} — {PRODUCT-CODE})` section to the body if not present
3. Append a `change_history` entry

**Do NOT add new REQs to shared FEATs.** New REQs belong under the product-specific FEAT.

---

## 9 — (Synthesis doc removed)

Do **NOT** create a synthesis document. The synthesis step has been retired.
The permanent, browsable record for each product lives in
`reports/evaluations/product-analyses/{PRODUCT-NNN}-{PRODUCT-CODE}.md` (your colleague's
detailed analysis) and is surfaced via the "Product Analyses" tab in the
requirements site. No additional tracking file is needed.

---

## 10 — Source tier rules

| Condition | `source_tier` |
|---|---|
| At least one Azure story found | **gold** |
| No Azure story, specification document section found | **silver** |
| Legacy codebase only (no specification document, no US) | **bronze** |
| Nothing found | **NOT ALLOWED — write TODO** |

Bronze-only items always get: `> ⚠ Bronze-only — TODO: verify with PO before implementing.`

---

## 11 — Conflict resolution

When sources disagree on a field or rule:
1. **Winning value** (Gold > Silver > Bronze) goes in the Formal Requirement text
2. **Both values** appear in the Source Atlas table — never hide the losing value
3. `change_history` entry: `"<source A> says X; <source B> says Y → X adopted (Gold priority)."`
4. Specification document vs legacy codebase with no Azure story → keep specification document, add `TODO: PO confirmation`

Example:
```
Dropoff location maxlength:
  Gold  US #614840 AC-3: 93 chars → USED
  Legacy    {LEGACY-CODEBASE-DIR}/import-script: truncates at 100 chars
  → Source Atlas: US=93(#614840) | specification document=— | Legacy=100(import-script) | USED=93 | Conflict=YES
  → change_history: "US #614840 says 93 chars; legacy code truncates at 100. 93 adopted (Gold priority)."
```

---

## Hard constraints (non-negotiable)

1. `{LEGACY-CODEBASE-DIR}/` is **READ-ONLY** — never create, edit, or delete files there.
2. `docs/requirements/source-import/` is **READ-ONLY**.
3. All new FEAT/REQ: `status: draft`. Never `status: approved`.
4. `id:` in frontmatter **must match the filename exactly**.
5. Every edit to an existing file **appends** a `change_history` entry — never delete old entries.
6. **Do not invent requirements** — write TODO if no source confirms.
7. **Check existing files before creating** — augment if the content is there, create if genuinely absent.
8. New REQs go under the **product-specific FEAT** (Step 6), not under shared FEATs.
9. **No synthesis document** — step 9 is retired; do not create one.
10. Do not modify files outside `docs/requirements/`.
