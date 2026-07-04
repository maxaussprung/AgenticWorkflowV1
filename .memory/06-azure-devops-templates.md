# Azure DevOps command templates (copy-paste — do NOT re-derive each time)

All REST via `curl`. Constants + identity GUIDs in [04-accounts-and-azure-metadata.md](04-accounts-and-azure-metadata.md).
**Most of this is automated by the skills** (`pick-implementation-slice` creates the claim ticket;
`complete-implementation-slice` opens the PR + adds reviewers + arms auto-complete). Use these raw
templates for speed, manual fixes, proof comments, and work-item status.

> **Reusable scripts do most of this — reach for them before curl** (all in [tools/](tools/README.md)):
> - **Inspect a work item / children / PR / screenshots:** [`tools/scripts/az_workitem.py`](tools/scripts/az_workitem.py) `<id> [--download <dir>]`.
> - **Post any PR comment** (proof / rebuttal / plain) + optional set-Done: [`tools/scripts/post_to_pr.py`](tools/scripts/post_to_pr.py).
> - **Set work-item state** (+children): [`tools/scripts/set_workitem_state.py`](tools/scripts/set_workitem_state.py).
>
> Use the raw calls below only for what the scripts + skills don't cover (creating a PR/ticket is owned
> by `complete-`/`pick-implementation-slice`; §1/§3 are for manual one-offs). **Keep in sync:** if you
> change a command/endpoint here, update the matching script too, and vice-versa (see `tools/README.md`).
> Do NOT create per-PR/per-ticket one-off scripts.

## 0. Auth (load PAT without printing it — PATs in `.memory/PATS/`)
```bash
PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json)            # or: python -c "import json;print(json.load(open('.memory/PATS/AZURE-PAT.json'))['pat'])"
B64=$(printf ':%s' "$PAT" | base64 -w0)                  # Azure REST uses Basic ":<PAT>"
H=(-H "Authorization: Basic $B64")
ORG=https://dev.azure.com/HPS-AT-GenAI; PROJ=Post
REPO=4d4baa85-9026-40ec-8f3e-1fa4d8e535ea
# NuGet build: export NUGET_POSTAT_USERNAME=jonas.hauser@accenture.com; export NUGET_POSTAT_CLEAR_TEXT_PASSWORD=$(jq -r .pat .memory/PATS/NUGET-PAT.json)
```
Never `echo`/`cat` the PAT or the json. Prefer a Python script (see [01](01-proof-reporting-protocol.md)
posting script) for multi-step posts — cleaner JSON handling.

**Do not resolve PATs relative to the repo root.** The directory is `.memory/PATS/`, not `PATS/`.
For one-off scripts in `.memory/temp/`, `Path(__file__).parents[1]` is `.memory`; use that for
`PATS/AZURE-PAT.json`. `parents[2]` is the repo root and produces the wrong missing path
`Post/PATS/AZURE-PAT.json`.

## 1. Create a work item (ticket) — with description, acceptance criteria, tags, parent
Types: `Product Backlog Item`, `Task`, `Bug`. Body = JSON-Patch (`application/json-patch+json`).
```bash
curl -s "${H[@]}" -H "Content-Type: application/json-patch+json" -X POST \
 "$ORG/$PROJ/_apis/wit/workitems/\$Task?api-version=7.0" -d '[
  {"op":"add","path":"/fields/System.Title","value":"VVF | <short title>"},
  {"op":"add","path":"/fields/System.Description","value":"<p>...HTML...</p>"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Common.AcceptanceCriteria","value":"<p>...HTML...</p>"},
  {"op":"add","path":"/fields/System.Tags","value":"vvf; frontend; ux"},
  {"op":"add","path":"/fields/System.AssignedTo","value":"jonas.hauser@accenture.com"},
  {"op":"add","path":"/relations/-","value":{"rel":"System.LinkTypes.Hierarchy-Reverse",
     "url":"'"$ORG"'/_apis/wit/workItems/<PARENT_ID>"}}
]'
```
**Description LAYOUT** (mirror `pick-implementation-slice`, see implementation-slice-workflow.md §4):
opening business paragraph ("This claim covers the VVF <feature> …") → **Implementation scope**
block (feature, requirements REQ-*, OpenSpec path, owner, branch, `openspec/track.md`) → boundary
sentences (what stays OUT of scope) → **Database impact** section when a requirement has DB
necessities (create/extend/use/read + target tables). Fields are **HTML** (`<p>`, `<ul><li>`, `<b>`).
**Acceptance criteria LAYOUT**: Given/When/Then lines derived from the requirement pages (one block
per AC), including DB acceptance criteria when there's DB impact.

