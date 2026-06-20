# to_be_migrated_repo/

This folder is a placeholder for the **legacy codebase being migrated**.

Place the read-only legacy source code (or a reference copy of it) here so agents can analyze it during requirements discovery and migration planning.

## Usage

1. Copy or clone the legacy source code into this folder.
2. Mark it as read-only in AGENTS.md / CI guardrails to prevent accidental modification.
3. Agents reference this code as a **secondary source** for behavior parity — never as the source of truth for new requirements.

## Important

- **Never edit** the files in this folder — treat them as frozen reference material.
- The canonical requirements live in `docs/requirements/`, not here.
- CI should reject any PR that modifies files under this path.

## Structure

Organize by the legacy system's original structure, for example:

```
to_be_migrated_repo/
├── {legacy-module-1}/
├── {legacy-module-2}/
└── README.md  <- this file
```
