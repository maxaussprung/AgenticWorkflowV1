# Claude Code Guidance

The canonical, tool-agnostic guidance for this repository is in `AGENTS.md`. Read it first:

@AGENTS.md

## Claude-specific notes

- Claude Code auto-loads the nearest `CLAUDE.md` up the directory tree. Each area with an
  `AGENTS.md` has a one-line `CLAUDE.md` that imports it, so the same guidance Codex and
  OpenCode read from `AGENTS.md` reaches Claude too:
  `csharp/src/backend/`, `csharp/src/frontend/`, `legacy-sql/`,
  `.agents/subagents/requirements-site/`.
- **Subagents** (the requirements-site roles) live in `.claude/agents/`; their tool-neutral
  specs are `.agents/subagents/requirements-site/agent_<role>.md`.
- **Skills** live in `.agents/skills/` (tool-neutral; Codex/OpenCode read it natively).
  `.claude/skills` is a symlink to it so Claude Code discovers the same skills.
- **Slash commands** in `.claude/commands/` are adapters only. Their canonical workflows live in
  `.agents/skills/`.
- The legacy codebase source under `to_be_migrated_repo/` is a **read-only secondary reference**;
  never edit it. CI (`azure-pipelines-guardrails.yml`) rejects PRs that modify it.
