# Proof + Azure DevOps Reporting Protocol

Applies to every fix that closes a **tester- or UX-originated** work item, and to every **newly
implemented slice** at `complete-implementation-slice` time.

## Comment order on a NEW-slice PR (post in this sequence, at complete-implementation-slice)
1. **Proof comment** — the clean page screenshots (3 sizes). @tag **all required reviewers**. (Frontend-observable changes only — a pure backend/no-UI slice has no proof screenshots.)
2. **UX-overlay comment** — the `--annotate` screenshot (red alignment/gap lines + px). @tag **Yujiao (UX) only**. (Only when the UI has a table / alignment-sensitive layout.)
3. **Test-guide comment** — the step-by-step manual test. @tag **all required reviewers**.
4. **Limitations comment (OPTIONAL — only when it applies)** — see below. @tag **all required reviewers**. Posted LAST, and ONLY when a requirement could not be fully met or something is now blocked by a limitation.

So a typical frontend slice posts **3** comments (1–3); if it also hit a limitation it posts a **4th**.
A pure-backend slice posts the test-guide (and the 4th if applicable) but no proof/overlay comments.
The last slice (a fully-met frontend slice) correctly had **no** 4th comment.

## 4th comment — requirement not fully met / blocked by a limitation (OPTIONAL, all reviewers)
Post this ONLY when, during implementation, a stated requirement/spec detail **could not be fully
satisfied** or something is **blocked** by a platform/library/external limitation — so the reviewers know
it's a conscious, surfaced gap, not an oversight. @tag **ALL required reviewers**. It is the LAST comment.
Content (template in [06 §9](06-azure-devops-templates.md)): the requirement/AC id, WHAT couldn't be met,
the LIMITATION that blocks it (e.g. "amarillo `Typography` has no `h6` variant → rendered `h5`"; "external
Label-Center machine unavailable"; "PERI-DB field not yet returned"), the workaround/closest thing shipped,
and what would unblock full compliance. Examples that warrant it: an amarillo API limit forcing a design
deviation (h6→h5), an external system not connected, a deferred dependency. Post it with `post_to_pr.py`
(shots=[], originator=all reviewers). If everything was fully met, do NOT post it.

## After review: fixing a tester/UX finding on the OPEN PR (post per finding)
When a reviewer finding is fixed, the comment(s) depend on whether the fix is frontend-observable:
- **UX / frontend finding (Yujiao, or any visible change):** post a **proof comment** (screenshots) — AND,
  **when the fix changed a SPATIAL property, a SECOND `--annotate`/pixel-overlay comment is MANDATORY**.
  **OVERLAY-REQUIRED trigger — did the fix move/resize/space anything?** placement, alignment (left-edge
  to a sibling column), margin, gap, padding, spacing, width/height that affects layout, a cut-off/clip, or
  table-column alignment → **YES, post the overlay** that **measures the fixed value** (`getBoundingClientRect`
  left-edges / the 16px·24px·48px gaps drawn + labelled; nothing `CLIP`ped; header over its column).
  Screenshots alone are NOT proof of a spatial fix — the overlay is (step 3 of the
  [02 CLOSED LOOP](02-ux-design-checklist.md); do step 1 record + step 2 extend the overlay first).
  **NO overlay needed** for a NON-spatial visible change: heading LEVEL/variant (h5→**h4**), label/wording,
  a color token, an icon swap, or enabling/disabling/adding/removing a control — the plain proof shot suffices.
  Worked examples: **#2209** (form left-aligned to the card + 16/16/48px gaps) → proof **+ overlay**;
  **#2211** (heading → h4, a semantic level, no re-spacing) → proof **only**; **#2219** ("Ansehen" button
  re-enabled for cancelled rows) → proof **only**. If unsure whether it's spatial, post the overlay.
  @tag the **originator** (Yujiao for UX). Set the work item Done.
- **Tester finding that is NOT frontend/UX (Tobias, backend/logic/data):** do NOT post proof screenshots.
  Post a **tester-response comment** explaining, point by point, **how each finding was fixed** (what
  changed + where + how you verified: tests/commands). @tag **Tobias only**. Set the work item Done.
  (Agents already do this via `post_to_pr.py` plain mode; template in [06 §10](06-azure-devops-templates.md).)
- A tester finding that DID require a visible change is treated like the UX case (proof + overlay).

