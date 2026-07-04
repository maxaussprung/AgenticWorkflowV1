# Playwright Proof Screenshots — the ONE working recipe (do NOT deviate)

> **Reuse first:** [`tools/scripts/proof_shots.py`](tools/scripts/proof_shots.py) already bakes in
> everything below (boot mocks, catch-all, 3-size capture) + reads [`tools/testdata/mocks.json`](tools/testdata/mocks.json).
> Copy it to the scratchpad, fill the two CONFIG blocks (page + page-mocks), run. Only read the rest of
> this file to understand/extend it or when a page needs new mocks. Keep the doc and the json in sync.
> Add **`--annotate`** for table/alignment-sensitive pages: it emits `*_annotated.png` — green/red column
> guides (`+Npx` when a header is offset) PLUS red **gap** lines with px labels (left/right page margins,
> inter-block gaps, bottom gap — for the UX designer) PLUS red **`CLIP Npx`** boxes for cut-off content
> (truncated labels/cells, or elements cut at the viewport edge) — and prints `ALIGNMENT: OK/MISALIGNED`
> + `gaps(...)` + `CLIPPING: OK` / `CLIPPED …`. The automated gate for the #1 recurring bug + spacing +
> cut-offs ([02 #1 + CLOSED LOOP](02-ux-design-checklist.md)); post it as the overlay comment (Yujiao). It
> is a **living gate — extend it whenever a new spacing/cut-off/alignment finding is learned** (02 step 2).

> **These route-interception mocks are for OFFLINE PROOF SCREENSHOTS ONLY.** They are NOT the
> `mock-implementation-slice` skill — that adds a real backend `Mock`-env adapter/seed so a human can
> click through the running Docker app. If the slice needs a real Mock for human testing, run that skill
> too; the Playwright mock never replaces it (see [05](05-slice-workflow.md)). Do BOTH where needed.

## GOLDEN RULES (each one cost us real time when ignored)
1. **DO NOT use MSW / `NEXT_PUBLIC_ENABLE_MOCK_SERVER=true`.** It is BROKEN in-browser here:
   msw 1.2.1 throws `response.headers.all is not a function`; `public/mockServiceWorker.js` is
   stale; and the built-in unpaid-count handler even uses the WRONG url (`/count/Unpaid`).
   Every minute on MSW is wasted. **Mock via Playwright route interception ONLY.**
2. **No backend needed.** Intercept every API call. Frontend: `pnpm dev` → http://localhost:3000
   (start/stop + free a stale :3000 with [`tools/scripts/dev_server.sh`](tools/scripts/dev_server.sh)).
   API base = `https://localhost:7098` (`.env.development`). Browser context: `ignore_https_errors=True`.
3. **Use the REAL pages** (no throwaway preview pages, no Redux seeding needed):
   - Change form: `http://localhost:3000/directive-order/59-5121/change`
   - Search page: `http://localhost:3000/directive-orders/search` → then click
     `[data-testid="directive-search-submit"]` (defaults pre-check all statuses+types, so the
     submit is valid) → the auto-scroll effect fires on loading true→false.
   - `NEXT_PUBLIC_ENV=development` is set → the `useRedirectRoute` guard is OFF, so these load directly.
4. **`restRequest` returns `{ data: <parsed body> }`.** So your route `fulfill` body = the RAW
   payload JSON shown below — do NOT wrap it in `{data:...}`.

## Endpoints hit on EVERY page (Layout → SessionInformation)
If ANY of these fails, you get BOTH toasts — "Failed to fetch" AND "Cannot read properties of
undefined (reading 'statusCode')" — because the error handler does `error.response.statusCode`
on a raw fetch failure. So mock all of them + add a catch-all.

| Method / URL | Fulfill body (raw) | Note |
|---|---|---|
| `GET /account/me` | `{"fullName":"Max Mustermann","organizationUnit":"Customer Support","role":"Admin"}` | left header column |
| `GET /directives/orders/Unpaid/count` | `165` | **BARE NUMBER.** An object body → "Objects are not valid as a React child" → SessionInformation crashes → blank page. (This exact bug cost ~1h.) |
| `GET /system/info` | `{"version":"1.0.0.0","currentDate":"2026-07-01T08:00:00.000Z","opalConnection":"offline"}` | `currentDate` MUST be valid ISO (`format.dateTime(new Date(...))`), else "Invalid Date". Shows "Opal: offline". |
| `GET /lookups/{key}?includeTranslations=true` | `[]` | 5 keys: customer-title-prefix, customer-title-suffix, customer-id-type, company-id-type, countries. Empty array is safe. |

## Page-specific endpoints
- **Change** `GET /directives/orders/59-5121` → `DirectiveOrderResponse`. Pre-fill reads
  `data.data.contact.{telephoneNumber,email}`; header reads `formulaNumber`, `type`,
  `customerIdentification.{firstName,lastName}`. Example body:
  ```json
  {"id":"59-5121","formulaNumber":"59/5121","type":"VacationPostOfficeBox",
   "validFrom":"2021-07-24T00:00:00Z","validTo":null,
   "customerIdentification":{"firstName":"Mara","lastName":"Karst"},
   "data":{"contact":{"telephoneNumber":"01/490526","email":"domenic55@gmail.com"}}}
  ```
- **Search** `GET /directives/orders/search*` → `{"items":[...],"count":7}`. Match `/search`
  BEFORE the generic `/{id}` route. Hit shape:
  `{id, formulaNumber, type, customerLastName, addressSummary, validFrom, validTo, status}`,
  status ∈ `Active|Expired|Future`. Give ~7 realistic rows (Urlaubs-Postfach, Nachsendeauftrag
  Ausland, Rechtsanwalt, Postfach Plus, Postfach Paket, Postfach Offen, Postfach Offen Plus).
- **Logdaten** (`http://localhost:3000/logdaten`, loads directly, fires `GET /audit-logs` on mount →
  wait for `[data-testid="logdaten-results"]`). Body `{"items":[AuditLogEntry],"count":N}`, reverse-
  chronological. `AuditLogEntry = {id, actor, action, targetEntityType, targetEntityId, summary,
  createdAt}` where `action ∈ Created|Changed|Cancelled` (rendered Angelegt/Geändert/Storniert) and
  `targetEntityType` is shown verbatim (e.g. `DirectiveOrder`). Columns rendered:
  Zeitpunkt(createdAt) / Benutzer(actor) / Aktion(action) / Objekt(targetEntityType) /
  Zusammenfassung(summary). Give ~7 rows (users like anna.huber@post.at / jonas.mayer@post.at,
  "Auftrag NNNN (…) angelegt/geändert/storniert"). Headers left-aligned via a DataTable
  `styleOverride` (fix `02c51113`) — the `--annotate` gate confirms OK.

## `--annotate` overlay: measure CONTENT-left, not cell-box-left (fixed 2026-07-02)
The overlay used to compare the header LABEL div's left (content-left, i.e. after the cell's 16px
left padding) against the body `td`'s BOX left (before its 16px padding). amarillo `MuiTableCell`
has 16px left padding on BOTH thead and tbody cells, so this apples-to-oranges compare reported a
phantom **`+16px` on EVERY column** even when the header text sits exactly over the body text →
false `MISALIGNED`. A uniform, identical offset on all columns is the tell-tale of this artifact
(a REAL misalignment varies per column). Fixed in `proof_shots.py`: a `contentLeft(el)` helper
now measures where each cell's TEXT actually starts (deepest non-blank text node via TreeWalker +
Range, fallback to first child element), and the overlay compares header content-left vs body
content-left. Verified on Logdaten: text-left is 80px for both header and body → offset 0 → `OK`,
green guides land on each column. If you see a constant offset equal to the cell padding, it's this
bug — do NOT report the page as misaligned.

