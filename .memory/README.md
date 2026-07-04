# Local Agent Memory — INDEX (local-only, never committed)

> Location: `Post/.memory/`. Ignored via `.git/info/exclude` so it persists across branch
> checkouts and is never pushed. **This is the source of truth for HOW we work in this repo.**
> Every agent (master + spawned) MUST, **before starting any research or implementation**, (1) read the
> relevant memory file(s) for the task from the index below, and (2) do a keyword **grep-sweep across ALL
> of `.memory/`** for the topic (`Grep pattern="<kw>" path=".memory"`) so no existing recipe/gotcha is
> missed — THEN act, and keep the memory updated. Reading memory first is not optional; it is step zero.

## When in doubt, read these (grouped):

| File | Use it when… |
|---|---|
| [00-playwright-proof-howto.md](00-playwright-proof-howto.md) | Taking ANY frontend proof screenshot. Contains the ONE working recipe + all mock contracts. **Read this before touching Playwright.** |
| [01-proof-reporting-protocol.md](01-proof-reporting-protocol.md) | Posting proof to Azure DevOps (work-item status, PR comment, tagging, cleanup, new-slice PR proof). |
| [02-ux-design-checklist.md](02-ux-design-checklist.md) | Reviewing screenshots critically for UX/design defects before posting. |
| [03-local-setup-and-infra.md](03-local-setup-and-infra.md) | Building/running locally: dev server, backend, Docker/Typesense, disk/WSL pitfalls. |
| [04-accounts-and-azure-metadata.md](04-accounts-and-azure-metadata.md) | Azure IDs (repo, PR, identity GUIDs), accounts, PAT usage. |
| [05-slice-workflow.md](05-slice-workflow.md) | Delivering a new slice: skill order, master↔spawned-agent roles, slice-selection rules, repo reading list, the go-ahead handshake, and **step 3b — publishing the feature branch to the shared `test` integration branch** (before the first PR + after every fix). |
| [06-azure-devops-templates.md](06-azure-devops-templates.md) | Copy-paste Azure REST templates: create ticket (description/AC/tags layout), set state, create PR + reviewers + auto-complete, attach image, PR comment + @mention, proof-comment + "finding is wrong" templates. |
| [07-kickoff-and-triggers.md](07-kickoff-and-triggers.md) | How the master starts fast from a one-line trigger ("pick a slice from X" / "fix work item Y"), incl. the canonical spawned-agent prompt template. |
| [08-backend-patterns.md](08-backend-patterns.md) | Adding a .NET vertical slice: the aggregate→config→migration→port→repo→handler→endpoint→DI recipe, the exact `dotnet ef` command (startup=Infrastructure), actor/request-context resolution, the `ErrorOr<T>` FakeItEasy dummy gotcha, the `DirectivePaymentStatus` open set, the DirectiveOrder join fields, the Mock-only seed hook, and reuse-before-adding. Read before backend work. |
| [09-frontend-patterns.md](09-frontend-patterns.md) | Adding a frontend feature: REUSE existing components (never re-implement), VERIFY the amarillo API before use, the read-only list-screen vertical slice (service→model→store→component→page→i18n), the amarillo `DataTable` no-`onRowClick` + custom-action-cell-loses-onClick → use `rowActions` gotcha, `Typography` has no `h6`, no `Alert` export. Read before frontend work (with [02](02-ux-design-checklist.md)). |
| [10-testing-patterns.md](10-testing-patterns.md) | Writing tests (backend xUnit + frontend Jest/RTL): run ONE test fast (`verify.sh --jest`/`--filter`), the EF-InMemory DbContext harness + unit-vs-CI-integration split, the RTL `test-utils` harness, the jsdom `ResizeObserver` stub, the fetch-on-mount async-settle determinism rule, and the lint-misses-test-files trap. Read before writing tests. |
| `PATS/` | Local-only PAT store: `AZURE-PAT.json` (master, Azure REST) + `NUGET-PAT.json` (build agents). **Reference by PATH only — NEVER read/open/cat/print/echo/load the contents** (see PAT core rule below). The scripts load them internally: `PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json)` into a var, never to stdout. |
| [tools/README.md](tools/README.md) | **Authoritative script/testdata index** (check here before writing your own). Categories: *orientation* (`repo_status.sh`, `backend_info.sh`, `az_workitem.py`), *Azure* (`post_to_pr.py`, `set_workitem_state.py`), *proof* (`proof_shots.py` + `testdata/mocks.json`), *verify* (`verify.sh`), *git* (`checkout_branch.sh`, `publish_to_test.sh`, `merge_check.sh`), *reference* (`openspec_example.sh`), *cleanup/infra* (`cleanup_proof.sh`, `disk_cleanup.sh`, `wsl_compact_vhdx.ps1`). Add new *reusable* ones there (never one-off/per-PR scripts). |
| [merge-logs/README.md](merge-logs/README.md) | **Forensic event log per `test`-branch merge** (auto-written by `publish_to_test.sh`: auto-merged + conflict file lists + shas; agent appends the per-conflict resolution rationale on conflict merges). Read the matching log when a merge later breaks something on `test`. Persistent (not wiped by `cleanup_proof.sh`); see [05 Merge safety](05-slice-workflow.md). |