**Always bank the learning — for EVERY finding, whatever the source** (core rule, see [README](README.md#core-rule--every-fix-flow-finding-becomes-a-learning-ux-tester-or-any-source)):
a fixed finding means something was wrong, so record the root cause + fix + how-to-avoid in the right file
(UX/spacing/cut-off → [02](02-ux-design-checklist.md) + its CLOSED LOOP; frontend → [09](09-frontend-patterns.md);
backend → [08](08-backend-patterns.md); test gap → [10](10-testing-patterns.md); infra → [03](03-local-setup-and-infra.md)).
A rebutted (wrong) finding gets banked too. This is not optional — a fix with no learning is incomplete.

### Finding intake: parent ticket vs already-done child tasks
Before analyzing a screenshot, read the parent ticket discussion with
`az_workitem.py <id> --comments --download <dir>` **and** inspect the latest tester commit on the branch.
Do not re-open/re-analyze an already-Done child task just because its old attachment downloaded first.
Use the newest active blocker as the source of truth:
- Parent PBI discussion comment + latest tester commit = current finding.
- Done child task screenshots = historical context only unless the newest comment explicitly points back
  to that task as still failing.
- If screenshots show raw i18n keys (`personendaten.titlePrefix`) while translations exist, check the
  page `getStaticProps` namespace `pick(...)`; component tests with a full translation provider may pass
  even when the runtime page omitted that namespace.

## No double-testing
Either the master agent runs Playwright, OR a spawned agent runs it and passes screenshots back —
**never both**. Preferred split: **spawned agent generates screenshots only; master analyzes +
posts to Azure.** Tell the spawned agent explicitly NOT to post/comment/change work items.

## Per work item / component: 3 screenshots
1280×1024, 1920×1680, and whole-page@1920 (see [00-playwright-proof-howto.md](00-playwright-proof-howto.md)).
ALWAYS the full page in context — never the isolated component. Mock everything; zero error toasts.

## Before posting — CRITICAL verification (be strict, double-check)
1. Open every screenshot and confirm the fix is genuinely visible.
2. Run the **pixel-region gate** from [00](00-playwright-proof-howto.md) on the relevant proof area
   (not only the whole screenshot): `proof_pixels.py shot.png --region "label:x,y,w,h:0.02"`.
   DOM assertions are not enough; a locator can contain the right text while the attached PNG is mostly
   blank or the important component is too small to serve as proof. If the pixel gate fails, or if the
   important content is only a tiny island in a large empty frame, retake with better framing and/or add
   a close-up proof image alongside the full-page context.
3. Confirm NO toasts "Failed to fetch" / "Cannot read properties of undefined (reading 'statusCode')".
   If present → retake (an endpoint wasn't mocked).
4. Run the [02-ux-design-checklist.md](02-ux-design-checklist.md). If you spot anything the UX
   colleague would flag (misaligned table head/body, cut-off buttons, wrong header sizes, gaps
   not matching our spacing) → **fix first** (spin up a fix agent), re-proof, THEN post.

## Who to @tag (get this right)
- **Initial / new-slice proof comment** (posted at complete-implementation-slice on the fresh PR):
  @tag **ALL required reviewers** of that PR — Tobias (always) + Yujiao (when the slice touches frontend).
- **Task-response comment** (fixing/answering a specific tester/UX work item): @tag **only the owner of
  that task** (the person who raised it) — Yujiao for a UX item, Tobias for a tester finding. Not everyone.
Identity GUIDs in [04](04-accounts-and-azure-metadata.md); `post_to_pr.py` `originator` takes a list for the
initial comment (all reviewers) or a single key for a task response.

## Reviewer test-guide comment (EVERY PR — separate from the proof comment)
On every PR (at complete-implementation-slice, alongside the proof comment) post a SECOND comment that
@tags **all required reviewers** and gives a **step-by-step manual test guide** so they can verify without
reading the code:
- **Where:** the exact page(s)/route(s) + the direct URL to reach the changed component
  (`http://localhost:3000/<route>`), and the entry flow if it's not directly reachable
  (e.g. landing → search → row action).
- **Steps:** a numbered click-through (open route → do X → expect Y), covering each acceptance criterion.
- **Data/preconditions:** what to seed/search for (Mock stack / a known record), and any setup
  (e.g. reindex Typesense per [03](03-local-setup-and-infra.md)).
- **What to look for:** the concrete expected result per step (matches the ACs).
Gather routes + click targets fast with [`tools/scripts/find_route.sh`](tools/scripts/find_route.sh)
`<keyword>` (prints the page route(s) + the component's `data-testid`s). Template in
[06 §Reviewer test-guide](06-azure-devops-templates.md). Post it with `post_to_pr.py` (shots=[],
originator=all reviewers).

## Annotated UX-overlay comment (when the UI has a table / alignment-sensitive layout)
When the change touches a DataTable (or other overlay-checkable layout), also run the proof with
`proof_shots.py --annotate` and post the `*_annotated.png` as a separate comment **tagging Yujiao (UX)
ONLY** — it is the UX designer's artifact: green/red column guides (headers over columns) + **red gap
lines with px labels** (page margins, input↔input gaps, row→button, block→table, bottom gap), see
[02 #1/#2](02-ux-design-checklist.md). Non-table/non-layout changes skip this one.

## Posting steps (per work item)
1. Set work-item **State = Done** (Task type supports it):
   `PATCH {org}/{project}/_apis/wit/workitems/{id}?api-version=7.0`
   `Content-Type: application/json-patch+json`  body `[{"op":"add","path":"/fields/System.State","value":"Done"}]`
2. Upload each PNG to the PR:
   `POST {org}/{project}/_apis/git/repositories/{repoId}/pullRequests/{prId}/attachments/{fileName}?api-version=7.1-preview.1`
   header `Content-Type: application/octet-stream`, `--data-binary @file`. Response `.url` = embed url.
3. Post ONE PR comment thread:
   `POST {org}/{project}/_apis/git/repositories/{repoId}/pullRequests/{prId}/threads?api-version=7.0`
   body: `{"comments":[{"parentCommentId":0,"commentType":1,"content":"<markdown>"}],"status":1}`
   Comment markdown MUST contain:
   - the requirement worked on (e.g. REQ-DACT-002),
   - the work-item id + link,
   - each screenshot embedded `![](<attachment url>)` with a SHORT caption line ABOVE it,
   - an **@mention** of the originator: `@<identity-GUID>` (see
     [04-accounts-and-azure-metadata.md](04-accounts-and-azure-metadata.md); Yujiao=UX, Tobias=tester).
4. For a NEW slice: same, but the comment goes on the newly created PR at complete-implementation
   time and leads with the requirement + screenshots + short description.

## If you believe the finding is WRONG (tester/UX are human too)
Don't silently skip it. After fully analysing and being confident it's not-a-bug, post a rebuttal PR
comment (link the work item + its requirement, cite evidence, @mention the originator) and set the
work item Done as a temporary "completed pending reply". Use the template in
[06-azure-devops-templates.md](06-azure-devops-templates.md) §7. Be respectful — they may be right.

## Ready-made command + comment templates
**Fastest path:** [`tools/scripts/post_to_pr.py`](tools/scripts/post_to_pr.py) does upload + captioned
comment (@mention) + set-Done in one run — fill its CONFIG. Raw REST calls (create ticket/PR/reviewers/
auto-complete/attachment/comment) and the proof-comment + rebuttal markdown templates live in
[06-azure-devops-templates.md](06-azure-devops-templates.md).

## After posting — cleanup is the LAST step (never before)
Cleanup runs ONLY once the proof/overlay comment(s) are **posted to the PR AND verified** (threads
exist, work item set). Until then, **do NOT delete or touch ANYTHING under `.memory/temp`** — the proof
PNGs live there, so even removing an *unrelated* scratch file/log there mid-flow risks (and looks like)
nuking the proof and wastes a re-shoot. Keep the whole `.memory/temp` intact through posting; do all
tidying at the very end. Then delete the proof PNGs + any throwaway `pages/__*.tsx` / Playwright scripts —
run [`tools/scripts/cleanup_proof.sh`](tools/scripts/cleanup_proof.sh) `[.memory/temp]` (wipes throwaway
preview pages + the `.memory/temp` workspace).

## Recurring reporting facts
- Org `https://dev.azure.com/HPS-AT-GenAI`, project `Post`. See metadata file for repoId/PR/GUIDs.
- Azure PR-comment @mention syntax is `@<GUID>` (identity id, not email).