**Empty-header columns (rowActions / checkbox) are NOT misalignment (fixed 2026-07-02).** An amarillo
`rowActions` column (icon-only, e.g. the "Öffnen" eye) or a select-checkbox column has NO header text,
so there is nothing to align to its body content — its icon centres in the cell and the overlay used to
report a spurious `MISALIGNED` on it (offset that *grows with viewport*, e.g. −12px@1280 → −32px@1920,
because the empty column widens). `proof_shots.py` now skips columns whose header label is blank from the
verdict (draws a neutral guide, not red). Verified on Offene Inkassofälle (REQ-COLL-001): the 5 real data
columns are green/`OK`; the leftmost icon-only action column no longer trips the gate. If the ONLY flagged
column has an empty header and a size-varying offset, it's this artifact — the data columns are aligned.

## Catch-all safety net (kills any stray toast)
Register a route on `https://localhost:7098/**`; for any URL you didn't explicitly handle,
`fulfill(status=200, body="[]", content_type="application/json")`. Log unmatched URLs so you can
add them. With the catch-all, nothing ever rejects → no toasts.

## Screenshots (per component / work item)
- Viewport **1280×1024** (min), viewport **1920×1680** (max), and **whole page** (viewport width
  1920, `page.screenshot(full_page=True)` → height varies to fit the page).
