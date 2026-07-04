# Merge logs — forensic event trail for `test`-branch merges (local-only)

Every real merge into the shared **`test`** integration branch (step 3b, `publish_to_test.sh`) writes ONE
terse event-log file here. **Purpose:** when something later breaks on `test`, trace *which* merge
introduced it and *how* each conflict was resolved — the reasoning `git` can't show. Local-only
(git-ignored, under `.memory/`), never pushed. Not wiped by `cleanup_proof.sh` (that only clears
`.memory/temp/`); this is a persistent ledger.

Keep entries **terse** — a forensic ledger, not a narrative. Git already holds the factual *what* (the
merge commit + its diff + `git log --merges`); these logs add only the file lists at a glance and the
per-conflict **resolution rationale**.

## Filename (flat, index-first — matches the `00-…` memory convention)
`<NNN>-<from-branch>-into-test-<YYYYMMDD-HHMMSS>.log`
- `<NNN>` — zero-padded running index (auto-computed = existing `*.log` count + 1).
- branch `/` and spaces are sanitized to `-` (`feature/dtrf-prefill-from-existing` → `feature-dtrf-prefill-from-existing`).
- timestamp orders them; the base / feature-tip / result **shas live in the log body**.
(Flat on purpose: one file per merge — a folder-per-merge holding a single file is clutter.)

## When it's written / completed
- **Auto-written** by `publish_to_test.sh` on every non-trivial merge (a "nothing to merge" no-op writes none).
- **Clean merge:** fully auto-completed (auto-merged list + `CLEAN` + `RESULT: pushed <sha>`). No manual step.
- **Conflict merge:** the script writes the skeleton (auto-merged + conflict file lists, `result: PENDING`)
  and prints its path. The AGENT then, after resolving + verifying, **appends** a `--- resolution ---`
  section (one line per conflicted file: which side / union / rationale) and the final pushed sha —
  **before finishing the merge** (see [../05-slice-workflow.md](../05-slice-workflow.md) "Merge safety").
- **Manual merges / rebase-conflict resolutions** (rare, e.g. via `safe-rebase-on-master`): write a log
  here by hand in the same format.

## Format
```
MERGE 007  feature/offene-inkassofaelle-view -> test
when:   2026-07-03T16:20:41+0200
base:   538010d5   tip(feature/...): d8b7a98f   result: 36a29499
--- auto-merged ---
  csharp/src/frontend/src/translations/de/common.json
  ...
--- conflicts ---
  csharp/src/frontend/src/components/directiveOrderDetail/DirectiveOrderDetail.tsx
  openspec/track.md
--- resolution ---            (agent-appended on conflict merges)
  DirectiveOrderDetail.tsx  -> took test's shared `statusLabel` guard (identical fix, cleaner); my inline guard dropped
  openspec/track.md         -> kept branch row (testing-blocked) + kept HEAD's FEAT-056 eez row (union)
--- status ---
  CONFLICTS resolved; verify.sh frontend green (870/870); RESULT: pushed 36a29499
```

## Using it when a merge breaks something (forensics)
1. `git log --merges origin/test` → find the merge; match it to the log here by index / timestamp / sha.
2. Read the `--- conflicts ---` + `--- resolution ---` lines to see how it was resolved, then `git show <mergesha>`.
3. If a resolution was wrong, fix forward and append a short correction note to that log.
