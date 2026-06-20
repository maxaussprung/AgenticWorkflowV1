# setup-repo

Set up this repository template for a new project by replacing all placeholder values interactively.

Reads `.agents/skills/setup-repo-structure/SKILL.md` and executes the guided setup — asks questions about project name, tech stack, Azure DevOps, legacy system, and specification documents, then performs all placeholder replacements across the repo. This covers both **file contents** and **file/folder names** (paths like `Dockerfile.{project-name}-ui`, the `Mock/EXAMPLE-*-MOCK/` folders, and `SRC-EXAMPLE-001.md` are renamed on disk, not just their contents).

Run once after cloning. See `docs/architecture/project-placeholders.md` for the full placeholder reference.