- Before shooting, `wait_for_selector` on the proof element (e.g. `[data-testid="change-cancel"]`
  for the change page; the Trefferliste table / a result row for search). Give the smooth-scroll a
  moment (`page.wait_for_timeout(800)`) so the after-scroll state is captured.

## Mandatory visual-pixel gate (DOM assertions are NOT enough)
Selectors and `expect(locator).to_contain_text(...)` can pass while the actual PNG is bad proof:
the relevant component may be tiny in a mostly blank frame, off-screen after a full-page capture,
hidden by layout, or rendered with text that is technically in the DOM but not useful in the image.
This happened on DTRF PR #1593: pre-fill assertions passed, but the posted 1920/full-page proof looked
nearly empty because the important Auftraggeber*in card occupied only a small top-left part of a huge
blank frame.

Before posting any proof screenshot:
1. **DOM gate:** wait for the exact element/text that proves the requirement.
2. **Pixel gate:** run [`tools/scripts/proof_pixels.py`](tools/scripts/proof_pixels.py) on a region around
   that element and require visible non-background pixels, e.g.
   ```powershell
   .\.venv\Scripts\python.exe .memory\tools\scripts\proof_pixels.py .memory\temp\shot.png --region "auftraggeber-card:60,230,700,260:0.02"
   ```
   Use the relevant component's bounding box or a tight manual crop region, not the whole blank page.
3. **Human image gate:** open the PNG and check that the caption's claim is obvious to a reviewer in
   the image. If the relevant proof is a small island in a sea of blank space, retake it framed better
   (scroll, crop/element screenshot, or add a close-up alongside the full-page context). Do **not** post
   a caption like "pre-filled" when the screenshot does not make that visually obvious.

The full-page context shot is still useful, but for sparse screens it is not sufficient by itself. Add
a close-up/viewport shot of the relevant region and pixel-check that region before attaching it.

## Minimal Playwright template (Python; venv: `Post/.venv/Scripts/python.exe`)
```python
from playwright.sync_api import sync_playwright
import json
API = "https://localhost:7098"
M = {  # exact-path → body (see tables above)
  "/account/me": {"fullName":"Max Mustermann","organizationUnit":"Customer Support","role":"Admin"},
  "/directives/orders/Unpaid/count": 165,
  "/system/info": {"version":"1.0.0.0","currentDate":"2026-07-01T08:00:00.000Z","opalConnection":"offline"},
}
def handle(route):
    p = route.request.url.split(API,1)[-1].split("?")[0]
    if p in M: body = M[p]
    elif p.startswith("/lookups/"): body = []
    elif p.startswith("/directives/orders/search"): body = {"items": SEARCH_ROWS, "count": len(SEARCH_ROWS)}
    elif p.startswith("/directives/orders/") and p.endswith("/change"): body = []  # n/a
    elif p == "/directives/orders/59-5121": body = DETAIL
    else: print("UNMATCHED", p); body = []
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(ignore_https_errors=True, viewport={"width":1280,"height":1024})
    pg = ctx.new_page(); pg.route(f"{API}/**", handle)
    pg.goto("http://localhost:3000/directive-order/59-5121/change", wait_until="networkidle")
    pg.wait_for_selector('[data-testid="change-cancel"]'); pg.wait_for_timeout(500)
    pg.screenshot(path=".../shot_change_1280.png")
    pg.set_viewport_size({"width":1920,"height":1680}); pg.wait_for_timeout(300)
    pg.screenshot(path=".../shot_change_1920.png")
    pg.screenshot(path=".../shot_change_full.png", full_page=True)
    ...
```

