# Implementation-Slice Workflow & Roles

The end-to-end flow for delivering a new slice, who does what, and how to pick one. Authoritative
repo docs: `docs/architecture/implementation-flow.md` and
`docs/architecture/implementation-slice-workflow.md` — read them; this file is the quick map.

## Skills, in order (the pipeline)
1. **pick-implementation-slice** — start on `master`; select slice; write+push the claim to
   `openspec/track.md`; create Azure claim ticket; create branch + OpenSpec change (`openspec-propose`).
2. **generate-tdd-tests** — derive failing tests from acceptance criteria; implement smallest change; refactor.
3. **mock-implementation-slice** — AFTER implementation, BEFORE PR. Adds a local-only mock ONLY when
   all four hold: behavior is frontend-observable, blocked locally today (real dep missing), a faithful
   mock is feasible from existing types, real thing not yet implemented. Mocks live only in the `Mock`
   env (`ASPNETCORE_ENVIRONMENT=Mock`); never mark a requirement done. Most slices add no mock.
   **CRITICAL — this is NOT the Playwright proof mock.** The route-interception in [00](00-playwright-proof-howto.md)
   is for OFFLINE proof SCREENSHOTS only; it does NOT make the running Docker app usable for human
   testing. If a slice needs a real backend `Mock`-env adapter/seed so a human can click through the
   Docker stack, `mock-implementation-slice` STILL applies — do **BOTH** where needed. Never skip
   `mock-implementation-slice` because "it's already mocked for Playwright" — they are different mocks
   for different purposes and the memory must never cause one to be dropped.
3b. **Publish to the shared `test` branch (NEW mandatory step — see the dedicated section below).**
   AFTER implementation is verified and BEFORE `complete-implementation-slice` opens the PR the FIRST
   time, merge the feature branch into the long-lived `test` integration branch and push `origin/test`,
   so ALL open features / open PRs always live on ONE branch the testers test from. Re-run it after
   EVERY fix pushed to the feature branch during the testing loop. Master-owned git step; use
   [`tools/scripts/publish_to_test.sh`](tools/scripts/publish_to_test.sh) `feature/<branch>`.
4. **complete-implementation-slice** — at dev-close, after checks + manual validation + the `test`-branch
   publish (3b): writes `validation.md`, sets `track.md` → **in-review**, opens the PR with required
   reviewers (Tobias always + Yujiao when frontend) and **auto-complete armed** (PR still targets
   **master**, not `test`). Does NOT archive/verify/mark done.
5. **test-implementation-slice** — tester runs it on the open PR (finding-loop). No findings → architect
   finalizes in-PR (delta spec from final code, `openspec-verify-change` code↔spec gate, REQ Architecture),
   sets `testing-complete`, then freezes in-PR (`finalize.py <change> --no-push` → archive + sync specs → `done`).
Supporting skills: **legacy-sql-analysis**, **extract-data-contracts** / **link-data-contracts**,
**measure-amarillo-spacing** (spacing), **review-pr**, **sonarqube-run-fix**, the **openspec-*** skills.

## Publish to the shared `test` branch (mandatory step 3b — MASTER-owned, every slice)
Azure DevOps now carries a long-lived **`test`** integration branch that must always be the **union of
every currently-open feature branch / open PR**. Testers test from that ONE branch instead of checking
out each feature branch separately. This step COMPLEMENTS the repo skills — it does not replace any of
them; the PR still targets **master** and `complete-implementation-slice`/`test-implementation-slice`
run unchanged. **Every agent from now on MUST comply.**

**When to publish (two triggers):**
1. **First publish:** AFTER the slice is implemented + verified and BEFORE `complete-implementation-slice`
   opens the PR the first time. (So the code is on `test` the moment testing can start.)
2. **Re-publish on EVERY fix:** every time a UX/tester/reviewer fix is pushed to the feature branch
   during the testing loop, re-merge the feature branch into `test` and push — `test` must never lag the
   feature branch. A fix that isn't re-published to `test` = the tester tests stale code (a fix-flow miss).