## Finding things fast (how to search — do THIS before re-deriving)
**Running memory tools (READ THIS — env does NOT persist across tool calls).** Each shell tool call is a
FRESH process with a frozen inherited env; PATH/`$env` changes (session_env, even a persistent User-PATH
edit) do NOT carry to the next call or to spawned agents. `git`/`jq`/`pnpm`/`dotnet` ARE on the inherited
PATH; **`bash` is NOT** (Git's `bin` dir isn't on it). So there is **no "run once"** — invoke tools robustly
**every** time:
- **bash script:** `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/X.sh` (full path — always works).
- **python script:** `.venv/Scripts/python.exe .memory/tools/scripts/X.py` (run from repo root — no PATH needed).
- Only if you want bare `bash`/`tsc`/`mkdocs` names inside ONE multi-command call, prepend
  `. .\.memory\tools\scripts\session_env.ps1 | Out-Null;` at the start of that same call (`-WithSecrets`
  also loads PATs — see [03 Session setup](03-local-setup-and-infra.md#session-setup-path--secrets)).
- **Avoid inline Python/complex quoting in a PowerShell tool call** (PowerShell mangles `$(...)`, quotes,
  `[]`): write the snippet to `.memory/temp/*.py|*.sh` and run it by full path instead.
- **The shell tool intermittently SWALLOWS stdout** on multi-command `&&`/`;` chains, pipes, and `grep`
  (you see `(no output)` or a truncated read). Do NOT read that as failure — a `git commit` can succeed
  while printing nothing. Read state reliably by redirecting to a file and `Read`ing it
  (`git status --porcelain > .memory/temp/s.txt`; `git log --oneline -3 > .memory/temp/l.txt`), run ONE
  simple command, or use the `Grep`/`Read`/`Glob` tools instead of `bash grep/ls/cat`. Always re-confirm
  a git mutation via a file-captured `git log`/`status` rather than trusting the inline output.

**Orient before hand-rolling anything:**
1. **See every tool you have** — `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/lookup_memory_tools.sh`
   prints ALL memory tools + one-line descriptions (from the [tools index](tools/README.md)). Reach for an
   existing tool instead of re-deriving; if the one you need is MISSING, ADD it (reusable+parametrised).
2. **Jump to the right code fast** — `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/code_map.sh <area>`
   (`frontend`, `backend-api`/`-application`/`-domain`/`-infra`/`-migrations`, `tests`).

Lookup order, cheapest first: **(1) this memory → (2) the repo → (3) ask the user** only if still blocked.

**Search the memory** (small now, will grow — always start at the index table above, then grep):
- Pick the file by topic from the table, open it, skim its `##` headers (every file is grouped by `##` sections — keep it that way).
- Keyword sweep across all memory: `Grep pattern="<kw>" path=".memory"` (tool) or `grep -rin "<kw>" .memory/`.
- List sections of a file fast: `grep -n "^#" .memory/<file>.md`.
- **Topic → file quick map:** screenshots/Playwright/mocks/toasts/create-mask → `00`; PR comments / work-item status / proof reporting / "finding is wrong" → `01` + templates in `06`; UX defects (gaps, sizes, cut-offs, table/alignment) + directive-type facts → `02`; dev server / backend build / Docker / Typesense / disk-WSL → `03`; PATs / repo & PR ids / identity GUIDs → `04`; slice flows (new / fix / **continue**) / skill order / roles / selection rules / reading list / **publish to shared `test` branch (step 3b)** → `05`; raw Azure REST templates → `06`; triggers ("pick" / "fix" / "continue") + spawn-agent template → `07`; backend vertical-slice recipe / EF migration cmd / ErrorOr-FakeItEasy gotcha / payment-status open set / Mock-only seed → `08`; frontend REUSE-components / amarillo API limits / list-screen slice / DataTable row-click + rowActions / Typography no-h6 → `09`; writing tests (EF-InMemory harness / RTL harness / ResizeObserver stub / async-settle / run one test fast) → `10`; runnable scripts + testdata → `tools/`.

**Search the repo** (authoritative source of truth — memory only distills it):
- Code/symbols: `Grep` tool (ripgrep) e.g. `Grep pattern="titlePrefix" glob="*.tsx"`; find files: `Glob pattern="**/*personendaten*"`.
- Nearest guidance: read the closest `AGENTS.md` up the tree from the file you're editing; area overviews in `docs/architecture/` and requirement truth in `docs/requirements/` (`requirements/`, `features/`, `data-contracts/`, `requirement-map.md`).
- Claim/lock state: `openspec/track.md`. History/answers: `git log --oneline -- <path>`, `git grep "<kw>" <ref>`, `git log -S"<string>"` (who added a string).
- Don't Read whole large files — Grep to the line, then Read a window around it (saves tokens).

**Keep it findable (every agent):** when you add a learning, put it in the right file under a clear
`##`/`###` header, use words future agents will grep for, and if it's a new file add a row to the
index table above. Never dump content into this README — one index line only. Consistent structure =
fast grep = fewer tokens next time.

## CORE PRINCIPLE — COMPLEMENT the repo's skills/flows, never OVERRIDE them
The repository's skills and workflows (`pick-` / `mock-` / `test-` / `complete-implementation-slice`,
`generate-tdd-tests`, `openspec-*`, `sonarqube-run-fix`, the `implementation-slice-workflow`) are the
**source of truth for HOW work flows**. This memory exists ONLY to make running those flows **faster,
cheaper, and less error-prone** — distilled recipes, exact facts, reusable scripts. It must never
replace, bypass, or contradict a skill. If a memory entry ever conflicts with a repo skill/flow, the
**skill wins** — fix the memory (self-heal). Scripts here are conveniences that call the repo's own
canonical commands (e.g. `verify.sh` runs `pnpm typecheck/lint/test` + `dotnet`); they are not new pipelines.

## CORE PRINCIPLE — the memory is LOCAL-ONLY; never leak it into the repo
NEVER mention or reference `.memory/`, its scripts, "local memory", or anything under it in ANY file
that gets committed/pushed to the repo — code, comments, commit messages, PR descriptions, PR/work-item
comments, `openspec/*`, `docs/*`, `tasks.md`, `validation.md`, `track.md`, or test files. The memory is
a private local accelerator; the repo must read as if only the repo's own skills/flows produced the work.
When committing, cite the repo's skills/docs, never the memory. (Audit: `git grep -n "\.memory/"` on a
branch must return nothing but false positives — it did for #2180.) This is WHY we complement the repo
skills instead of overriding them: the repo has to stand on its own.

## CORE RULE — promoting a learning into the REPO's own docs (RARE; huge, universal learnings only)
Default: a learning lives in `.memory/`. **Keeping it local is almost always right.** VERY rarely a
learning is big enough that it belongs in the repo's OWN durable docs — a nearest `AGENTS.md`, a skill's
`SKILL.md`, `docs/architecture/*`, or `docs/requirements/*` — where every agent AND human contributor
sees it. The agent MAY make that repo edit, but the bar is HIGH and this must NOT become clutter (it is
NOT the common case).

**Promote ONLY when ALL five hold** (else keep it local): (1) **huge/foundational** — a standing rule
that changes how work is done, not a tip; (2) **universal** — every contributor needs it, not just our
local flow; (3) **durable** — a stable convention, not a transient recipe/fact that will rot; (4)
**genuinely missing** from the repo (grep the AGENTS.md tree + skills + `docs/` first — often it's already
there); (5) **not local-flow-specific** — Playwright proof recipes, PATs, the shared-`test` branch /
`merge-logs`, PR-comment/overlay protocol, `proof_shots.py`, disk/WSL tricks **stay LOCAL** (they are ours,
not the repo's). When in doubt → keep local. Most learnings NEVER graduate.

**Where (match the existing structure — never restructure):**
- Cross-cutting dev/coding/testing/doc rule → the **most-specific `AGENTS.md`** for the concern
  (`csharp/src/backend/AGENTS.md` or `.../frontend/AGENTS.md` for a layer rule; `csharp/AGENTS.md` for
  csharp-wide; root `AGENTS.md` only for truly repo-wide). A requirements convention → `docs/requirements/AGENTS.md`.
- A change to how a **skill flows** → that skill's `.agents/skills/<skill>/SKILL.md`.
- Architecture / workflow decision → `docs/architecture/*` (e.g. `implementation-slice-workflow.md`, `agent-config.md`).
- Read the target first; add under its EXISTING `##`/section conventions, in its exact terse style; additive only.

**How (repo hygiene — non-negotiable):** (a) **NEVER reference `.memory/`, local tools, PATs, or "local
memory"** in the committed edit (the LOCAL-ONLY rule above) — write it as if the repo produced it, citing
the repo's own skills/docs. (b) Follow the repo's doc rules (e.g. a requirement/feature page edit needs
`change_history` entries; `mkdocs build --strict` must still pass). (c) It's a **repo change → treat like
code**: small, reviewable, and committed **only when the user asks** (AGENTS "don't commit unless asked").
(d) It must FIT the repo's flow, not fork/override it (same spirit as COMPLEMENT above). (e) After
promoting, leave a **one-line pointer** in the relevant memory file noting it graduated to `<repo path>` —
but the repo side must stand alone. If it doesn't clearly meet the five-part bar, it is clutter — keep it local.

## CORE PRINCIPLE — every agent USES both the tools AND the skills (efficiency is the point)
Master AND spawned agents are COMPELLED to (a) use the repo's **skills/flows** (the source of truth —
this matters most) and (b) use this memory's **tools/recipes** to run them faster, then (c) **heal/extend**
the memory. The grand goal: each run cheaper (time+tokens) AND higher quality/accuracy in **backend and
frontend** (especially UX pitfalls — see §1 above). Reaching for a memory tool/recipe before hand-rolling,
and banking every learning, is mandatory — that is how we compound.

## CORE RULE — sync master FIRST, always (avoid the rebase/lock churn)
Before you claim, branch, commit-to-push, or open a PR, **fetch/pull master first** so you build on the
current tip. Master moves under you — other agents land claims (`openspec/track.md`), and a stale base
causes push rejections + `track.md` rebase conflicts (it bit us twice). Concretely:
- **Before claiming a slice / creating the branch:** `git fetch origin && git checkout master && git pull --ff-only`
  (or `git pull --rebase`), THEN cut the feature branch.
- **Before pushing the claim / any master change:** `git pull --rebase origin master` first.
- **Before opening the PR:** ensure the branch is rebased on / merges cleanly with current master.
[`tools/scripts/checkout_branch.sh`](tools/scripts/checkout_branch.sh) already fetches + ff-only on checkout;
use it. This is a ground rule — never skip the pre-sync.

## CORE RULE — PAT files are reference-only; NEVER read, print, or load their contents
The `PATS/*.json` files hold live secret tokens. Agents may reference them **by path** in a command
(exactly as the scripts do — `$(jq -r .pat .memory/PATS/AZURE-PAT.json)` piped into a variable/env that a
tool consumes) but must **NEVER**: `Read`/`cat`/open the file to see the token, echo/print/log it, put it
in a comment/commit/PR/console, or paste it into any message. You do not need to — and must not — know the
actual token value; treat it as opaque. If a token value ever appears in ANY output (console, error,
screenshot, file), **sanitize/redact it immediately** (replace with `***`) and do not propagate that
output. This is an absolute ground rule for master AND every spawned agent.

## CORE PRINCIPLE — no double implementation; clean architecture; follow the repo's own guidelines
We want ONE clean implementation, in backend AND frontend — never a parallel/duplicate one. Before adding
code, **grep for what already exists and extend it** (a component, an entity, a query, an endpoint, a
service). The repo already carries **enough architecture documentation, guidelines and constraints** —
follow them: Clean Architecture / DDD / CQRS layer boundaries on the backend, the component/model/epic
conventions on the frontend, `docs/architecture/*`, and the nearest `AGENTS.md`. No spaghetti, no
duplicated logic, clean separation of concerns. Do NOT trade architecture quality for speed ("given time"
shortcuts): the memory makes us fast so we DON'T have to cut corners — a clean slice passes review once
instead of looping. Frontend specifics: [09 REUSE existing components](09-frontend-patterns.md); backend
specifics: [08 vertical-slice recipe intro](08-backend-patterns.md).

## CORE RULE — EVERY fix-flow finding becomes a learning (UX, tester, or any source)
If something had to be **fixed in the fix flow, it was wrong in the first place** — so it MUST be banked
as a learning so it never recurs. This applies to **every** finding, no matter the source: Yujiao/UX,
Tobias/tester, a reviewer comment, or a defect the master/agent caught. When you fix a finding, record the
**root cause + the fix + how to avoid it next time** in the right file (grep first; extend, don't
duplicate):
- UX / spacing / margins / gaps / cut-off / alignment → [02](02-ux-design-checklist.md) — AND run the
  full CLOSED LOOP there (record → extend the `--annotate` overlay → re-prove in the overlay comment).
- Frontend code/behaviour gotcha → [09](09-frontend-patterns.md); backend → [08](08-backend-patterns.md).
- Test gap (a case we should have covered) → [10](10-testing-patterns.md).
- Local setup / infra / build / Docker → [03](03-local-setup-and-infra.md).
- Process / reporting / Azure flow → the relevant flow file ([01](01-proof-reporting-protocol.md)/[05](05-slice-workflow.md)/[07](07-kickoff-and-triggers.md)).
A fix that leaves no learning is an incomplete fix. If a finding turns out to be **wrong** (rebutted), bank
that too (why it was not-a-bug) so the same objection isn't re-litigated. This is the whole point of the
memory: we stop re-fixing the same class of thing.

## THE PRIME DIRECTIVE — time & token optimization (read this first)
Every agent — master AND every fresh-context spawned agent — MUST (1) **reason from this memory
instead of re-deriving**, and (2) **write back every new learning/gotcha/"aha" immediately**. This
is the whole point: each implementation or fix should cost **less time and fewer tokens** and land at
**higher quality** than the last, because the traps are already written down. Consulting memory is
never optional; contributing to it is never optional. If you spent time figuring something out, the
next agent must not have to — record it, categorized/indexed/grouped, in the right file.

## Rules for maintaining this memory (MANDATORY for every agent)
- **Reason WITH this memory** — consult the relevant file before acting; when in doubt, read it.
  Playwright is the LAST test, so the UX checklist ([02](02-ux-design-checklist.md)) is crucial:
  most defects we hit repeat (gaps, sizes, overlaps/cut-offs, table/field/background alignment).
- **Contribute back** — the moment you have a finding or an "aha" (a tester/UX fix, an infra
  gotcha, a working recipe), ADD it to the right file. Spawned agents ARE allowed to edit these
  files and add a NEW file if none fits — but keep the exact style/structure so it never gets messy.
- **Self-heal — fix what's wrong.** If you find anything in this memory that is incorrect, stale, or a
  command/recipe that no longer works, you SHOULD **fix it in place** — replace it with the verified
  working version (and note what changed, briefly). Do not leave a known-broken entry or work around it
  silently; a wrong memory is worse than none. This should rarely be needed — but when it is, correcting
  it is mandatory, not optional.
- **Record every command / script / test data you used.** If you ran a command, wrote a Python/bash
  script, or built mock/test data to get the job done, capture it: a one-off note goes in the relevant
  `.md` (what it does + how to run + why); anything reusable goes in `tools/scripts/` or
  `tools/testdata/` (parametrised) with an index row in [tools/README.md](tools/README.md). The next
  agent must not have to re-derive it.
- **Cross-link scripts at point of use.** A script that serves a specific topic MUST also be linked in
  that topic's file — e.g. `ef_migration.sh` linked in `08`'s migration section, `mkdocs.sh` in `03`'s
  site-build section, `find_route.sh`/`post_to_pr.py` in `01`. When you ADD a topic-related script, add
  the link in its topic file in the SAME edit (not only in `tools/README`), so an agent reading that
  section finds the tool without hunting.
- **Style: plain Markdown, NO emoji.** The memory is emoji-free — do not add emoji or decorative
  pictographs of any kind. Use `##`/`###` headers, tables, and code fences; keep the same terse,
  scannable style in every file. (Typographic arrows like `->` in prose are fine; pictographic emoji are not.)
- **No duplication, no mess (anti-corruption).** Before adding, grep to see if it already exists —
  extend the existing entry instead of duplicating. Keep every entry under a clear `##`/`###` header,
  described well enough to act on cold. This memory must never rot into contradictions or clutter — if
  it starts to, clean it (the `consolidate-memory` skill does a reflective merge/prune pass).

## Post-spawn check (MASTER runs this every time a spawned agent finishes)
Before moving on, the master MUST verify the spawned agent left the memory correct and complete:
1. **Did it record its learnings?** Any command it ran, script it wrote, test data it built, or gotcha
   it hit → must be in the right `.md` and/or `tools/`. If the agent forgot, the master adds it now.
2. **Well-formed?** New entries are correctly placed, indexed (index row added for new files/tools),
   categorized, grouped, deduped, and clearly described — not dumped in the wrong file or the README body.
3. **Self-healed?** If the agent discovered an existing entry was wrong, it must have been fixed in place.
Fix any gaps immediately — this check is what keeps the memory compounding instead of decaying.

## Verify note-by-note (no slip-ups)
Go through tickets / slices / work items **requirement by requirement, note by note** and verify EVERY
stated detail is actually met before declaring done. If a ticket says "16px gap", a specific label, a
field order, a status, an exact value — check each one against the running UI/tests. One missed detail =
a full extra round-trip (UX/tester re-tests → flags → re-fix → re-verify → re-test). Slow is smooth,
smooth is fast: the note-by-note pass is cheaper than the loop.

## Master operating playbook (why runs are fast now)
This is the distilled "how" a fresh master should operate so a new session works from just
*"pick a slice from <list>"* or *"fix <ticket>"* (see [07](07-kickoff-and-triggers.md) for the triggers):
1. **Read memory first, act from it** — the recipes here (Playwright route-interception, exact mock
   contracts, Azure templates, slice flow) mean you rarely need to rediscover anything.
2. **Fetch the ticket + its children + inline/attached screenshots** ([06](06-azure-devops-templates.md)); pin the exact target + PR + requirement.
3. **Spawn a fresh agent** for implementation (give it the [07](07-kickoff-and-triggers.md) template — read memory, skip picking, verify-only, no git/post). For a state-heavy proof, let the same agent do fix+proof and pass shots back (no double-testing).
4. **Master owns git + Azure + the critical review**: verify the diff, review the 3 proof shots hard
   (UX checklist [02](02-ux-design-checklist.md) + note-by-note), fix+re-proof anything a reviewer would flag, then commit/push, post ([01](01-proof-reporting-protocol.md)/tools), set the work item Done, clean up.
5. **Run the post-spawn check** (above), then report + await go-ahead.
The speed comes from not re-deriving and not shipping half-right screens — both are memory-enforced.
- Every UX decision/finding we had to fix MUST be saved, categorized, indexed, and grouped so the
  frontend gets better over time and we stop re-fixing the same things.
- Keep it tight, structured, and agent-actionable (commands, exact values, not prose).
- Never store raw secret tokens here (PATs are provided per-session by the user).
- The master agent MUST tell every spawned agent this memory exists and which file(s) to read.

## Live task tracking
Keep a TODO for the current work (via the task tools) so neither master nor spawned agents
lose track. Mirror big multi-step efforts here if the task list is cleared.
