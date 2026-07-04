# Local Setup & Infrastructure

## Session setup (PATH + secrets) — and why there is NO "run once"
**Each shell tool call is a FRESH process with a frozen inherited env.** PATH/`$env` changes do NOT
persist to the next tool call or to spawned agents — proven: setting `$env` or even the persistent
User `PATH` in one call, a separate call sees neither (bash stays missing). So **do not** rely on a
one-time setup. What IS already on the inherited PATH: `git`, `jq`, `pnpm`, `dotnet`, `node`, `wsl.exe`.
What is **NOT**: `bash`/`grep`/`sed`/`awk` (Git's `bin\` dir isn't on it), and bare `python`/`mkdocs`/`tsc`.

**Robust invocation (per call — this is what actually works):**
- **bash script:** `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/X.sh` (full path).
- **python script:** `.venv/Scripts/python.exe .memory/tools/scripts/X.py` (from repo root; UTF-8: prefix `$env:PYTHONUTF8=1;`).
- **bare tool names** (`bash`/`tsc`/`mkdocs`/`python`) only if you prepend, in the SAME call,
  `. .\.memory\tools\scripts\session_env.ps1 | Out-Null;` (`-WithSecrets` also loads `DEVOPS_PAT`,
  `NUGET_POSTAT_*`, `NPM_POSTAT_*`, `PAT` into `$env` without printing them — PAT files stay
  reference-only, [README core rule](README.md)). It affects THAT call only.
- **Don't inline complex Python/quoting in a PowerShell call** — PowerShell mangles `$(...)`/quotes/`[]`.
  Write it to `.memory/temp/*.py|*.sh` and run it by full path (`cleanup_proof.sh` wipes temp after).

[`tools/scripts/session_env.ps1`](tools/scripts/session_env.ps1) is only for the bare-name case above.
`wsl.exe` is on PATH; **Docker runs INSIDE WSL, not on the Windows host** (see the WSL section below).
See every tool: `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/lookup_memory_tools.sh`.

## Repo paths
- Git + builds run from **`C:/Users/jonas.hauser/ROOTPOST/Post`** (fast local copy). The
  `OneDrive - Accenture/Desktop/ROOTPOST/Post` path is the same project but OneDrive-synced and
  SLOW — do work in the ROOTPOST path.
- `.memory/` lives here and is ignored via `.git/info/exclude` (local-only, survives checkouts).
- **Switch to a slice/fix branch** with [`tools/scripts/checkout_branch.sh`](tools/scripts/checkout_branch.sh)
  `feature/<branch>` — aborts on tracked changes, fetches, checks out, fast-forwards, shows status.
- **Orient at the start of a fix/continue** with [`tools/scripts/repo_status.sh`](tools/scripts/repo_status.sh)
  (branch + tracked status + diff-stat + recent log, read-only).

## Verify (canonical gate — one command)
[`tools/scripts/verify.sh`](tools/scripts/verify.sh) `frontend|backend|all [--jest <pat>] [--it]` runs the
repo's own checks (frontend `pnpm typecheck`+`lint`+`test`; backend `dotnet build` + `Mad.UnitTests`, NuGet
PAT auto-loaded). Use it for the final gate before proof/PR. Raw commands below are for quick per-file iteration.

## Requirements-site build (mkdocs --strict)
Just run [`tools/scripts/mkdocs.sh`](tools/scripts/mkdocs.sh) (strict build; `serve` to preview). It uses
the VERIFIED Windows path `.venv/Scripts/mkdocs.exe` — NOT `.venv/bin/mkdocs` (the POSIX path AGENTS.md
cites, absent here). Underlying command: `.venv/Scripts/mkdocs.exe build -f tools/requirements-site/mkdocs.yml --strict`
(exit 0; ~60s; only INFO notices for pre-existing excluded links — no warnings). Run after editing any
`docs/requirements/**` page (e.g. adding `openspec_change` frontmatter + Architecture sections).

