# Agent configuration

How AI coding assistants are wired in this repo, not what they build. This is the reference for
anyone — human or agent — adding or moving rules, skills, or subagents. Target tools:
**Claude Code, Codex CLI, OpenCode**.

## Principle

**One canonical source per fact, plus the thinnest possible per-tool glue.** Only two things are
cross-tool standards — `AGENTS.md` (project rules) and `SKILL.md` (skills). Everything else
(where each tool looks, how slash commands are exposed, and how subagents are defined) differs per
tool, so some glue is unavoidable. We keep that glue tiny, standard, and self-documenting rather
than maintaining tool-specific source copies.

There is **no single folder all three tools read**. The table below is the whole model.

## What each tool reads

| Artifact | Canonical source (write once) | Codex CLI | OpenCode | Claude Code |
|---|---|---|---|---|
| **Rules** | `AGENTS.md` (root + nested) | reads `AGENTS.md` natively (walks dir tree) | reads `AGENTS.md` natively | reads `CLAUDE.md` → one-line `CLAUDE.md` (`@AGENTS.md`) sits beside each `AGENTS.md` |
| **Skills** | `.agents/skills/<name>/SKILL.md` | scans `.agents/skills/` natively; `.codex/skills` is a compatibility symlink | scans `.agents/skills/` natively; `.opencode/skills` is a compatibility symlink | reads `.claude/skills/` → it is a **symlink** to `.agents/skills` |
| **Subagents** | `.agents/subagents/requirements-site/agent_<role>.md` (tool-neutral role spec) | reaches the role via the spec referenced from `AGENTS.md` | same as Codex | discovers only in `.claude/agents/` → a thin wrapper per role points back to `agent_<role>.md` |
| **Slash commands** | `.agents/skills/openspec-*/SKILL.md` | no repo command adapter | `.opencode/command/opsx-*.md` thin adapters | `.claude/commands/opsx/*.md` thin adapters |

**Where duplication exists:** only at adapter layers, because the tools have incompatible
subagent and command-discovery systems. The role *content* lives once in `agent_<role>.md`; the
`.claude/agents/<role>.md` wrapper points back to it. OpenSpec command workflows live once as
skills under `.agents/skills/openspec-*`; Claude/OpenCode command files are wrappers that tell the
tool to read the corresponding skill. Rules, skills, role specs, and command workflows are never
duplicated — they are reached via an import shim (`@AGENTS.md`), a symlink, or a thin adapter.

## File map

```
AGENTS.md                                   canonical rules (root)        ── Codex/OpenCode native
CLAUDE.md                                   @AGENTS.md + Claude notes      ── Claude
csharp/src/backend/AGENTS.md   (+ CLAUDE.md shim)                          backend rules
csharp/src/frontend/AGENTS.md  (+ CLAUDE.md shim)                          frontend rules
.agents/subagents/requirements-site/
    AGENTS.md                  (+ CLAUDE.md shim)                          requirements-site role hub
    agent_<role>.md            canonical, tool-neutral role specs (source of truth)
    copilot/                   Copilot prompt variants (Copilot is not a target tool today)
.claude/agents/<role>.md       Claude subagent wrappers → reference agent_<role>.md
.agents/skills/<name>/SKILL.md canonical skills                            ── Codex/OpenCode native
.claude/skills -> ../.agents/skills   symlink so Claude finds the skills
.codex/skills -> ../.agents/skills    compatibility symlink; no skill copies
.opencode/skills -> ../.agents/skills compatibility symlink; no skill copies
.claude/commands/opsx/*.md            Claude command adapters -> .agents/skills/openspec-*
.opencode/command/opsx-*.md           OpenCode command adapters -> .agents/skills/openspec-*
to_be_migrated_repo/           frozen, read-only legacy reference (see below)
azure-pipelines-guardrails.yml CI guard protecting to_be_migrated_repo/ source
```

## Symlink portability

The three tool-facing skills entries are tracked as Git symlinks:
`.claude/skills`, `.codex/skills`, and `.opencode/skills` all point to `../.agents/skills`.
This keeps skill content canonical under `.agents/skills/`.

On Windows checkouts, Git only materializes those entries as real symlinks when Windows symlink
privileges are available and `core.symlinks=true` is set before checkout. With
`core.symlinks=false`, Git writes plain text files containing `../.agents/skills` instead. Codex
and OpenCode still have their native `.agents/skills/` scan path, but Claude Code depends on
`.claude/skills` resolving as a symlink for default skill discovery.

`azure-pipelines-guardrails.yml` checks that all three entries remain symlinks targeting
`../.agents/skills`, so accidental replacement with copied directories or plain files fails in CI.

## How to extend it

- **Add/adjust an area rule:** edit (or create) that area's `AGENTS.md`. If it is a new area,
  also drop a one-line `CLAUDE.md` next to it containing `@AGENTS.md` so Claude cascades it.
  Keep nested files **delta-only** — don't restate the root rules.
- **Add a skill:** create `.agents/skills/<name>/SKILL.md` (YAML frontmatter `name` +
  `description`, then instructions). All three tools pick it up — Codex/OpenCode natively or
  through compatibility symlinks, Claude through the `.claude/skills` symlink. Nothing else to
  wire.
- **Add a subagent role:** write the canonical spec as
  `.agents/subagents/requirements-site/agent_<role>.md`, then add a thin Claude wrapper at
  `.claude/agents/<role>.md` (frontmatter `name`/`description`/`tools`/`model`) that tells the
  agent to read the canonical spec. Codex/OpenCode reach it via the role hub `AGENTS.md`.
- **Add a slash command:** put the canonical workflow in a skill when it can be reused across
  tools. Add only tool-specific command adapters, such as `.claude/commands/opsx/<name>.md` and
  `.opencode/command/opsx-<name>.md`, that tell the tool to read the canonical skill.

## Legacy codebase reference

`to_be_migrated_repo/` is the **frozen, read-only** legacy source — a *secondary* reference for
behaviour parity. Primary requirements come from customer documents and project tickets, curated in
`docs/requirements/`. It must never be edited; `azure-pipelines-guardrails.yml` is a
tool-agnostic CI gate that rejects any PR touching `to_be_migrated_repo/` source (with a
carve-out so the directory's own `README.md`/`AGENTS.md`/`CLAUDE.md` can be updated). The actual
source import is a future task.

## Why this shape

The discovery paths above are each tool's documented defaults where possible (Codex/OpenCode scan
`.agents/skills/` and read `AGENTS.md`; Claude reads `CLAUDE.md`, `.claude/agents/`,
`.claude/skills/`). Compatibility symlinks and command adapters exist only where a tool still
expects a tool-specific path. Tools *can* be pointed at custom paths via config (OpenCode
`instructions` globs, Codex `[[skills.config]]`, Claude `CLAUDE.md` `@import`), but using thin
default-path adapters keeps canonical content in `.agents` and avoids per-tool source copies.