**How (master-owned git mutation, like all git/Azure):** push the feature branch to origin FIRST, then
```
bash .memory/tools/scripts/publish_to_test.sh feature/<branch>
```
It fetches, checks out a local `test` tracking `origin/test`, `git merge --no-ff`s the feature tip
("Merge branch 'feature/X' into test"), pushes `origin/test`, and returns to your branch. On conflict it
STOPS mid-merge (leaves `test` for you to resolve): resolve **minimally** — union `openspec/track.md` /
i18n / openspec-ledger rows, and preserve BOTH features' behaviour for real code (safe-rebase
principles) — then `git add -A && git commit && git push origin test && git checkout <feature>`.

**Ground rules for `test`:**
- `test` is a **rebuildable DOWNSTREAM integration branch**. **NEVER** merge `test` back into `master`
  or into a feature branch, and never open a PR from `test`. PRs go feature → **master** as before.
- Merged/closed PRs may still linger on `test`; that's fine (it's the union of what's in flight). `test`
  can be force-rebuilt from the open branches at any time.
- Sync the feature branch (and, when relevant, master) FIRST (core rule) so you publish the current tip.

### Merge safety (no loss, no artefacts, tests green)
Publishing to `test` MERGES divergent feature branches, and **merges are dangerous**: a careless
resolution silently **loses functionality** or leaves **conflict artefacts / duplicates**. Because `test`
already holds several features, expect conflicts in the *aggregation* files (barrel `components/index.ts`,
`store/rootEpic.ts`/`rootReducer.ts`, i18n `de|en/common.json`, `openspec/track.md`) and in shared UI
that multiple features touch (e.g. the hit-list `columns.tsx`/`TrefferListe.tsx` row actions). Rules:
- **Union, don't overwrite.** For aggregation files keep BOTH sides' additions (both imports/exports,
  both reducer/epic entries, both i18n keys). For shared components, keep BOTH features' behaviour
  (all row actions, all props) — never drop one side to make the conflict go away.
- **Ledger (`track.md`): take the NEWER row per slice** (in-review/PR link beats a stale `claimed`) and
  keep every other slice's row. Never lose a row.
- **Ground non-trivial conflicts in the requirements.** When two features restructured the same code,
  read the `openspec/track.md` rows + the `REQ-*`/change behind BOTH commits so both survive (same
  principle as the **safe-rebase-on-master** skill). Don't guess a structural merge.
- **Watch for silent semantic divergence** (safe-rebase skill): a prop/signature you union in one file
  may break an *unconflicted* sibling (e.g. a `*.test.tsx` calling the changed factory) — the compiler
  catches these, so ALWAYS typecheck.