## 2. Set work-item state / fields
```bash
curl -s "${H[@]}" -H "Content-Type: application/json-patch+json" -X PATCH \
 "$ORG/$PROJ/_apis/wit/workitems/<ID>?api-version=7.0" \
 -d '[{"op":"add","path":"/fields/System.State","value":"Done"}]'   # Task: To Do|In Progress|Done
```
PBI states: New|Approved|Committed|Done. Move a claim ticket to `Approved` after branch link (§5).

## 3. Create a PR (with description, reviewers, work-item link, auto-complete)
```bash
# create
PRID=$(curl -s "${H[@]}" -H "Content-Type: application/json" -X POST \
 "$ORG/$PROJ/_apis/git/repositories/$REPO/pullRequests?api-version=7.0" -d '{
  "sourceRefName":"refs/heads/feature/<branch>","targetRefName":"refs/heads/master",
  "title":"feat(<area>): <slice title> (REQ-XXX-000)",
  "description":"## What\n...\n## Requirements\nREQ-XXX-000\n## Validation\n...",
  "workItemRefs":[{"id":"<AZURE_ID>"}]
 }' | python -c "import sys,json;print(json.load(sys.stdin)['pullRequestId'])")
# add required reviewers (Tobias always; Yujiao when frontend). isRequired=true
for RID in ed127298-d005-60ef-a1e7-24650e2dff64 deee0071-c83d-6e32-8bb6-b8b24d362fd5; do
 curl -s "${H[@]}" -H "Content-Type: application/json" -X PUT \
  "$ORG/$PROJ/_apis/git/repositories/$REPO/pullRequests/$PRID/reviewers/$RID?api-version=7.0" \
  -d '{"vote":0,"isRequired":true}'; done
# arm auto-complete (set by me = Jonas), squash + delete source
curl -s "${H[@]}" -H "Content-Type: application/json" -X PATCH \
 "$ORG/$PROJ/_apis/git/repositories/$REPO/pullRequests/$PRID?api-version=7.0" -d '{
  "autoCompleteSetBy":{"id":"5317506a-a75a-6a15-b57b-8862123b808c"},
  "completionOptions":{"deleteSourceBranch":true,"squashMerge":true,"mergeStrategy":"squash"}}'
```
(Prefer letting `complete-implementation-slice` do all of the above; these are the raw calls.)

## 4. Attach an image to a PR (returns embeddable url)
```bash
curl -s "${H[@]}" -H "Content-Type: application/octet-stream" --data-binary @shot.png -X POST \
 "$ORG/$PROJ/_apis/git/repositories/$REPO/pullRequests/<PRID>/attachments/shot_$(date +%s).png?api-version=7.1-preview.1"
# → response .url  →  embed in markdown as ![caption](<url>)
```

## 5. PR comment thread (+ @mention). status:1=active, 4=closed(fixed)
```bash
curl -s "${H[@]}" -H "Content-Type: application/json" -X POST \
 "$ORG/$PROJ/_apis/git/repositories/$REPO/pullRequests/<PRID>/threads?api-version=7.0" -d '{
  "comments":[{"parentCommentId":0,"commentType":1,"content":"<markdown>"}],"status":1}'
```
**@mention** in `content` = `@<identity-GUID>` (Yujiao `deee0071-…`, Tobias `ed127298-…`).

