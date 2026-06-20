# Legacy SQL - Frozen Read-Only Reference

This directory holds **client-provided legacy SQL** for the legacy codebase-backed ({LEGACY-TECH}) {PROJECT-NAME}/{LEGACY-SYSTEM-NAME}
database layer. It is kept as a **secondary reference** for understanding existing data structures,
stored behavior, and behavior parity while {PROJECT-NAME} is extended on the active C# platform under
`../csharp/`.

The legacy codebase ({LEGACY-TECH}) source is not available in this repository yet. Once it becomes
available, map legacy codebase calls to the SQL objects here before treating any stored behavior as used
legacy behavior.

Primary requirements come from customer documents and project management tickets, curated in
`../docs/requirements/`. Confirmed requirements take precedence when they disagree with legacy SQL.

## Rules

- **Do not edit, run, refactor, reformat, or modernize imported SQL here.** It is reference input,
  not deployable database code.
- Preserve the client-provided repository layout when importing a snapshot unless an owner approves
  a different structure for traceability.
- Do not create active migrations, generated SQL, test data output, or deployment scripts here.
  Active implementation database changes belong under `../csharp/` following the C# project rules.
- Treat legacy SQL as evidence of current or historical behavior only. Do not infer new
  requirements from it without recording the source and confirming the requirement.
- Changing this directory from read-only reference material into active implementation material
  requires explicit owner approval (see `../OWNERS.md`).

## Provenance

TODO: Record the client-provided legacy SQL repository or snapshot details:

- source repository or archive name
- branch, tag, commit, or snapshot identifier
- snapshot date
- importer
- any files intentionally excluded from the import

## Suggested Import Layout

If the client-provided repository already has meaningful structure, keep it. If the source is a flat
collection and an owner approves organizing it during import, prefer simple artifact-oriented
folders such as:

```text
legacy-sql/
|-- schema/
|-- tables/
|-- views/
|-- procedures/
|-- functions/
|-- jobs/
|-- data/
`-- misc/
```

Do not reorganize after import just for style.