- **Gate every merge before committing:** [`tools/scripts/merge_check.sh`](tools/scripts/merge_check.sh)
  `feature/<branch>` (leftover conflict markers + changed-JSON validity + **lost-test scan**), THEN
  [`tools/scripts/verify.sh`](tools/scripts/verify.sh) `all` — the merged `test` branch must be **green**
  (frontend typecheck/lint/jest + backend build/unit tests), and the tests that existed on the branch
  must **still exist and still pass** (that's what proves nothing was lost). Only run the SLOW WSL/Docker
  integration tests ([03](03-local-setup-and-infra.md#wsl--docker-integration-tests-slow-on-demand-only))
  if the merge touched integration-tested backend paths or a pipeline IT step fails.
- **Write a merge log (forensic trail).** `publish_to_test.sh` auto-writes an event log to
  [`merge-logs/`](merge-logs/README.md) for every real merge (auto-merged + conflict file lists + shas;
  clean merges are auto-completed). On a **conflict** merge you MUST **append a `--- resolution ---`
  section** (one terse line per conflicted file: side taken / union / rationale) + the final pushed sha to
  that log **before finishing** — it's the only record of *why* a non-trivial conflict was resolved a
  certain way. When a merge later breaks something on `test`, READ the matching merge-log (+ `git show
  <mergesha>` / `git log --merges origin/test`) to see what/how before re-deriving.

## Division of labour: MASTER vs SPAWNED agent
**MASTER (me) does — never delegate these:**
- **Sync master FIRST** (core rule — [README](README.md#core-rule--sync-master-first-always-avoid-the-rebaselock-churn)): `git fetch && git checkout master && git pull --ff-only` before claiming/branching, and `git pull --rebase origin master` before every push. Master moves under you (concurrent claims) — a stale base = push rejection + `track.md` rebase conflict.
- Report slice status (claimed / done / in-review / in-progress / not-claimed) from `openspec/track.md` + requirement pages.
- **Pick** the slice, **claim on master** (track.md row + MkDocs claim metadata + `mkdocs build --strict`), create the **Azure claim ticket**, add its ID to track.md, **push master** (pull --rebase first), create the branch + OpenSpec change.
- All git/Azure/PR mutations, incl. **publishing the feature branch to the shared `test` branch** (step
  3b — before the first PR and after every fix; `publish_to_test.sh`) and running
  **complete-implementation-slice** AFTER the user's go-ahead.
- Playwright proof + Azure posting (or delegate screenshots to a spawned agent per the no-double-test rule in [01](01-proof-reporting-protocol.md)).

**SPAWNED implementation agent (fresh context) does:**
- **Read the memory first** (step zero — the task's [00–10] files + a grep-sweep of ALL `.memory/` for the topic), THEN read the repo (reading list below). Do not start research before the memory sweep.
- **SKIP the actual "picking / claiming" step** in `pick-implementation-slice` (master already claimed) but continue the rest of the flow: implement (TDD, tests from [10](10-testing-patterns.md)), keep delta spec current, add mocks if needed, write/keep tests + `tasks.md`.
- **Reuse, don't duplicate** (core rule): grep for an existing component ([09](09-frontend-patterns.md)) / entity / query / endpoint ([08](08-backend-patterns.md)) and extend it; follow the repo's Clean-Architecture boundaries + `docs/architecture/*` + nearest `AGENTS.md`. No parallel/duplicate implementations, no spaghetti; don't trade architecture for speed.
- **Surface limitations:** if a requirement/spec detail can't be fully met (e.g. an amarillo API limit), record it for the master's 4th PR comment — don't silently deviate.
- Allowed to **install tools** if needed. Allowed to **add/adjust this memory** (add a new file if none fits) — keep the same style/constraints so it never gets messy.
- Does NOT push/track.md/openspec-commit/PR (master does), and does NOT double-run the Playwright proof if master is doing it.

## Slice selection rules
- Size **1–3 requirements**. Bigger is fine (best case FE + BE + maybe a mock, cohesive) but **not too big** — must review as one PR.
- Must be **not yet claimed** — check `track.md` active statuses (claimed/in-progress/in-review/blocked/testing-blocked/testing-complete) and page `status: in-progress`.
- Must be **actually implementable**: independently testable, not mostly external/process work, no unresolved decisions, no hidden large dependency chain.
- **Check legacy SQL** (documented in the requirement pages; `legacy-sql-analysis`) AND **data contracts** (`docs/requirements/data-contracts/`) — see global memory `vvf-data-contracts` (read the `.md`, not the xlsx). Quick existence check: [`tools/scripts/find_datacontract.sh`](tools/scripts/find_datacontract.sh) `<keyword>`.
- **Excluded subsections** unless provably implementable now: **Printing** (`REQ-PRT-*` — external Label Center machine we don't have) and **Address Search / Fuzzy** (`REQ-FUZZY-*` — external). BUT: if a **data contract exists** for the piece (PERI, DB, etc.), it **is** implementable even if the external system isn't connected — build our side against the contract.
- **Backend is fair game, not just frontend.** Especially when a data contract is linked, or Kafka is involved and `PostAG.Events` lacks the topic/event: **Post owns the new Kafka topics/events**, so we define a provisional one (sibling pattern: configurable topic, `AutoRegisterSchemas=false`, PROVISIONAL header) until Post publishes the real Avro.

## Reading list the spawned agent MUST read (repo overview)
- **All AGENTS.md**: root `AGENTS.md`, `csharp/AGENTS.md`, `csharp/src/backend/AGENTS.md`,
  `csharp/src/frontend/AGENTS.md`, `docs/requirements/AGENTS.md`, `docs/requirements/data-contracts/AGENTS.md`,
  and the Mock ones: `csharp/src/backend/PostAG.Logistics.Mad.Infrastructure/Mock/AGENTS.md` (+ `Mock/Kcrm`, `Mock/Peri`, `Mock/SiteService`).
- **Flow docs**: `docs/architecture/implementation-flow.md`, `implementation-slice-workflow.md`,
  `dev-workflow.md`, `agent-config.md`, and every doc they reference (e.g. `tracking.md`,
  `requirements-site.md`). Plus `docs/development-workflow.md` / `development-workflow-vertical.md`.
- **Design/tech**: `docs/architecture/vvf-technical-guidelines.md`, `amarillo-spacing-tokens.md`,
  `csharp-source-architecture.md`.
- **Requirements model**: `docs/requirements/` — `requirements/`, `features/`, `products/`, `epics/`,
  `data-contracts/`, `data-sources/`, `decisions/`, `test_cases/`, `requirement-map.md`,
  `source-traceability.md`. The requirement pages carry DB necessities, legacy SQL, and data-contract links.

## track.md ledger (do not break)
Exactly **11 pipe columns**, fixed order:
`| Feature | Requirements | Change | Owner | Branch | Azure Work Item | Status | Claimed | Completed | PR | Notes |`
Parsed by position by `finalize.py` and `select_next_slice.py`. Notes = one-line qualifier + relative link.

### Claim metadata — implementation state lives ONLY in track.md (hook-enforced)
When claiming, do NOT put implementation state on the **requirement** page: a requirements-site hook
aborts `mkdocs --strict` with *"`status: in-progress` is an implementation state / `owner` lives in
openspec/track.md — use draft/approved + owner: TBD here."* So on claim:
- **Requirement page:** keep `status: draft` (or `approved`) and `owner: TBD` (do NOT set in-progress /
  a real owner / an `in-progress` tag). A `change_history` provenance line noting the claim is fine.
- **track.md row:** carries the real Owner + Status (claimed/in-progress/...). This is the lock.
- **Feature page:** set `implementation_owner`, `implementation_claim`, `status: in-progress`, `in-progress`
  tag (features ARE allowed these; the hook only guards requirement pages).
Always run `tools/scripts/mkdocs.sh build` before committing/pushing the claim. (This corrects the older
workflow-doc wording that said to set status/owner on the requirement page.)

## Dependency on another in-flight requirement — READ-ONLY inspect (change nothing)
If the slice's requirement needs / connects to another requirement that isn't done yet, **check
`openspec/track.md`** for it: is there a claim / branch / PR? If a branch exists, you MAY check it out
to understand how it works and connects — so your implementation doesn't conflict, break it, or
duplicate it — but you **must change NOTHING** there. Flow:
1. Ensure your own branch is clean (commit/stash first — normally there's nothing yet).
2. `checkout_branch.sh feature/<dependency-branch>` (it aborts if you have tracked changes).
3. Read it thoroughly: how it's built, the contracts/types/endpoints it exposes, how the two connect.
   Take mental notes of everything relevant (names, shapes, DI, events).
4. `checkout_branch.sh feature/<your-branch>` (return).
5. Continue on your branch **with those findings in mind** — reuse its contracts, avoid double
   implementation, keep it compatible. Never edit the dependency branch. If the dependency is a hard
   blocker (nothing usable yet), record it in the claim notes and pick/continue differently.

## Continuing a slice (the THIRD flow: "continue on <slice/ticket>")
A slice was already picked + claimed (track.md row `claimed`/`in-progress`, branch + OpenSpec change
exist) but implementation is unfinished. This is NOT a new pick (don't re-claim) and NOT a UX/tester fix
(no open-PR finding). Master steps:
1. **Locate the slice:** find its `openspec/track.md` row (branch, change name, Azure id, status) — from
   the ticket id, the REQ id, or the Owner. If ambiguous, `az_workitem.py <ticket>` + grep track.md.
2. **Check out the branch** (`checkout_branch.sh feature/<branch>`; `repo_status.sh` for a quick state
   read) and read where it stands: the change's `tasks.md` (done vs open), `proposal.md`/`design.md`, the
   delta spec (artifact format: `openspec_example.sh <artifact>`), the requirement page(s), and the
   current code + tests. If the PR is already open, read its findings with `az_pr.py <prid>`. Summarise
   what's implemented vs remaining.
3. **Spawn a fresh agent to CONTINUE** — give it the 07 template plus: the change path, the remaining
   `tasks.md` items, and "resume implementation (do NOT re-pick/claim/openspec-propose; the slice exists),
   keep tasks.md + delta spec current, TDD the remaining ACs, verify-only". Same no-git / no-proof split.
4. **Then** the normal tail: master proof (if frontend-observable) → critical review note-by-note →
   go-ahead → **publish to `test`** (3b) → `complete-implementation-slice` (opens the PR if not open yet).
   If the PR is already open, it's effectively the fix/testing stage — push the continuation commits,
   **re-publish to `test`** (`publish_to_test.sh`), and post a new-slice proof comment.
Resuming an incomplete *claim* (Azure id `TBD`, missing branch/OpenSpec) is handled by
`pick-implementation-slice` step 2.1 — let it finish the claim, then continue as above.

**Partial-claim variant seen in practice (audit-log-and-logdaten-view, #2180):** the track.md row +
branch + Azure id all existed and looked fully claimed, but the **OpenSpec change dir was never
created** (`openspec/changes/<name>/` absent; `git log --all -- 'openspec/changes/<name>/*'` empty).
The "continue" flow then has to **author the missing OpenSpec artifacts first** (proposal / design /
tasks / delta specs under `specs/<capability>/spec.md`, `.openspec.yaml`) from the ticket + requirement
pages before implementing — mirror a recent change's structure (e.g. `dev-c-gating` for the delta-spec
`## ADDED Requirements` + `#### Scenario` shape). Don't re-claim (row/ticket/branch already exist); just
fill the gap, then TDD the work. Check for this at step 2 of the continue flow (`ls openspec/changes/<name>/`).

## The go-ahead handshake
After the slice is implemented, mocked (if needed), and the master has produced + verified Playwright
proof, the master reports the requirement→screenshot list and waits for the user's **"go-ahead"**. Then
the master **publishes the feature branch to the shared `test` branch** (step 3b — `publish_to_test.sh`,
before the PR exists) and runs `complete-implementation-slice` (track.md → in-review, PR with Tobias +
Yujiao, auto-complete armed) and posts the PR comments **in order** (see [01](01-proof-reporting-protocol.md)):
(1) proof screenshots → all reviewers, (2) `--annotate` UX-overlay → Yujiao only (table/layout),
(3) test-guide → all reviewers, and (4) **only if a requirement couldn't be fully met / is blocked** a
limitations comment → all reviewers. A fully-met frontend slice posts 3 comments (no 4th).

## Every fix-flow finding feeds the memory (core rule — any source)
When ANY finding is handled (fixed OR rebutted) — Yujiao/UX, Tobias/tester, a reviewer, or one the agent
caught — bank the learning, because it was wrong there: a UX/layout/spacing/cut-off pitfall →
[02](02-ux-design-checklist.md) (+ its CLOSED LOOP: extend the overlay); a frontend/backend prod-code
gotcha → [09](09-frontend-patterns.md)/[08](08-backend-patterns.md); a test gap → [10](10-testing-patterns.md);
infra → [03](03-local-setup-and-infra.md). See the [README core rule](README.md#core-rule--every-fix-flow-finding-becomes-a-learning-ux-tester-or-any-source).
The fix-flow comment rules (frontend fix = proof + overlay; non-UI tester fix = tester-response comment,
no screenshots) are in [01](01-proof-reporting-protocol.md). **After pushing any fix to the feature
branch, always re-publish it to the shared `test` branch** (step 3b, `publish_to_test.sh`) so the tester
never tests stale code — a fix left off `test` is itself a fix-flow miss.
