# /setup-repo

Set up this repository template for a new project by replacing all placeholder values interactively.

## What it does

Reads `.agents/skills/setup-repo-structure/SKILL.md` and executes the guided setup:
- Asks you a series of questions (project name, client name, tech stack, Azure DevOps details, legacy system info, spec documents, external services)
- Performs bulk placeholder replacement across the entire repository — both **file contents** and **file/folder names** (e.g. `Dockerfile.{project-name}-ui`, the `Mock/EXAMPLE-*-MOCK/` folders, `SRC-EXAMPLE-001.md` are renamed on disk, not just their contents)
- Reports what was changed and renamed, and what still needs manual attention

## When to use

Run this once, immediately after cloning this template for a new project — before any development work.

## Usage

```
/setup-repo
```

No arguments needed. The agent will guide you through the questions interactively.

## Reference

All placeholders are documented in [`project-placeholders.md`](../../docs/architecture/project-placeholders.md) under `docs/architecture/`.
