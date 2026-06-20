# Contributing

This monorepo is worked on by a small team alongside coding agents (Claude Code, Codex,
OpenCode). These conventions keep humans and agents from stepping on each other. Agents must
also read [`AGENTS.md`](AGENTS.md).

## Branching & pull requests

- **Trunk-based.** Branch off `master` with short-lived branches named
  `type/short-description` (`feat/`, `fix/`, `chore/`, `docs/`, `req/`).
- Keep PRs **small and single-concern** — easier to review, less merge-conflict surface when
  several people/agents work in parallel.
- Every PR needs at least one review (see [`OWNERS.md`](OWNERS.md) for area reviewers) and
  green CI before merge.
- Reference the requirement(s) or Jira ticket(s) a change implements in the PR description.

## What lives where

The repository map and the rules that govern each area are owned by
[`AGENTS.md`](AGENTS.md#repository-structure) and the nested `AGENTS.md` files. Read those
rather than relying on a copy here — this file covers only human workflow (branching, setup,
checks).

## Local setup

- **C# backend:** `cd csharp && dotnet build` / `dotnet test`. See `csharp/README.md` for
  EF Core migrations and docker-compose.
- **Frontend:** `cd csharp/src/frontend && pnpm install`. Use **pnpm** (not npm/yarn);
  Husky + lint-staged run ESLint/Prettier on commit.
- **Requirements site:** `pip install -r tools/requirements-site/requirements.txt`, then
  `mkdocs serve -f tools/requirements-site/mkdocs.yml` (http://localhost:8000).
- **Windows symlinks:** enable Windows Developer Mode or another symlink privilege, and clone with
  Git symlink support enabled (`git config --global core.symlinks true`). This keeps
  `.claude/skills`, `.codex/skills`, and `.opencode/skills` as real symlinks to
  `.agents/skills`; with `core.symlinks=false`, Git materializes them as plain text files and
  Claude Code skill discovery breaks.

## Formatting & checks (run before pushing)

- C#: `dotnet format` (CI runs `dotnet format --verify-no-changes`).
- Frontend: `pnpm lint` / `pnpm typecheck`.
- Requirements site: `mkdocs build -f tools/requirements-site/mkdocs.yml --strict` must succeed.

## Working with agents

The repo-wide rules (for humans **and** AI assistants) live in [`AGENTS.md`](AGENTS.md) — that
is the single source of truth; update it first when conventions change. How the agent
configuration is wired across Claude Code, Codex, and OpenCode is documented in
[`docs/architecture/agent-config.md`](docs/architecture/agent-config.md); read it before moving
or adding any agent-config files. This file deliberately does **not** restate those rules.
