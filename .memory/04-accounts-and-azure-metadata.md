# Accounts & Azure DevOps Metadata

## Accounts
- Single user account for everything: **jonas.hauser@accenture.com**.
- Two PATs, SAME account, DIFFERENT scopes — **provided by the user per session, NOT stored here**
  (secrets; they rotate):
  - **DevOps PAT** → master agent uses it for all Azure REST (work items, PRs, attachments).
    **Scope now includes Build (Read)** (added 2026-07-02) → pipeline/build results ARE readable; use
    [`tools/scripts/az_build.py`](tools/scripts/az_build.py) to check a PR/branch's latest build + failing
    tests (the "watch CI to green" step, [07](07-kickoff-and-triggers.md)).
  - **NUGET PAT** → given to spawned agents for `dotnet build` (NuGet feed auth).
- Do not persist raw token values in this repo, even locally.
- **Load both into the session** (as env, never printed) with
  [`tools/scripts/session_env.ps1`](tools/scripts/session_env.ps1) `-WithSecrets` → sets `DEVOPS_PAT`,
  `NUGET_POSTAT_USERNAME`, `NUGET_POSTAT_CLEAR_TEXT_PASSWORD`, `PAT` (see [03 Session setup](03-local-setup-and-infra.md#session-setup-path--secrets)).
  Read a failed pipeline's cause with `az_build.py <pr> --logs` (tails the failed step's log).

## Azure DevOps constants (not secret)
- Org: `https://dev.azure.com/HPS-AT-GenAI`  ·  Project: `Post`
- Repo id: `4d4baa85-9026-40ec-8f3e-1fa4d8e535ea` (repo name `Post`)
- Auth header for REST: `Authorization: Basic base64(":" + <DevOps PAT>)`

## Identity GUIDs (for @mentions `@<GUID>`, reviewers, autoCompleteSetBy, AssignedTo)
| Person | Role | GUID | Email |
|---|---|---|---|
| Hauser, Jonas | me (owner) | `5317506a-a75a-6a15-b57b-8862123b808c` | jonas.hauser@accenture.com |
| Li, Yujiao | UX colleague / reviewer (frontend) | `deee0071-c83d-6e32-8bb6-b8b24d362fd5` | yujiao.a.li@accenture.com |
| Zizka, Tobias | tester / reviewer (always) | `ed127298-d005-60ef-a1e7-24650e2dff64` | tobias.zizka@accenture.com |

## PATs (local-only, `.memory/PATS/`)
`AZURE-PAT.json` (master → Azure REST) and `NUGET-PAT.json` (build agents → NuGet). Load without
printing: `PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json)` (or the python one-liner). These are TEMP
session tokens — if a call returns 401/403 the PAT rotated; ask the user for a fresh one.

**Path gotcha (hit 2026-07-02):** the PAT directory is exactly `Post/.memory/PATS/`, not
`Post/PATS/`. A scratch script under `.memory/temp/` should resolve `Path(__file__).parents[1]`
to `.memory` and then read `.memory/PATS/AZURE-PAT.json`; `parents[2]` is the repo root and will
incorrectly point at missing `Post/PATS/AZURE-PAT.json`. Prefer reusing the existing Azure scripts,
which already load from `.memory/PATS`.

## Current slices in flight — source of truth is `openspec/track.md` (do NOT hardcode here)
Which slices/PRs are claimed / in-review / done rots fast, so read it live from `openspec/track.md`
(Owner/Status/PR columns) + `az_pr.py <prid>` for votes/comments, rather than a hardcoded list here.
Map a branch → PR fast: `git fetch` then query PRs by `searchCriteria.sourceRefName=refs/heads/<branch>`
(or the branch's `openspec/track.md` PR column). Check its pipeline with `az_build.py <pr-id>`.

## Handy REST snippets
```bash
PAT=$(printf ':%s' "$DEVOPS_PAT" | base64 -w0); ORG=https://dev.azure.com/HPS-AT-GenAI
# work item + children
curl -s -H "Authorization: Basic $PAT" "$ORG/Post/_apis/wit/workitems/<id>?\$expand=relations&api-version=7.0"
# set state Done
curl -s -X PATCH -H "Authorization: Basic $PAT" -H "Content-Type: application/json-patch+json" \
  "$ORG/Post/_apis/wit/workitems/<id>?api-version=7.0" -d '[{"op":"add","path":"/fields/System.State","value":"Done"}]'
# attach to PR
curl -s -X POST -H "Authorization: Basic $PAT" -H "Content-Type: application/octet-stream" \
  --data-binary @file.png "$ORG/Post/_apis/git/repositories/4d4baa85-9026-40ec-8f3e-1fa4d8e535ea/pullRequests/<pr>/attachments/<name>.png?api-version=7.1-preview.1"
# comment thread
curl -s -X POST -H "Authorization: Basic $PAT" -H "Content-Type: application/json" \
  "$ORG/Post/_apis/git/repositories/4d4baa85-9026-40ec-8f3e-1fa4d8e535ea/pullRequests/<pr>/threads?api-version=7.0" \
  -d '{"comments":[{"parentCommentId":0,"commentType":1,"content":"..."}],"status":1}'
```
