# Agent Instructions - legacy-sql/ (READ-ONLY)

This directory is for **client-provided legacy SQL** from the legacy codebase-backed ({LEGACY-TECH}) {PROJECT-NAME}/{LEGACY-SYSTEM-NAME}
database layer. It is a **secondary** reference for understanding data structures, stored behavior,
and behavior parity. Primary requirements come from customer documents and project management tickets curated in
`../docs/requirements/`.

Read the repository root `../AGENTS.md` first.

## Rules

- **Never edit, delete, reformat, modernize, or execute imported SQL under `legacy-sql/` as
  deployment code.**
- Do not convert legacy SQL into active migrations here. Active implementation database changes
  belong under `../csharp/` and must follow the C# project rules.
- When asked to import a new client-provided SQL snapshot, preserve the source layout and content
  for traceability, then update `README.md` provenance notes.
- Use SQL files here only to understand current or historical behavior. Record confirmed findings
  under `../docs/requirements/` when they become requirements or source observations.
- The legacy codebase source ({LEGACY-TECH}) is not available yet. When it arrives, build a legacy codebase-to-SQL call
  map before assuming which SQL objects are actively used by the legacy application.
- Confirmed requirements take precedence when they conflict with legacy SQL.

Only governance and provenance documentation in this directory should change unless an explicit
owner-approved task changes the status of the legacy SQL material.
