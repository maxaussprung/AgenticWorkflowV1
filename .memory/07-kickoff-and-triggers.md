# Kickoff & Triggers — how the master starts a run FAST

Goal: the user gives a one-line trigger; the master runs the whole flow from memory without being
re-told the standing rules. **Read the relevant memory files, don't re-derive.** Every run should be
faster + cheaper than the last (see README time/token mandate).

## Trigger → what the master does
- **"pick a new slice from <list/file>"** → NEW-SLICE flow:
  1. Report which listed reqs are claimed/done/in-review/in-progress vs not-claimed (from `openspec/track.md` + requirement pages).
  2. Pick per [05](05-slice-workflow.md) rules (1–3 reqs, unclaimed, implementable, legacy-SQL + data-contract check, Print/Address-Search excluded unless a data contract makes them buildable, backend/Kafka fair game).
  3. **Sync master first** (`git fetch && checkout master && pull --ff-only` — core rule, avoids the rebase/lock churn), THEN **master claims**: track.md row + MkDocs claim metadata + `mkdocs build --strict` → `pull --rebase` → commit+push master → create Azure claim ticket ([06](06-azure-devops-templates.md) §1) → add ID to track.md → push → create branch + OpenSpec (`openspec-propose`).
  4. Spawn the implementation agent with the template below (it SKIPS picking/claiming, continues the flow).
  5. Master proof (Playwright, [00](00-playwright-proof-howto.md)) → critical UX review ([02](02-ux-design-checklist.md)) → fix+re-proof if needed.
  6. Report requirement→screenshot list, wait for **go-ahead**, then **publish the feature branch to the shared `test` branch** (step 3b, `bash .memory/tools/scripts/publish_to_test.sh feature/<branch>` — before the PR exists; see [05](05-slice-workflow.md)) and run `complete-implementation-slice` (opens PR **targeting master**, reviewers Tobias always + Yujiao if frontend, auto-complete) and post the PR comments **in order** ([01](01-proof-reporting-protocol.md)): (1) proof → all, (2) `--annotate` overlay → Yujiao only, (3) test-guide → all, (4) **only if a requirement couldn't be fully met / is blocked** limitations → all ([06](06-azure-devops-templates.md) §6/§8/§9).
- **"fix <work item / slice>"** (UX/tester follow-up on an existing open PR) → FIX flow:
  1. Fetch the ticket + children + PR + screenshots in one go: `az_workitem.py <id> --download <dir>`
     (add `--comments` for discussion); read the PR's findings/reviewer-votes with `az_pr.py <prid>`.
     Identify the target + its PR + the requirement.
  2. **Verify note-by-note the finding is actually right** ([02](02-ux-design-checklist.md)); if it's wrong,
     rebut instead of implementing ([06](06-azure-devops-templates.md) §7, via `post_to_pr.py`) + set Done.
  3. Spawn an implementation agent (scoped fix, SKIP picking; not a new slice → no claim/openspec/new-PR).
  4. Master proof → critical review (if a NEW defect surfaces, run the fix-flow before posting).
  5. After pushing the fix to the feature branch, **re-publish it to the shared `test` branch** (`bash .memory/tools/scripts/publish_to_test.sh feature/<branch>` — so the tester never tests stale code; see [05](05-slice-workflow.md) step 3b). Then post to the slice's PR (`post_to_pr.py`), **@tag** the originator, set the work item **Done**, clean up. Comment depends on the fix ([01](01-proof-reporting-protocol.md)): **frontend/UX fix → proof comment + (spacing/cut-off/table/layout) `--annotate` overlay comment** re-proving the exact measure is now fixed; **non-UI tester fix → tester-response comment** (how each finding was fixed, no screenshots, [06](06-azure-devops-templates.md) §10). **Bank the learning for EVERY finding, any source** (core rule): UX/spacing/cut-off→02 (+ CLOSED LOOP overlay), code→08/09, test→10, infra→03.
