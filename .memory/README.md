# Agent Memory — INDEX

> **This is the source of truth for HOW we work in this repo.** Every agent (master + spawned)
> MUST, **before starting any research or implementation**, (1) read the relevant memory file(s)
> for the task from the index below, and (2) do a keyword **grep-sweep across ALL of `.memory/`**
> for the topic (`grep -rin "<kw>" .memory/`) so no existing recipe/gotcha is missed — THEN act,
> and keep the memory updated. Reading memory first is not optional; it is step zero.

## How this memory works

- **Topic files** (`NN-<topic>.md`) hold distilled, agent-actionable knowledge: working recipes,
  exact commands, gotchas with their fixes, project facts. One topic per file, grouped under
  `##`/`###` headers so it stays greppable.
- **This README is the index only.** One row per topic file in the table below — never dump
  content here.
- **`tools/`** holds reusable, parametrised scripts + test data (see [tools/README.md](tools/README.md)).
- **`temp/`** is the throwaway workspace for scratch scripts, logs, and screenshots — never create
  throwaway files in the repo tree.
- The memory **compounds**: each run should cost less time and fewer tokens than the last because
  the traps are already written down.

## Index

| File | Use it when… |
|---|---|
| [00-topic-template.md](00-topic-template.md) | Placeholder/template — copy it to start a new topic file, then add an index row here. |

<!-- Add one row per topic file. Suggested topics as they come up:
     local setup & infra, project workflow, external accounts & metadata,
     backend patterns, frontend patterns, testing patterns, review checklists,
     reporting/communication templates. Create files only when you have real
     content for them — empty files are clutter. -->

## Finding things fast (do THIS before re-deriving)

Lookup order, cheapest first: **(1) this memory → (2) the repo → (3) ask the user** only if still blocked.

- Pick the file by topic from the index table, open it, skim its `##` headers.
- Keyword sweep across all memory: `grep -rin "<kw>" .memory/`.
- List sections of a file fast: `grep -n "^#" .memory/<file>.md`.
- Check [tools/README.md](tools/README.md) for an existing script before writing your own.
- The repo itself is the authoritative source of truth — memory only distills it. Nearest
  guidance: the closest `AGENTS.md` up the tree from the file you're editing, plus
  `docs/architecture/` and `docs/requirements/`.

## CORE PRINCIPLE — COMPLEMENT the repo's skills/flows, never OVERRIDE them

The repository's skills and workflows are the **source of truth for HOW work flows**. This memory
exists ONLY to make running those flows **faster, cheaper, and less error-prone** — distilled
recipes, exact facts, reusable scripts. It must never replace, bypass, or contradict a skill. If a
memory entry ever conflicts with a repo skill/flow, the **skill wins** — fix the memory (self-heal).

## CORE RULE — secrets are reference-only; NEVER read, print, or commit their contents

Credential files (tokens, PATs, API keys) live outside the memory or in a git-ignored location,
and agents may reference them **by path only** — piped straight into a variable/env that a tool
consumes, never printed, logged, committed, or pasted into any message. If a secret value ever
appears in ANY output, sanitize/redact it immediately and do not propagate that output.

## CORE RULE — EVERY fix becomes a learning

If something had to be fixed, it was wrong in the first place — so it MUST be banked as a learning
so it never recurs, whatever the source (reviewer, tester, user, or a defect the agent caught
itself). Record the **root cause + the fix + how to avoid it next time** in the right topic file
(grep first; extend, don't duplicate). If a finding turns out to be **wrong** (rebutted), bank that
too, so the same objection isn't re-litigated. A fix that leaves no learning is an incomplete fix.

## THE PRIME DIRECTIVE — time & token optimization

Every agent — master AND every fresh-context spawned agent — MUST (1) **reason from this memory
instead of re-deriving**, and (2) **write back every new learning/gotcha/"aha" immediately**.
Consulting memory is never optional; contributing to it is never optional. If you spent time
figuring something out, the next agent must not have to.

## Rules for maintaining this memory (MANDATORY for every agent)

- **Reason WITH this memory** — consult the relevant file before acting; when in doubt, read it.
- **Contribute back** — the moment you have a finding or an "aha", ADD it to the right file.
  Spawned agents ARE allowed to edit these files and add a NEW file if none fits — but keep the
  exact style/structure so it never gets messy.
- **Self-heal — fix what's wrong.** If anything in this memory is incorrect, stale, or a
  command/recipe no longer works, **fix it in place** (and note what changed, briefly). A wrong
  memory is worse than none.
- **Record every command / script / test data you used.** A one-off note goes in the relevant
  `.md` (what it does + how to run + why); anything reusable goes in `tools/` (parametrised) with
  an index row in [tools/README.md](tools/README.md).
- **Cross-link scripts at point of use.** A script serving a specific topic MUST also be linked in
  that topic's file, in the SAME edit — so an agent reading that section finds the tool without hunting.
- **Style: plain Markdown, NO emoji.** Use `##`/`###` headers, tables, and code fences; keep the
  same terse, scannable style in every file.
- **No duplication, no mess.** Before adding, grep to see if it already exists — extend the
  existing entry instead of duplicating. Keep every entry under a clear header, described well
  enough to act on cold.
- **Never store raw secret tokens or real personal data here.**

## Post-spawn check (MASTER runs this every time a spawned agent finishes)

1. **Did it record its learnings?** Any command it ran, script it wrote, or gotcha it hit → must
   be in the right `.md` and/or `tools/`. If the agent forgot, the master adds it now.
2. **Well-formed?** New entries correctly placed, indexed, categorized, deduped — not dumped in
   the wrong file or this README.
3. **Self-healed?** If the agent discovered an existing entry was wrong, it must have been fixed
   in place.

## Verify note-by-note (no slip-ups)

Go through tickets / tasks **requirement by requirement, note by note** and verify EVERY stated
detail is actually met before declaring done. One missed detail = a full extra round-trip. Slow is
smooth, smooth is fast: the note-by-note pass is cheaper than the loop.
