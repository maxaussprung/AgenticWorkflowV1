# .memory/tools — reusable scripts & test data (use these before writing your own)

Executable helpers + canonical test data so agents don't rebuild boilerplate. **Check here first**;
if what you need is missing and reusable, **add it** (keep this index current, same style).

## scripts/

| File | What / when | How |
|---|---|---|
| [scripts/example_tool.sh](scripts/example_tool.sh) | Placeholder — copy as the starting point for your own tools, then replace this row. | `bash .memory/tools/scripts/example_tool.sh` |

## testdata/

| File | What |
|---|---|
| _none yet_ | Canonical, synthetic test payloads consumed by scripts. Keep script ↔ testdata ↔ topic-doc links in sync. |

## Rules

- **Reuse before rewriting.** If a script/testdata here fits, use it — don't hand-roll.
- **REUSABLE ONLY — never keep one-off/specific scripts.** A script belongs here only if it is
  **parametrised** (CONFIG block / args) and reliably reusable across cases. A script hardcoded to
  a single case must NOT be added; run it from `temp/` (or the scratchpad) and delete it. If you
  find yourself about to add a specific script, generalise it into an existing tool instead.
- **Add + document.** New reusable script/testdata → add it here with a one-line index row + a
  header comment in the file saying what/why/how.
- **Keep scripts ↔ docs in SYNC (link both ways).** A script serving a topic is also linked in
  that topic's `.md`; if you change a command/flow in a script, update the linked doc in the SAME
  edit (and vice-versa). Drift here is corruption — self-heal it on sight.
- **Self-heal.** If a script errors or a payload is stale, FIX it here (don't work around it silently).
- **Skill-owned actions stay scripts-free.** If a repo skill owns an action, do NOT add a
  competing script here — scripts are conveniences that call the repo's own canonical commands,
  never new pipelines.
- **`../temp/` is the throwaway workspace.** Scratch scripts, logs, and screenshots go there, not
  in the repo tree, and get deleted when done.
- **Never** put secrets or real personal data here — test data is synthetic only.
