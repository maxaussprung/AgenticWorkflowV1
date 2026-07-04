# .memory/tools — reusable scripts & test data (use these before writing your own)

Executable helpers + canonical test data so agents don't rebuild boilerplate. **Check here first**;
if what you need is missing and reusable, **add it** (keep this index current, same style).

## scripts/
| File | What / when | How |
|---|---|---|
| [scripts/az_workitem.py](scripts/az_workitem.py) | Inspect a work item/ticket: state/type/creator + children (with state) + PR links + Description/AcceptanceCriteria + inline/attached image URLs. `--comments` prints ticket discussion; `--download <dir>` pulls images. First thing to run for any fix/continue, before old child-task screenshots. | `python .memory/tools/scripts/az_workitem.py <id> [--comments] [--download <dir>]` (PAT auto-loaded from PATS). |
| [scripts/az_workitem.py](scripts/az_workitem.py) — **`--comments`** | now also prints the work-item discussion comments with `--comments`. | `python .memory/tools/scripts/az_workitem.py <id> [--comments] [--download <dir>]` |
| [scripts/az_pr.py](scripts/az_pr.py) | Inspect a PR: status + reviewer **votes** (flags *WAITING FOR AUTHOR* / *REJECTED*) + all comment threads (author/status/first line). `--active` = unresolved only. Read tester/UX findings fast. | `python .memory/tools/scripts/az_pr.py <pr-id> [--active]` |
| [scripts/az_build.py](scripts/az_build.py) | **Pipeline reader** — a PR's/branch's latest CI build result (the "watch CI to green" step, [07](../07-kickoff-and-triggers.md)). Resolves a PR id to its `refs/pull/<id>/merge` build. Needs the DevOps PAT **Build (Read)** scope ([04](../04-accounts-and-azure-metadata.md)). **`--logs`** tails the failed timeline steps' logs (the reliable "why it failed"); `--tests` best-effort lists failing tests (test API may 401). If the failing step is **integration tests**, reproduce locally with `integration_stack.sh` ([03](../03-local-setup-and-infra.md#wsl--docker-integration-tests-slow-on-demand-only)). | `DEVOPS_PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json) python .memory/tools/scripts/az_build.py <pr-id\|branch> [--logs] [--tests]` |
| [scripts/set_workitem_state.py](scripts/set_workitem_state.py) | Set a work item's State, optionally its children too. | `python .memory/tools/scripts/set_workitem_state.py <id> <state> [--with-children]` |
| [scripts/link_pr_workitem.py](scripts/link_pr_workitem.py) | Link an existing PR to a work item (ArtifactLink) — for fix/continue flows or when a PR was opened without the ref. `complete-implementation-slice` normally does this at PR creation. | `DEVOPS_PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json) python .memory/tools/scripts/link_pr_workitem.py <pr-id> <workitem-id>` |
| [scripts/find_datacontract.sh](scripts/find_datacontract.sh) | Slice-selection aid: does a data contract for `<keyword>` exist (data-contracts / source-import)? READ-ONLY. | `bash .memory/tools/scripts/find_datacontract.sh <keyword>` |
| [scripts/ef_migration.sh](scripts/ef_migration.sh) | `dotnet ef` with the VERIFIED flags (startup+project=Infrastructure, `--context DirectivesDbContext`, output-dir) — encodes the 08 trap; NuGet PAT auto-loaded. | `bash .memory/tools/scripts/ef_migration.sh add <Name>\|list\|script\|remove` |
| [scripts/mkdocs.sh](scripts/mkdocs.sh) | Requirements-site `--strict` build via the VERIFIED Windows `.venv/Scripts/mkdocs.exe` path (03 trap). Run after editing `docs/requirements/**`. | `bash .memory/tools/scripts/mkdocs.sh [build\|serve]` |
| [scripts/session_env.ps1](scripts/session_env.ps1) | **Session setup** ([03](../03-local-setup-and-infra.md#session-setup-path--secrets)): put every tool on `PATH` — Git bash (bash/grep/jq/sed/awk), `.venv` (python/mkdocs), frontend `node_modules\.bin` (tsc/jest/next/eslint), Node+npm-global (pnpm), dotnet, memory scripts. `-WithSecrets` also loads PATs+user into `$env` (DEVOPS_PAT / NUGET_POSTAT_* / PAT) **without printing them**. `wsl.exe` is already on PATH; Docker lives inside WSL. | Dot-source: `. .\.memory\tools\scripts\session_env.ps1 [-WithSecrets]` |
| [scripts/lookup_memory_tools.sh](scripts/lookup_memory_tools.sh) | **MANDATORY orientation** ([README](../README.md#finding-things-fast-how-to-search--do-this-before-re-deriving)): prints EVERY memory tool + one-line description (rendered from THIS index) so you reach for an existing tool instead of hand-rolling — and spot a MISSING one to add. | `bash .memory/tools/scripts/lookup_memory_tools.sh` |
| [scripts/code_map.sh](scripts/code_map.sh) | Fast "where does code live + which conventions" navigator per area (`frontend`, `backend-api`/`-application`/`-domain`/`-infra`/`-migrations`, `tests`) — canonical dirs + nearest AGENTS.md + memory recipe. Complements `find_route.sh`/`backend_info.sh`. | `bash .memory/tools/scripts/code_map.sh <area>` |
| [scripts/merge_check.sh](scripts/merge_check.sh) | **Merge-safety gate** ([05](../05-slice-workflow.md#merge-safety-no-loss-no-artefacts-tests-green)): scans for leftover conflict markers, validates changed source JSON, and (with a branch arg) flags test files present on the branch but MISSING now (lost-in-merge). Run before committing any `test`-branch merge, then `verify.sh`. | `bash .memory/tools/scripts/merge_check.sh [feature/<branch>]` |
| [scripts/integration_stack.sh](scripts/integration_stack.sh) | **SLOW, on-demand only** ([03](../03-local-setup-and-infra.md#wsl--docker-integration-tests-slow-on-demand-only)): start the local Mock stack or run backend integration tests INSIDE WSL (Docker lives only in WSL). Loads NuGet creds + forwards via WSLENV (no echo). Use only when the user asks or a failed pipeline's IT step needs local repro. | `bash .memory/tools/scripts/integration_stack.sh up\|test [args]` |
| [scripts/dev_server.sh](scripts/dev_server.sh) | Start/stop the frontend dev server for proofs; kills a stale `:3000` first + waits until up (fixes the leftover-node problem). | `bash .memory/tools/scripts/dev_server.sh start\|stop\|status` |
| [scripts/find_route.sh](scripts/find_route.sh) | Map a page/component keyword → Next.js route(s) + its `data-testid`s. For writing the reviewer test-guide comment (01) + proof navigation. READ-ONLY. | `bash .memory/tools/scripts/find_route.sh <keyword>` |
| [scripts/checkout_branch.sh](scripts/checkout_branch.sh) | Safe checkout for fix/continue: aborts on tracked changes, fetch → checkout → ff-only → status. | `bash .memory/tools/scripts/checkout_branch.sh feature/<branch>` |
| [scripts/publish_to_test.sh](scripts/publish_to_test.sh) | **Slice step 3b** ([05](../05-slice-workflow.md) "Publish to the shared `test` branch"): merge a feature branch into the long-lived `test` integration branch (union of all open features/PRs the testers test from) and push `origin/test`. Run BEFORE the first PR and after EVERY fix. Merges `--no-ff`, stops on conflict for manual union-resolve, returns to your branch. **Auto-writes a forensic [merge-log](../merge-logs/README.md)** (auto-merged + conflict lists + shas); on a conflict merge, append the per-file resolution rationale + final sha to it. NEVER merge `test` into master/feature; PRs still target master. | `bash .memory/tools/scripts/publish_to_test.sh feature/<branch> [--no-push]` |
| [scripts/repo_status.sh](scripts/repo_status.sh) | READ-ONLY one-shot repo orientation: branch + tracked status + diff-stat + recent log. Run at the start of a fix/continue. | `bash .memory/tools/scripts/repo_status.sh` |
| [scripts/backend_info.sh](scripts/backend_info.sh) | READ-ONLY backend snapshot: SDK, sln projects, target frameworks, DbContext(es), EF migrations, dotnet-ef, test projects. Live complement to `csharp-source-architecture.md`. | `bash .memory/tools/scripts/backend_info.sh` |
| [scripts/openspec_example.sh](scripts/openspec_example.sh) | READ-ONLY OpenSpec format reference — prints an artifact from the newest ARCHIVED change (a live, non-rotting example) so you see the shape before running the `openspec-*` skills. NOT a template; never copy as the artifact. | `bash .memory/tools/scripts/openspec_example.sh proposal\|design\|tasks\|spec\|validation [change]` |
| [scripts/verify.sh](scripts/verify.sh) | Run the repo's canonical build/lint/test gate — `pnpm typecheck`+`lint`+`test` (frontend) and `dotnet build`+unit tests (backend, NuGet PAT auto-loaded). The dev's own checks before proof/PR. Run ONE test fast with `--jest <pat>` (frontend) / `--filter <expr>` (backend, `dotnet --filter`) — see [10](../10-testing-patterns.md). Complements the skills, replaces none. | `bash .memory/tools/scripts/verify.sh frontend\|backend\|all [--jest <pat>] [--filter <expr>] [--it] [--soft]` |
| [scripts/proof_shots.py](scripts/proof_shots.py) | Playwright proof harness — route-intercepts the boot calls (zero toasts) + captures the 3 sizes. Fill 2 CONFIG blocks. **`--annotate`** also emits `*_annotated.png` (green/red table column-alignment guides + `+Npx`; red gap lines with px labels — page margins, inter-block gaps, bottom gap; **red `CLIP Npx` boxes for cut-off content**) and prints `ALIGNMENT: OK/MISALIGNED` + `gaps(...)` + `CLIPPING: OK/CLIPPED`. A LIVING gate — extend per the [02 CLOSED LOOP](../02-ux-design-checklist.md) when a new spacing/cut-off finding is learned. Robust `mocks.json` lookup even when copied to scratchpad. | `pnpm dev` up, then `…/.venv/Scripts/python.exe .memory/tools/scripts/proof_shots.py <out_dir> [--annotate]`. Copy to scratchpad to edit; delete after. See [00](../00-playwright-proof-howto.md). |
| [scripts/proof_pixels.py](scripts/proof_pixels.py) | Pixel-region gate for proof PNGs. Catches screenshots where DOM assertions pass but the posted image is visually useless, blank-looking, or the relevant content occupies too little of the frame. No Pillow dependency. | `.venv\Scripts\python.exe .memory/tools/scripts/proof_pixels.py shot.png --region "card:60,230,700,260:0.02"` |
| [scripts/post_to_pr.py](scripts/post_to_pr.py) | PR comment poster — covers **proof** (upload shots + captioned @mention + set Done), **rebuttal** (no images, see [06](../06-azure-devops-templates.md) §7), and **plain** comments. Config-driven (header/fixes_line/originator/shots/set_state all optional). | `DEVOPS_PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json) python .memory/tools/scripts/post_to_pr.py <shots_dir>`. See [01](../01-proof-reporting-protocol.md)/[06](../06-azure-devops-templates.md). |
| [scripts/disk_cleanup.sh](scripts/disk_cleanup.sh) | Reclaim disk when WSL/Docker misbehaves (low disk = #1 WSL-crash cause, see [03](../03-local-setup-and-infra.md)). Conservative default; `--aggressive` drops all unused images/volumes/cache. | `bash .memory/tools/scripts/disk_cleanup.sh [--aggressive]` |
| [scripts/wsl_compact_vhdx.ps1](scripts/wsl_compact_vhdx.ps1) | Compact the WSL `ext4.vhdx` to return freed space to Windows. **Manual, ADMIN only — never auto-run**; hand to the user. | Admin PowerShell: `.\.memory\tools\scripts\wsl_compact_vhdx.ps1` |
| [scripts/cleanup_proof.sh](scripts/cleanup_proof.sh) | Housekeeping after proof/abandoned attempt: removes throwaway `pages/__*.tsx` + scratchpad shots/scripts/logs + stray `__pycache__`. Never touches committed files. | `bash .memory/tools/scripts/cleanup_proof.sh [scratchpad_dir]` |

## testdata/
| File | What |
|---|---|
| [testdata/mocks.json](testdata/mocks.json) | Standard mock payloads: `boot` (account/me, Unpaid/count=165, system/info), `searchRows` (7 realistic hits), `detail` (a DirectiveOrderResponse), `auditLogs` (7 Logdaten rows), `collectionCases` (7 Offene-Inkassofälle rows). Consumed by `proof_shots.py`. Human reference lives in [00](../00-playwright-proof-howto.md) — keep the two in sync. |

## Rules
- **Reuse before rewriting.** If a script/testdata here fits, use it (fill config) — don't hand-roll.
- **REUSABLE ONLY — never commit one-off/specific scripts.** A script belongs here only if it is
  **parametrised** (CONFIG block / args) and reliably reusable across cases. A script hardcoded to a
  single case — "create PR #1592", "post a comment to PR #1234", "create ticket for REQ-X" — must NOT be
  added; run it from the scratchpad and delete it. Otherwise we'd drown in hundreds of near-duplicate
  `create_pr_*.py`. Need a specific action? Fill the CONFIG of the existing tool (`post_to_pr.py`) or use
  the raw templates in [../06-azure-devops-templates.md](../06-azure-devops-templates.md). If you find
  yourself about to add a specific script, generalise it into an existing tool instead.
- **Add + document (reusable only).** New reusable script/testdata → add it here with a one-line index
  row + a header comment saying what/why/how. Parametrise; don't hardcode a single case.
- **Keep scripts ↔ docs in SYNC (link both ways).** `proof_shots.py` ↔ [00](../00-playwright-proof-howto.md);
  `post_to_pr.py` ↔ [01](../01-proof-reporting-protocol.md) + [06](../06-azure-devops-templates.md);
  `mocks.json` ↔ [00](../00-playwright-proof-howto.md). If you change a command / endpoint / flow in a
  script, update the linked `.md` in the SAME edit (and vice-versa) so they never diverge — and check the
  reverse link still points correctly. Drift here is corruption — self-heal it on sight.
- **Self-heal.** If a script errors or a payload is stale, FIX it here (don't work around it silently).
- **Skill-owned actions stay scripts-free.** Creating a **PR** and creating a **slice claim ticket** are
  owned by `complete-implementation-slice` / `pick-implementation-slice` — do NOT add `create_pr.py` /
  `create_ticket.py` here (they'd compete with the skills). Use the skills; for a manual one-off use the
  raw templates in [../06-azure-devops-templates.md](../06-azure-devops-templates.md).
- **OpenSpec artifacts: NO static templates.** `proposal.md`/`design.md`/`tasks.md`/delta `spec.md` are
  created & shaped by the `openspec-*` skills (`openspec-propose`, `openspec validate`, …). A static
  template would invite hand-writing that bypasses the skill and rots. For the format, run
  `openspec_example.sh <artifact>` (prints the newest archived change — live, never rots), then use the
  **skill** to create/update — never copy the example as the artifact.
- **`templates/` convention.** Static reusable templates are allowed ONLY for **non-skill-owned** artifacts
  and live in `.memory/tools/templates/` (with an index row here). None exist yet — nothing we'd template
  is both reusable AND not already owned by a skill / covered by a script. Do NOT add skill-owned artifact
  templates (OpenSpec, PR/ticket creation, validation.md) there.
- **`.memory/temp/` is the throwaway workspace.** Copy a template there, create scratch scripts/logs
  there, put proof PNGs there — NOT in the repo tree. It's git-ignored (under `.memory/`). `cleanup_proof.sh`
  wipes it. Never create throwaway files inside the repo (`pages/__*.tsx` etc.) except where a proof
  genuinely needs a preview page — and delete those immediately after (cleanup_proof.sh handles both).
- **Never** put PATs or real personal data here — mocks use synthetic data only.
