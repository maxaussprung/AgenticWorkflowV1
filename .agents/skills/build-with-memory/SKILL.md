---
name: build-with-memory
description: Wrap any task in the agent-memory discipline — read the .memory/ instructions and relevant topic files BEFORE acting, reuse its recipes and tools while working, and contribute every new learning, gotcha, and reusable script back to the memory afterwards. Use when starting any implementation, fix, or research task in this repo, or when the user says "build with memory".
metadata:
  author: {project}
  version: "1.0"
---

# Build with Memory

Execute a task **with the local agent memory in the loop**: consult `.memory/` first, work from
its recipes and tools, and bank every learning back into it. The memory's own rulebook is
[`.memory/README.md`](../../../.memory/README.md) — this skill operationalizes it as an explicit,
checkable workflow. If this skill and `.memory/README.md` ever disagree, the README wins
(self-heal this skill).

## Input

The skill input is **the task to perform** (e.g. "add pagination to the orders list",
"fix ticket 1234", "investigate the flaky login test"). Everything after the skill name is the
task description.

**If no task is provided:** ask the user what to build/fix/investigate — do not invent one.

## Phase 0 — Read the memory (step zero, never skipped)

1. Read [`.memory/README.md`](../../../.memory/README.md) completely — the index table and the
   core principles/rules.
2. From the index table, open every topic file relevant to the task and skim its `##` headers,
   then read the matching sections.
3. **Grep-sweep the whole memory** for the task's keywords so no recipe/gotcha in an unexpected
   file is missed: `grep -rin "<keyword>" .memory/` (2–4 keywords: domain terms, error text,
   tool names).
4. Read [`.memory/tools/README.md`](../../../.memory/tools/README.md) and note which existing
   scripts/test data apply — reuse before writing your own.
5. Note in one or two lines what the memory already gives you (recipes, facts, gotchas to avoid)
   and what is genuinely new territory.

Lookup order for anything still unknown, cheapest first:
**(1) the memory → (2) the repo** (nearest `AGENTS.md`, `docs/architecture/`,
`docs/requirements/`, git history) → **(3) ask the user** only if still blocked.

## Phase 1 — Do the task, memory-first

- Follow the repo's own skills/flows for the work itself (OpenSpec, slice workflow, …). The
  memory **complements** them — it never replaces, bypasses, or overrides a repo skill. On
  conflict the skill wins; fix the memory entry.
- Reach for an existing `.memory/tools/` script before hand-rolling a command. If the tool you
  need is missing **and reusable**, add it (parametrised) instead of writing a one-off.
- Throwaway scripts, logs, and screenshots go in `.memory/temp/` (or the session scratchpad),
  never in the repo tree; delete them when done.
- Never read, print, or commit secret values — reference credential files by path only.
- While working, keep a running note of every learning: a command that needed non-obvious flags,
  an error and its root cause, a fact you had to dig for, a memory entry that turned out wrong.

## Phase 2 — Contribute back (the task is not done until this is)

Work through this checklist explicitly:

1. **Bank every learning.** Each recipe/gotcha/fact from Phase 1 goes into the right topic file
   under a clear `##`/`###` header, in the memory's terse, grep-friendly style. **Grep first —
   extend an existing entry rather than duplicating it.**
2. **New topic needed?** Copy [`.memory/00-topic-template.md`](../../../.memory/00-topic-template.md)
   to `NN-<topic>.md`, fill it, and add an index row to `.memory/README.md`'s table. Never leave
   a new file unindexed; never create an empty file "for later".
3. **Promote reusable scripts.** Anything parametrised and reusable moves to
   `.memory/tools/scripts/` with (a) a what/why/how header comment, (b) an index row in
   `.memory/tools/README.md`, and (c) a link from the topic file it serves — all in the same
   edit. One-off scripts are deleted, not promoted.
4. **Self-heal.** Any memory entry you found stale, wrong, or broken is fixed **in place** (with
   a brief note of what changed) — never worked around silently.
5. **Hygiene check.** No secrets or real personal data, no emoji, no content dumped into
   `.memory/README.md` beyond index rows, cross-links intact in both directions.

A fix that leaves no learning is an incomplete fix. If a finding was rebutted (not actually a
bug), bank that too so it isn't re-litigated.

## Report

End with a short summary in chat:

- **Task outcome** — what was built/fixed/found, and how it was verified.
- **Memory read** — which files/sections informed the work.
- **Memory contributed** — each entry added/updated/fixed (file + header), new tools promoted,
  or an explicit "no new learnings" with one line of justification (rare — most tasks teach
  something).