- **"continue on <slice / ticket / REQ>"** → CONTINUE flow (see [05](05-slice-workflow.md) "Continuing a slice"):
  1. Locate the slice in `openspec/track.md` (branch, change, Azure id) from the ticket/REQ/owner.
  2. `checkout_branch.sh feature/<branch>`; read `tasks.md` + design + code to see done-vs-remaining.
  3. Spawn a fresh agent to **resume** implementation (07 template + remaining tasks; do NOT re-pick/claim/propose).
  4. Master proof (if frontend) → note-by-note review → go-ahead → **publish to `test`** (3b, `publish_to_test.sh`) → `complete-implementation-slice` (or, if the PR is already open, push + **re-publish to `test`** + proof-comment).

## Standing facts to inject (so you never wait to be told)
PATs in `.memory/PATS/` (master uses AZURE, spawned build agents use NUGET — load, never print).
Account `jonas.hauser@accenture.com`. Reviewers: Tobias (tester) always, Yujiao (UX) when frontend.
No double-testing. 3 screenshots (1280×1024 / 1920×1680 / whole-page@1920), full page, mock
everything, zero toasts. Playwright = route interception, NO MSW ([00](00-playwright-proof-howto.md)).

## Canonical spawned-agent prompt TEMPLATE (fill the ⟨…⟩, paste)
> Task: ⟨implement REQ-XXX-000 …⟩ | ⟨fix UX work item #NNNN …⟩. Branch `feature/⟨…⟩` is checked out.
>
> **Read memory FIRST — step zero (reason WITH memory, don't re-derive):** read `.memory/README.md`
> then the files it points to for this task — especially `00-playwright-proof-howto.md`,
> `02-ux-design-checklist.md`, `03-local-setup-and-infra.md`, `05-slice-workflow.md`,
> `08-backend-patterns.md`/`09-frontend-patterns.md` (whichever the task touches), `10-testing-patterns.md`
> (before writing ANY test), and `tools/` (reusable `proof_shots.py`/`post_to_pr.py`/`verify.sh` +
> `testdata/mocks.json` — use them, don't rebuild boilerplate). Also **grep-sweep ALL of `.memory/`** for
> the topic (`Grep pattern="<kw>" path=".memory"`) before starting research, so no recipe/gotcha is missed.
> Before that, **orient**: `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/lookup_memory_tools.sh`
> (see EVERY tool you have — use them, don't hand-roll; add a missing one) and `… code_map.sh <area>`
> (jump to the right code). NOTE — env does NOT persist across tool calls (frozen inherited env); `bash`
> is NOT on PATH though `git`/`jq`/`pnpm`/`dotnet` are. So call bash tools by **full path**
> `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/X.sh` and python via
> `.venv/Scripts/python.exe …X.py` (there is no "run session_env once"; see [03 Session setup](03-local-setup-and-infra.md#session-setup-path--secrets)).
> That `.memory/` is our local-only memory (git-ignored, survives checkouts). **You MAY and MUST add to it**
> the moment you hit a finding/gotcha/"aha", run a notable command, write a script, or build test data
> (keep the exact style, NO emoji; reusable code → `tools/`, add an index row + cross-link at point of use;
> add a new file only if none fits; self-heal any entry you find wrong). This is how we get faster each run.
>
> **Repo overview:** read all AGENTS.md (root, csharp, csharp/src/backend, csharp/src/frontend,
> docs/requirements, docs/requirements/data-contracts, the Mock/* ones), `docs/architecture/
> implementation-flow.md` + `implementation-slice-workflow.md` + files they reference, and the
> relevant skills (pick/mock/test/complete-implementation-slice, generate-tdd-tests). You may install tools.
>
> **Flow:** SKIP the actual pick/claim step in `pick-implementation-slice` (the master already
> claimed) but continue the normal flow — implement TDD (tests per `10-testing-patterns.md`), keep the
> delta spec current, add local mocks only if the four-part gate holds (`mock-implementation-slice`), keep
> tasks.md + tests current. Legacy SQL + data contracts are supporting context. Post owns new Kafka
> topics/events (provisional pattern) — backend is fair game.
>
> **REUSE, don't duplicate (core rule):** before adding UI/code, grep for an existing component
> (`09`) / entity / query / endpoint / service (`08`) and EXTEND it — no parallel/duplicate implementation,
> no spaghetti. Follow the repo's Clean-Architecture boundaries + `docs/architecture/*` + nearest
> `AGENTS.md`; don't trade architecture for speed. **Never read/print/load the PAT files** — reference by
> path only. If a requirement/spec detail can't be fully met (e.g. an amarillo API limit), record it and
> tell the master (it becomes the 4th PR comment) — do NOT silently deviate.
>
> **Do NOT:** run git push / commit the openspec / open the PR / touch track.md / run Playwright proof
> / post to Azure — the MASTER does all of those (no double-work). Verify locally with
> `bash .memory/tools/scripts/verify.sh frontend|backend|all [--jest <pat>] [--filter <expr>]` (canonical
> pnpm/dotnet checks, NuGet PAT auto-loaded); use `next lint --file <changed>` for fast per-file iteration.
>
> **Report:** files changed + why, verification results, any limitation you had to surface, and exactly
> what you added to memory (which `.md`/`tools/` entries, incl. any command/script/testdata + self-heals). Stop there.

## Master's own checklist each run
**Orient:** `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/lookup_memory_tools.sh` (see every
tool) + `… code_map.sh <area>` for the area you'll touch. Call bash tools by **full path** (env doesn't
persist per call — [README "Finding things fast"](README.md#finding-things-fast-how-to-search--do-this-before-re-deriving)). ▸
Consult memory (read first + grep-sweep) ▸ **sync master** ▸ (new slice) pick+claim+ticket+branch+openspec ▸
spawn agent ▸ verify agent's diff ▸ Playwright proof (3 sizes, reuse `tools/scripts/proof_shots.py` +
`tools/testdata/mocks.json`) ▸ **critically review** vs [02](02-ux-design-checklist.md) **note-by-note**
(every stated detail, e.g. an exact "16px" gap) ▸ fix+re-proof if needed ▸ **run the Post-spawn check**
(README: agent recorded its commands/scripts/testdata + self-heals, well-structured; fill gaps) ▸ report +
await go-ahead ▸ (on go-ahead) **publish feature branch → shared `test` branch** (`publish_to_test.sh`, before the PR; re-publish after every later fix) ▸ `complete-implementation-slice` + post comments in order (proof→all,
overlay→Yujiao, test-guide→all, **limitations→all only if a req couldn't be fully met**) ▸ set work items
(reuse `tools/scripts/post_to_pr.py`) ▸ **watch the PR CI pipeline to GREEN** ▸ cleanup. Keep a TaskCreate
todo so nothing is lost.

**Triage "did MY change break the pipeline?" before fixing (don't misattribute).** When told a pipeline
is red "since your commit": (1) `git show --stat <sha>` — a **track.md/ledger-only** commit (or any
non-code doc change) cannot break build/test/Playwright pipelines; (2) check the pipeline's **history**
with `az_build.py` — if it was already red on earlier, unrelated commits, the break **predates** you
(it's chronic, not yours); (3) distinguish **PR-validation** builds (gate the merge: e.g. `Post C# BE` /
`Post React FE` on `refs/pull/<id>/merge`) from **scheduled** suites (e.g. `Nigthly AI UI Tests`) that run
on `master` against a **deployed test env** — a scheduled deployed-env suite failing (missing lookup
elements, KCRM/session data, `<element(s) not found>`) is usually env/test-data/deploy drift, owned by
whoever maintains that env, NOT a code regression from a ledger commit. Only THEN decide what (if anything)
to fix. (Seen 2026-07-02: `6d3bb106` was track.md-only yet blamed for a nightly that had been red 4+ days.)

**After opening the PR, verify CI goes green — a red pipeline is a fix-flow finding.** Check it with
[`tools/scripts/az_build.py`](tools/scripts/az_build.py) `<pr-id>` (the DevOps PAT now has Build-Read).
The backend **integration tests run ONLY in CI** (no Docker locally, so `verify.sh` can't catch them) —
the most likely late failure. `az_build.py --tests` tries to name the failing tests; if the test API 401s,
read the failed step's **log** (`build/builds/<id>/timeline` → the failed record's `log.url`). Fix, push,
and **bank the learning** ([10](10-testing-patterns.md)
for a test gotcha; e.g. the shared-non-reset-DB per-type-count trap). Don't consider a slice done on a red
pipeline. This is why integration tests that persist shared-DB rows must follow [10](10-testing-patterns.md)'s
non-perturbation rule up front.