## How to render the CREATE entry mask for proof (seed-preview page — WORKS)
The create mask (`/directive-order/create/[orderName]`) only renders its form once Redux state
is set, so route-interception alone is not enough. Use a **throwaway seed-preview page** — it
renders inside the global Provider+Layout (`_app.tsx`), so `useAppDispatch` (from `store`) can seed
the slices, and gating render behind a `seeded` flag makes react-hook-form read the seeded
defaults. Confirmed working for the Personendaten field-order proof (UX #2196):
- File `src/pages/__preview_personendaten.tsx` (DELETE after). Seed on mount then render
  `<CreateDirectiveOrdersPage/>` (import from `components/createDirectiveOrdersPage`):
  1. `setDirectiveOrderHolderData({firstName:'Anna',surname:'Neumann',titlePrefix:'',titleSuffix:''})`
     (from `models/directiveOrder`) → pre-fills Vorname/Nachname (the form default reads
     `directiveOrder.data.directiveOrderHolderIdData`).
  2. `setSelectedDirectiveOrderType({id:'1',type:'LocalAbsence',name:'Ortsabwesenheit',code:'OA',
     colorCode:'#ffcc00',isEnabled:true,conflictsWith:[],subtypes:[]})` (from
     `models/directiveOrdersTypes`) → non-null `selectedType` ⇒ FormWrapper renders. **Pick a
     CLEAN code** — `OA` avoids PF/NSA/dropoff/new-destination/roommates-unsupported branches so
     the fewest sub-sections render.
  3. `setSettings({allowedFrom:'2026-07-01T...', defaultFrom:..., maxFrom:..., defaultTo:null,
     maxTo:null, maxNumberOfCustomers:1, maxNumberOfCompanies:0, preferredTo:[], customerType:null})`
     (from `models/createDirectiveOrder`) → **non-empty `allowedFrom` ⇒ CreateDirectiveOrderForm
     renders**.
  - `differentOrderHolderType` defaults to `null` ⇒ treated as private customer ⇒ the
    Antragsteller/Personendaten block + Online-Kundensuche render (no seeding needed).
- **getStaticProps namespaces**: copy the list from `pages/directive-order/create/[orderName]/index.ts`
  AND add `'personendaten'` (a TOP-LEVEL namespace the real page's list omits) — else the four
  field labels render as raw keys (`personendaten.title` etc.). Titel dropdowns show "Auswählen".
- The mask auto-fires the §11.8.1 Online-Kundensuche on the seeded name → `GET
  /contacts/pum-identification?...`; the catch-all `[]` answers it (shows "Keine Übereinstimmung
  gefunden"). No extra mock needed.
- Warm the route once (`curl http://localhost:3000/__preview_personendaten`) so Next dev compiles
  it before Playwright navigates. Wait for `[data-testid="personendaten-information"]` +
  `[data-testid="person-title-prefix"]`. To read pre-filled input values in Playwright use
  `page.input_value(sel)` (the live DOM value), NOT `get_attribute('value')` (stale HTML attr).

### Seed a NID (out-of-area redirection) create mask — for Formulardaten + Bisherige-Adresse proofs (verified 2026-07-02)
Same seed-preview recipe, but seed an **NSA parent + NID sub-group** instead of OA so both the
`FormulardatenBlock` (`data-testid="formulardaten-block"`) and the context-dependent
**Bisherige Adresse** heading + address fields render (`DirectiveOrderPreviousAddress`,
`data-testid="previous-address"`). Address blocks render only when the **parent** `code ∈
HAS_NEW_DESTINATION_ADDRESS = ['NSA','NID','NAD']`; `isOfTypeInland`/`isOutOfArea` derive from the
**sub-group** (`DomesticRedirection`=NID). Seed (all from the same models as above):
  1. `setSelectedDirectiveOrderType({id:'nsa-parent-id',type:'NSA',name:'Nachsendeauftrag',code:'NSA',isEnabled:true,conflictsWith:[],colorCode:'#0000FF',subtypes:[]})` — parent code NSA ⇒ address blocks render.
  2. `setSelectedDirectiveOrderSubtype({id:'nid-sub-id',type:'DomesticRedirection',name:'Nachsendeauftrag Inland',code:'NID',isEnabled:true,conflictsWith:[]})` — Inland + out-of-area ⇒ "Bisherige Adresse".
  3. `setSettings({...allowedFrom:'2026-07-02'...})` (non-empty allowedFrom ⇒ form renders).
  4. `setCreateDirectiveOrderShipmentTypes({directiveId:'nid-type-id', shipmentTypesGroupResponses:[{id:'Briefe',name:'Briefe',isChoosable:false,translations:{'en-US':{name:'Briefe'},'de-AT':{name:'Briefe'}}}, ...]})` — populates the Formulardaten `ShipmentTypes` control (this action APPENDS one group; call once).
  - Exact NID fixture lives in `createDirectiveOrderForm/__tests__/CreateDirectiveOrderForm.test.tsx` (`nidState`).
  - **`setSelectedDirectiveOrderSubtype` + `setSelectedDirectiveOrderType`** are in `models/directiveOrdersTypes`; `setSettings` + `setCreateDirectiveOrderShipmentTypes` in `models/createDirectiveOrder`.
- Wait for `[data-testid="formulardaten-block"]`; use `scroll_to: '[data-testid="previous-address"]'`
  to bring the Bisherige-Adresse section into the viewport for the `--annotate` overlay.
- **STALE testid (self-heal):** the memory-00 OA recipe above says wait for
  `[data-testid="personendaten-information"]` — that testid does NOT exist on the current create
  mask (feat branches mid-2026); the mask renders the form directly (Nachsendegrund / Formulardaten
  / addresses / Erreichbarkeit), no separate "Personendaten" block. `personendaten` is also not a
  top-level namespace (harmless — `pick` drops missing keys). Wait for a control that actually
  renders (`formulardaten-block`, `previous-address`, or `create-directive-order-next-button`).

## How to prove "Neu erfassen" pre-fills a new directive from an existing one (DTRF — REAL flow, no seed page)
The DTRF prefill (PR #1593, REQ-DTRF-002 Case 2; if someone says #5193, that was a typo observed
2026-07-02 — Azure returns 404, `openspec/track.md` and the PR title resolve to #1593) is best proven end-to-end with route interception —
NO seed page needed. Each search Trefferliste row has a **"Neu erfassen"** button
(`data-testid="create-new-order-{index}"`, label `directiveSearch.newEntry`) beside "Ansehen".
Clicking it dispatches `prefillFromExistingDirective(id)` (`models/directivePrefill`) → `GET
/directives/orders/{id}` → maps the source (`mapSourceDirectiveToPrefill`) → seeds the
`directiveOrder` slice via its own setters (holder id, different-holder, KCRM address) → `navigate('/directive-orders')`.
Recipe (verified 2026-07-02):
  1. Go to `/directive-orders/search`, click `[data-testid="directive-search-submit"]`, wait for `[data-testid="create-new-order-0"]`, scroll `[data-testid="trefferliste-results"]` into view, then shoot the Trefferliste (shows the "Neu erfassen" column). At 1280 the table is below the fold without the scroll, so an unscrolled screenshot proves only the search mask.
  2. Mock `GET /directives/orders/{rowId}` to return a `DirectiveOrderResponse` (`services/directiveSearch/types.ts`) with `customer`/`customerIdentification` (→ Auftraggeber*in name) and `newAddress` {postalCode,city,street,houseNumber,staircase,doorNumber} (→ address line). `owner` optional (→ Abweichende*r).
  3. Click `create-new-order-0`, `page.wait_for_url("**/directive-orders")`, then shoot: the landing shows the **pre-filled Auftraggeber*in card** (e.g. "Mara Karst" + "1010 Wien, Ringstrasse 1 / 2 / 5") with an "Abweichende*r Auftraggeber*in" checkbox + "Weiter". The store persists across the SPA navigation, so route interception alone reproduces the whole flow (no backend, no seed page). For AC-4 ("Auftraggeber*in-Daten eingeben" when not prefilled), capture `/` where `CaptureIdDataButtons` is mounted; direct `/directive-orders` shows the blank card + checkbox/Weiter, not that button. Scripts kept in the scratchpad (`proof_dtrf.py`) — not a reusable tool.
  4. **Do the pixel gate** on the Auftraggeber*in card region before posting. The card can be present but visually too small inside a mostly blank 1920/full-page frame; include a tighter viewport/region proof if the full-page shot looks empty.

## Overlay + PIXEL-VERIFY a FORM's alignment & gaps (verified #2209 — the UX double-check)
For a form finding (alignment to a sibling column, 16px/48px gaps) `proof_shots.py --annotate` (built for
tables) isn't enough — measure the form directly and draw a form overlay. This is the DOUBLE-CHECK that
catches a misalignment you'd never spot by eye (it caught the ChooseOrderHolder body sitting ~29px right
of the card above). Recipe (a scratchpad script, e.g. `.memory/temp/proof_<id>.py` — case-specific, not a
reusable tool):
1. Drive to the screen (real flow / route-interception as usual), then in `page.evaluate` collect
   `getBoundingClientRect()` (rounded) for: the upper section's left reference (the sibling section
   title/card), the form title's `.MuiGrid2-container` (`titleEl.closest('.MuiGrid2-container')` — the
   title BLOCK, not the text, so the margin is included), the **fields-container CHILDREN**
   (`[...document.getElementById('<form>-fields').children].map(rect)` = one rect per field row/column —
   reliable, unlike climbing from an input), and the action row / `[data-testid="back-button"]`.
2. **PRINT the numbers and assert** (don't hallucinate): left-edge deltas `formTitle/firstField/backBtn.left
   − upperTitle.left` (align = each `|Δ|≤2px`); gaps `firstField.top − titleGrid.bottom` (title→field),
   `next.top − prev.bottom` (field→field), `child2.left − child1.right` (columns), `backBtn.top −
   lastField.bottom` (field→actions) — compare to the spec (e.g. 16/16/16/48).
3. Inject overlay `<div>`s (absolute, high z-index, `+ window.scrollX/Y`): a GREEN vertical guide at the
   upper-section left edge run down through the form; a GREEN tick + `Δ+0px` at each aligned left edge (RED
   + the delta if not); RED dashed gap lines with `Npx` labels for each measured gap. Screenshot the
   annotated version at 1280/1920/full.
4. **Read the annotated PNG** and confirm the guide passes through every block's left edge and the gap
   labels read the spec values — post it as the UX overlay comment (Yujiao). Bank any new finding here +
   [02](02-ux-design-checklist.md) (CLOSED LOOP).

## Always verify each PNG (Read tool) before using it
No red toasts; yellow header populated (name/role/date/version/Opal offline/count). If a toast
appears, an endpoint wasn't intercepted → check `UNMATCHED` prints / browser console for the url.
The two toasts to hunt for: **"Failed to fetch"** and **"Cannot read properties of undefined
(reading 'statusCode')"** — both mean an un-mocked call; a screenshot with either MUST be retaken.
Also reject screenshots where the relevant proof is not visually obvious even if the DOM assertion
passed. Run the pixel gate above and open the image; both must agree before posting.

## If you ever render against the REAL backend (not route-interception)
Prefer route interception (above) — no backend, no cert issues. But if a proof genuinely needs the
live Mock stack: first open the API/swagger URL (https://localhost:5001/docs/index.html) in the
browser context once and accept/trust the self-signed cert (or launch with `ignore_https_errors=True`),
otherwise every call fails → the two toasts. For Typesense "not found"/stale after a restart, run the
reset in [03-local-setup-and-infra.md](03-local-setup-and-infra.md).
