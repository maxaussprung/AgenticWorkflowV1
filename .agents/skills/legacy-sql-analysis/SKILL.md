---
name: legacy-sql-analysis
description: Analyze the client-provided legacy {LEGACY-DB-NAME} SQL Server database project against official specification document PDFs, producing a searchable HTML report with inventory tables, risk flags, cross-reference mappings, and diagrams. Use when investigating legacy SQL under legacy-sql/{LEGACY-DB-DIR}, comparing SQL behavior to client requirements, or refreshing reports/evaluations/legacy-sql/legacy-sql-analysis.html.
---

# Legacy SQL Analysis

Use this skill for detailed investigation of the client-provided legacy {LEGACY-DB-NAME} SQL Server database
project under `legacy-sql/{LEGACY-DB-DIR}/`.

The SQL belongs to the legacy database layer. Treat it as read-only evidence, not
active C# implementation code. The legacy codebase under `{LEGACY-CODEBASE-DIR}` is available as
static call-site evidence, but it is not production runtime telemetry; scheduled jobs, datasource
deployment, and active user-flow reachability still require review.

## Generate The Report

Run from the repository root:

```bash
python3 .agents/skills/legacy-sql-analysis/scripts/generate_report.py
```

Outputs:

- `reports/evaluations/legacy-sql/legacy-sql-analysis.html`
- `reports/evaluations/legacy-sql/legacy-sql-analysis-data.json`

## Validate The Report

Run from the repository root after generating the analysis report:

```bash
python3 .agents/skills/legacy-sql-analysis/scripts/validate_report.py
```

Outputs:

- `reports/evaluations/legacy-sql/legacy-sql-analysis-validation.html`
- `reports/evaluations/legacy-sql/legacy-sql-analysis-validation-data.json`

Validation checks PDF page/snippet references, SQL/C# file-line references, diagram source claims,
product mappings, function explanations, and inventory counts. Failed checks indicate broken
evidence; warnings indicate inferred or semantic evidence that needs human review.

## Validate Requirements Traceability

Run from the repository root after promoting legacy SQL or legacy codebase evidence into
`docs/requirements/`:

```bash
.venv/bin/python .agents/skills/legacy-sql-analysis/scripts/validate_traceability.py
```

Outputs:

- `reports/evaluations/traceability-source-validation.html`
- `reports/evaluations/traceability-source-validation-data.json`

This validates requirement and feature frontmatter references to `sql_source` and `cf_source`:
source files, line numbers, SQL object plausibility, and whether each rationale is supported by
nearby or file-level source terms. Failures indicate broken references; warnings indicate semantic or
file-level evidence that should be reviewed manually.

Inputs:

- `legacy-sql/{LEGACY-DB-DIR}/`
- `docs/requirements/source-import/` (specification document PDFs)
- `{LEGACY-CODEBASE-DIR}/`

## Workflow

1. Read root `AGENTS.md` and `legacy-sql/AGENTS.md`.
2. Do not edit or execute imported SQL.
3. Run `scripts/generate_report.py` to refresh the searchable HTML report.
4. Run `scripts/validate_report.py` to create the validation issue matrix.
5. Review the generated semantic comparison, print-field mapping, manual review queue, SQL inventory,
   dependency tables, risks, and open client questions.
6. Promote only confirmed findings into `docs/requirements/`; leave generated analysis under
   `reports/evaluations/`.

## Validation

After script changes, run:

```bash
python3 -m py_compile .agents/skills/legacy-sql-analysis/scripts/generate_report.py
python3 -m py_compile .agents/skills/legacy-sql-analysis/scripts/validate_report.py
.venv/bin/python -m py_compile .agents/skills/legacy-sql-analysis/scripts/validate_traceability.py
python3 .agents/skills/legacy-sql-analysis/scripts/generate_report.py
python3 .agents/skills/legacy-sql-analysis/scripts/validate_report.py
.venv/bin/python .agents/skills/legacy-sql-analysis/scripts/validate_traceability.py
git diff --check
```
