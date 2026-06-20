# Ownership

Area reviewers for pull requests. Azure DevOps has no native `CODEOWNERS`; wire these as
**branch policy automatic reviewers** (path filters) on `master` so the right people are
added automatically. Keep this file in sync with those policies.

| Area / path | Reviewers | Notes |
|---|---|---|
| `csharp/src/backend/` | TODO | Clean Architecture / CQRS / DDD backend |
| `csharp/src/frontend/` | TODO | Next.js / TypeScript frontend (pnpm) |
| `csharp/test/` | TODO | C# test projects |
| `csharp/azure/`, `*.yml` pipelines | TODO | CI/CD, Helm, infrastructure |
| `to_be_migrated_repo/` | TODO (approval required to change status) | Frozen read-only legacy reference |
| `docs/requirements/` | TODO | Requirements engineering |
| `docs/architecture/` | TODO | Architecture & ADRs |
| `tools/requirements-site/` | TODO | MkDocs requirements-site tooling |
| `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.agents/`, `agents/` | TODO | Agent configuration |

TODO: replace each `TODO` with the responsible person(s) once the team is confirmed.
