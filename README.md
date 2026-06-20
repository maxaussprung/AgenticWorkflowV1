# {PROJECT-NAME} Monorepo

> Replace `{PROJECT-NAME}` with your actual project name throughout this file and the repository.

This repository provides an **agent-based software migration framework** for building new
applications while migrating from a legacy codebase. The framework combines structured
requirements management, multi-agent AI workflows, and CI/CD pipelines into a single
reproducible template.

The client already started implementing the application under `csharp/`; current work extends
that codebase through tickets and confirmed requirements, preserving existing confirmed behavior
unless an approved requirement changes it.

- **Just cloned this template?** Run the **`setup-repo-structure`** skill first (Claude Code / OpenCode: `/setup-repo`). It interactively replaces every `{PLACEHOLDER}` across the repo — in **file contents *and* file/folder names** (e.g. `Dockerfile.{project-name}-ui`, the `Mock/EXAMPLE-*-MOCK/` folders). The full catalogue is [`docs/architecture/project-placeholders.md`](docs/architecture/project-placeholders.md). Until this is done, tokens like `{PROJECT-NAME}` throughout the repo are expected, not bugs.
- **New here?** Read [`CONTRIBUTING.md`](CONTRIBUTING.md) (how to contribute).
- **Starting to implement something?** Read [`docs/architecture/dev-workflow.md`](docs/architecture/dev-workflow.md) for the developer-facing implementation sequence, [`docs/architecture/implementation-flow.md`](docs/architecture/implementation-flow.md) for the end-to-end repo-to-board flow, and [`docs/architecture/implementation-slice-workflow.md`](docs/architecture/implementation-slice-workflow.md) for agent-selected implementation slices.
- **Coding agent?** Read [`AGENTS.md`](AGENTS.md) (canonical rules for all assistants).

## Repository structure

| Path | What it is |
|------|------------|
| `csharp/` | **Active** application — C# backend (`src/backend/`), Next.js/TypeScript frontend (`src/frontend/`), tests (`test/`), Azure Pipelines, Helm. |
| `to_be_migrated_repo/` | **Frozen, read-only** legacy codebase — a *secondary* reference for behavior parity. Never edited; CI rejects changes (`azure-pipelines-guardrails.yml`). |
| `legacy-sql/` | **Frozen, read-only** client-provided legacy SQL reference — a secondary source for understanding existing data structures and behavior. Not active migrations or deployable database code. |
| `docs/requirements/` | Requirement **content**: hand-authored Markdown with YAML frontmatter. Hierarchy is **products → features → requirements** (+ decisions/ADRs, test cases, applications, domains, sources). A product is the top-level item and maps to an Azure Boards Epic. |
| `docs/architecture/` | Architecture notes, diagrams, and decisions — including [`dev-workflow.md`](docs/architecture/dev-workflow.md) (developer-facing implementation sequence), [`implementation-flow.md`](docs/architecture/implementation-flow.md) (how work flows repo→board), [`implementation-slice-workflow.md`](docs/architecture/implementation-slice-workflow.md) (agent slice claiming and completion), [`tracking.md`](docs/architecture/tracking.md) (repo↔Azure Boards sync), and [`agent-config.md`](docs/architecture/agent-config.md). |
| `tools/requirements-site/` | MkDocs **tooling** (config, theme overrides, build hooks) that renders `docs/requirements/` into a site. |
| `reports/` | Generated/derived artifacts only — `test-results/` and `evaluations/` (the rendered site builds to `reports/evaluations/requirements-site/`). Not a source of truth. |
| `.agents/` | Canonical cross-tool agent assets: `skills/` (`SKILL.md`) and `subagents/` (tool-neutral role specs). |
| `.claude/` | Claude Code glue only: `agents/` wrappers, `commands/` adapters, `skills` symlink -> `.agents/skills`. |
| `.codex/` | Codex compatibility glue only: `skills` symlink -> `.agents/skills`. |
| `.opencode/` | OpenCode glue only: `command/` adapters and `skills` symlink -> `.agents/skills`. |

Top-level files: `AGENTS.md`, `CLAUDE.md` (Claude import shim), `CONTRIBUTING.md`, `OWNERS.md`,
`.editorconfig`, `.gitattributes`, `azure-pipelines-guardrails.yml`,
`azure-pipelines-csharp-backend-build.yml`, `azure-pipelines-csharp-fe-build.yml`.

## Repo-owned Azure pipelines

The root-level C# validation pipelines are owned by this repository and are separate from the
client pipeline files under `csharp/azure/`. Configure these Azure Pipeline variables before
running them; secret values must be stored as secret variables or in an authorized variable group.

| Pipeline | Required variables |
|----------|--------------------|
| `azure-pipelines-csharp-backend-build.yml` | `NUGET_{PROJECT}_USERNAME`, `NUGET_{PROJECT}_CLEAR_TEXT_PASSWORD`, `SONAR_TOKEN` (secret), `SONAR_CLOUD_ORGANIZATION`, `SONAR_CLOUD_BACKEND_PROJECT_KEY` |
| `azure-pipelines-csharp-fe-build.yml` | `NPM_{PROJECT}_USERNAME`, `NPM_{PROJECT}_CLEAR_TEXT_PASSWORD`, `SONAR_TOKEN` (secret), `SONAR_CLOUD_ORGANIZATION`, `SONAR_CLOUD_FRONTEND_PROJECT_KEY` |

Replace `{PROJECT}` with your project's identifier in the variable names above.

Optional SonarCloud display-name variables:

| Pipeline | Optional variable |
|----------|-------------------|
| `azure-pipelines-csharp-backend-build.yml` | `SONAR_CLOUD_BACKEND_PROJECT_NAME` |
| `azure-pipelines-csharp-fe-build.yml` | `SONAR_CLOUD_FRONTEND_PROJECT_NAME` |

`SONAR_TOKEN` is a SonarCloud token and can be reused by both pipelines if it has access to both
SonarCloud projects. The root `.sonarcloud.properties` scopes automatic SonarCloud analysis to
`csharp/src`; the CI pipelines add build/test context and coverage for the backend and React
frontend analyses.

## Agent configuration

`AGENTS.md` is the canonical guidance for all assistants (Claude Code, Codex, OpenCode);
`CLAUDE.md` and the nested `AGENTS.md` files point to it. How rules, skills, and subagents are
wired across the tools — what lives where and why — is documented in
[`docs/architecture/agent-config.md`](docs/architecture/agent-config.md).

## Documentation site

Requirements are Markdown with YAML frontmatter under `docs/requirements/`. Build/preview:

```bash
pip install -r tools/requirements-site/requirements.txt
mkdocs serve -f tools/requirements-site/mkdocs.yml   # http://localhost:8000
```

## C# application

See [`csharp/README.md`](csharp/README.md) for build, test, EF Core migrations, and
docker-compose instructions.