## .NET SDK / runtimes present here
`dotnet --list-sdks` → 8.0.310, 9.0.203, 9.0.205; net8 runtime (8.0.14/8.0.15) present. The backend
projects target **net8.0** and build fine with SDK 9 (net8 targeting pack installed). No side-by-side
juggling needed for the unit-test gate. Integration tests need Docker, which is **not on the Windows
host** (`docker info` fails there) — Docker lives **inside WSL (Ubuntu)**, so IT runs in CI or, when a
local repro is truly needed, inside WSL (see [WSL + Docker integration tests](#wsl--docker-integration-tests-slow-on-demand-only)). `dotnet ef` v9 installed.

## Frontend (`csharp/src/frontend`, pnpm) — canonical scripts
- Dev server: `pnpm dev` → http://localhost:3000. API base `https://localhost:7098` (.env.development).
  Prefer [`tools/scripts/dev_server.sh`](tools/scripts/dev_server.sh) `start` (kills a stale `:3000`,
  waits until up): `& "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/dev_server.sh start`.
  It **backgrounds** pnpm dev (log → `.memory/temp/devserver.log`). **INVOKE IT WITH A BOUNDED TOOL
  TIMEOUT (~30000ms) and do NOT pipe it through `Select-Object`** — on Windows the backgrounded
  node/Next process can keep the tool call's stdout pipe open, so the call may not return until its
  timeout (this is what made agents "get stuck" for 2-3 min). The server is up in a few seconds; once
  the output shows `up on http://localhost:3000` it's READY — a **timeout-return with that line is
  success**, proceed. To confirm cheaply without any wait, use `dev_server.sh status` (prints whether
  :3000 is held) or just `curl -s -o /dev/null http://localhost:3000`. If it's already running, skip the
  start entirely. `dev_server.sh stop` when done.
- Typecheck: `pnpm typecheck` (= `tsc --noEmit`). Lint: `pnpm lint` (whole) / `next lint --file <path>` (fast per-file; warnings can fail `--file` — keep clean).
- Tests: `pnpm test [pattern]` (jest). Also `pnpm build`, `pnpm test:ci` (coverage), `pnpm test:it|si|e2e` (playwright).
- For proof screenshots see [00-playwright-proof-howto.md](00-playwright-proof-howto.md). MSW is
  broken in-browser — do NOT use it.
- If `.venv/Scripts/python.exe` Playwright says Chromium is missing, install the browser once with
  `.venv\Scripts\python.exe -m playwright install chromium`.

## Backend (.NET 8, `csharp/`)
- Build needs NuGet feed auth (account jonas.hauser@accenture.com; NUGET PAT provided per session):
  ```bash
  export NUGET_POSTAT_USERNAME=jonas.hauser@accenture.com
  export NUGET_POSTAT_CLEAR_TEXT_PASSWORD=<NUGET PAT>
  dotnet build csharp/PostAG.Logistics.Mad.sln
  ```
- Integration tests use Testcontainers → need Docker running.

### Backend-only Mock smoke test
- `dotnet run --project csharp/src/backend/PostAG.Logistics.Mad.API/PostAG.Logistics.Mad.API.csproj --launch-profile Mock --no-build`
  listens on `https://localhost:7098` and is enough to curl Mock-only endpoints without the Docker stack.
- If LocalDB throws `Cannot create file 'C:\Users\jonas.hauser\DirectivesDb.mdf' because it already exists`,
  do **not** delete files outside the repo. Override just this shell with a throwaway DB name, e.g.
  `$env:ConnectionStrings__VvfDb='Server=(localdb)\MSSQLLocalDB;Database=DirectivesDb_MockCheck_<case>;Trusted_Connection=True;MultipleActiveResultSets=true;'`.

## WSL + Docker integration tests (slow, on-demand only)
Docker/Testcontainers work **only inside WSL (Ubuntu)** on this machine — not on the Windows host.
Bringing up the stack or running integration tests is **SLOW** (minutes to build+boot), so this is
**NOT** part of the normal per-slice loop. Do it ONLY when:
- the user explicitly asks for a running local stack / local integration testing, **or**
- a failed pipeline's failing step **is the backend integration tests** and you must reproduce locally
  (triage the build first with [`tools/scripts/az_build.py`](tools/scripts/az_build.py) `<pr> --logs`).

One helper does it — [`tools/scripts/integration_stack.sh`](tools/scripts/integration_stack.sh) — which loads
the NuGet creds (no echo), forwards them into WSL via `WSLENV`, and runs inside WSL:
```bash
bash .memory/tools/scripts/integration_stack.sh up          # start the Mock stack (start-mock-docker.sh)
bash .memory/tools/scripts/integration_stack.sh test [args] # backend integration tests via backend-test.sh
```
Equivalent manual form (what it runs inside WSL) — the exact commands, for reference/debug:
```bash
export NUGET_POSTAT_USERNAME=jonas.hauser@accenture.com
export NUGET_POSTAT_CLEAR_TEXT_PASSWORD=$(jq -r .pat .memory/PATS/NUGET-PAT.json)   # never echo it
export PAT="$NUGET_POSTAT_CLEAR_TEXT_PASSWORD"
wsl.exe -d Ubuntu bash -lc 'cd "$(wslpath -a "<repo>")" && bash csharp/tools/local-dev/start-mock-docker.sh'
```
`wsl.exe` is on PATH (System32); `wsl -l -v` shows the running **Ubuntu** distro. The repo is reached
inside WSL via `/mnt/c/...` (`wslpath`). If it misbehaves, low disk is the usual cause — see the pitfalls below.

**MANDATORY — disk cleanup AFTER every WSL integration/mock run.** Bringing up the mock stack /
running integration tests rebuilds Docker images + build cache INSIDE the WSL vhdx (measured ~15 GB —
it took C: from comfortable back to critical). So **as soon as you're done** (stack stopped / tests
finished), run the disk-cleanup flow — prune Docker inside WSL, then (hand the user) the vhdx compact:
```bash
wsl.exe -d Ubuntu bash -lc "docker system prune -af; docker builder prune -af; docker volume prune -f"
```
then reclaim the vhdx per [Local machine pitfalls → cleanup order](#local-machine-pitfalls-root-caused-before)
(`wsl_compact_vhdx.ps1`, ADMIN — hand to the user). This is NOT optional: leaving the stack's images
behind is what keeps refilling C:. Every WSL test/integration session ends with a cleanup.

## Docker mock stack (backend Mock env)
- **Runs inside WSL** (see the section above) — launch via `integration_stack.sh up`, which calls
  `bash csharp/tools/local-dev/start-mock-docker.sh` (wraps start-docker.sh with VVF_MOCK=1; builds all
  images, removes old containers itself). Flags pass through: `--build backend|frontend|all`,
  `--no-build`, `--restart frontend`.
- Containers: vvf_api (5000 http / 5001 https), vvf_api_database (mssql 1433, NO volume → reseeds on
  recreate), vvf_typesense (8108, volume ./typesense-data → KEEPS stale docs), vvf_ui (3000),
  vvf_wiremock_standalone. Swagger: https://localhost:5001/docs/index.html.
- Frontend Docker build is slow (~20 min): `.next` (138M) is NOT in the frontend `.dockerignore`
  so the build context is huge. (Known; not yet optimized per user.)

## Typesense reset (when search shows "Auftrag nicht gefunden" / stale / 409 after a restart)
The DB reseeds on recreate but the Typesense volume keeps old docs → mismatch. Fix:
```bash
curl -X DELETE 'http://localhost:8108/collections/directive-orders' -H 'X-TYPESENSE-API-KEY: typesense-api-key'
curl -sk -X POST https://localhost:5001/directives/orders/index   # wait a few seconds
```
(GET-by-id reads the DB, not Typesense. Reindex endpoint returns 202. Single + batch index handlers
now upsert, and the `validTo` field is optional — the schema only re-applies on a fresh collection,
hence the DELETE above.)

## Local machine pitfalls (root-caused before)
- **Low disk space → WSL crashes / filesystem lockups.** If WSL/Docker acts up (disk-full, locked
  files, weird build failures) or C: is low, CHECK FREE DISK FIRST and clean up. The **fast, high-yield
  cleanup order** (verified — took C: from 2.4 GB → ~9 GB, plus ~15 GB reclaimable behind the vhdx):
  1. **User `%TEMP%` is the #1 quick Windows win** — it had **5.7 GB** of throwaway; clear it (skip
     locked files). Also `C:\Windows\Temp`. (`.next`/`.turbo` build caches too — `disk_cleanup.sh` does those.)
  2. **`disk_cleanup.sh`'s docker prune is a NO-OP from git-bash** (Docker lives only in WSL). Prune
     INSIDE WSL: `wsl.exe -d Ubuntu bash -lc "docker system prune -af; docker builder prune -af; docker volume prune -f"`.
     Here the **Docker build cache (~11 GB) + unused images (~4.7 GB)** were the real hogs (~12 GB reclaimed).
  3. `pnpm store prune` (frees unreferenced store pkgs) + `dotnet nuget locals http-cache --clear` (safe;
     leaves `~/.nuget/packages` ~2.6 GB, which re-downloads only if you also clear it).
  4. **The WSL `ext4.vhdx` never auto-shrinks** — on THIS machine it lives at
     **`%LocalAppData%\wsl\{guid}\ext4.vhdx`** (~18 GB; NOT under `\Packages`). After the in-WSL prune the
     space is free inside WSL but the Windows file stays huge → to return it to C: run
     [`tools/scripts/wsl_compact_vhdx.ps1`](tools/scripts/wsl_compact_vhdx.ps1) in an **ADMIN** PowerShell
     (the agent must NOT auto-run it — hand it to the user; the script now searches both `\Packages` and `\wsl`).
  This has been the cause of multiple WSL crashes.
- `/mnt/c` builds are slow — expect long Docker frontend builds.
- npm/nuget need the per-session PATs (account jonas.hauser@accenture.com).

## Spawned-agent constraints
- Spawned agents historically die mid-run ("previous Claude Code process exited") — if nothing
  landed on disk, just re-spawn. Keep spawned-agent tasks scoped and verifiable.
- Give spawned agents the NUGET PAT for backend builds; the master keeps the DevOps PAT for Azure.