## 6. Proof-comment template (UX/tester response OR new-slice) — fill & post
```
**REQ-XXX-000 (<capability>) — <fix|new slice> proof, verified live via Playwright**

Fixes [#<ID> — <work item title>](<work item url>).      ← omit "Fixes …" line for a new-slice PR intro

@<GUID> <one sentence: what changed / what to look at>.

**1 · Min 1280×1024 — <caption>**
![min](<attachment url>)
**2 · Max 1920×1680 — <caption>**
![max](<attachment url>)
**3 · Whole page**
![full](<attachment url>)
```
Then set the work item **Done** (§2) and clean up local proof.

## 7. "This finding is wrong" template (tester/UX can be mistaken)
If, after fully analysing, you're confident a finding is invalid/not-a-bug: do NOT silently skip it.
Post a PR comment linking the work item + its requirement, explain WHY it needs no fix, **@mention
the originator**, then set the work item Done (temporary "completed" pending their reply).
```
**Re: [#<ID> — <title>](<url>) — REQ-XXX-000: no change needed**

@<GUID> I looked into this and I don't think a change is warranted:
- <evidence 1 — cite code path / requirement AC / screenshot>
- <evidence 2>
The current behaviour matches <REQ-XXX-000 AC-n / the design / existing forms>. Marking this Done
for now — please reopen with a note if you disagree and I'll revisit.
```
Attach a screenshot if it helps prove current behaviour. Be respectful; they may be right.

## 8. Reviewer test-guide comment template (EVERY PR, separate from proof — see 01)
Gather routes + testids with `tools/scripts/find_route.sh <keyword>`. @tag ALL required reviewers.
```
**How to test — REQ-XXX-000 (<slice title>)**

@<TOBIAS_GUID> @<YUJIAO_GUID> step-by-step manual test (Mock stack):

**Where:** `http://localhost:3000/<route>` — <the page>. (If not directly reachable: <entry flow, e.g.
landing → Suchen → row action "…">.)
**Setup:** <seed/search a known record; e.g. run the Mock stack; reindex Typesense if search-backed>.

1. Open `<route>` → expect <the page with …>.
2. <do X — click `[data-testid=…]` / enter …> → expect <Y>.
3. <next AC step> → expect <…>.
…
**Covers:** AC-1 (…), AC-2 (…), … . Deferred/not-testable-here: <…>.
```
Keep steps concrete and in reviewer language (buttons/labels, not code). Post with `post_to_pr.py`
(shots=[], originator=[all required reviewers]).

## 9. Limitations comment template — requirement not fully met / blocked (OPTIONAL, all reviewers, LAST)
Post ONLY when a stated requirement/spec detail couldn't be fully satisfied or something is blocked by a
platform/library/external limitation (see [01 §4th comment](01-proof-reporting-protocol.md)). @tag ALL
required reviewers. Post with `post_to_pr.py` (shots=[], originator=[all required reviewers]).
```
**Limitations / not fully met — REQ-XXX-000 (<slice title>)**

@<TOBIAS_GUID> @<YUJIAO_GUID> flagging where the implementation could not fully meet the spec, so it's a
surfaced decision, not an oversight:

- **<AC / spec detail>:** could not be met as written — <the limitation, e.g. "amarillo `Typography` has
  no `h6` variant (supports h1–h5)">. Shipped: <closest thing, e.g. "rendered as `h5`, the nearest
  supported heading">. Full compliance needs: <what would unblock it, e.g. "an amarillo `h6` variant / a
  design sign-off on h5">.
- <next limitation, if any>

Everything else in the ACs is fully met (see the proof + test-guide comments).
```

## 10. Tester-response comment template — how each finding was fixed (non-UI tester findings)
For a Tobias/tester finding that is NOT frontend-observable (backend/logic/data), no proof screenshots —
explain the fix point by point. @tag **Tobias only**. Post with `post_to_pr.py` (shots=[],
originator="tobias"), then set the work item Done.
```
**Re: [#<ID> — <title>](<url>) — REQ-XXX-000: fixed**

@<TOBIAS_GUID> thanks — addressed each point:

- **<finding 1>:** <what changed + file/where> — verified via <test name / command / result>.
- **<finding 2>:** <what changed> — <how verified>.

Backend build + tests green (`verify.sh backend`). Marking Done — reopen if anything's still off.
```
