# UX / Design Review Checklist (be critical BEFORE posting proof)

The UX colleague (Yujiao Li) will flag these — catch them first to save a round-trip.

## CLOSED LOOP — every spacing / margin / gap / cut-off / alignment finding feeds BOTH this file AND the overlay (guardrail)
This is the **spacing/cut-off specialization** of the universal [every-fix-flow-finding-becomes-a-learning
core rule](README.md#core-rule--every-fix-flow-finding-becomes-a-learning-ux-tester-or-any-source) — same
"bank it because it was wrong", plus the extra overlay step (2) below. It is a governing rule for the whole
flow (new slice AND fix flow), so the agent never drifts: when a
UX finding is about **margins, gaps, spacing, cut-off/clipping/overflow, or alignment of ANY sort**
(from Yujiao, from a tester, or caught in review), you MUST do all three, in this order:
1. **Record it here** — add it to the "Known past UX/tester findings" list (and, if it's a new class of
   defect, its own `## #N` section) with the **exact expected value** (e.g. "24px gap", "no clip at 1280",
   "header over column data") and the fix that satisfies it. So the next slice avoids it up front.
2. **Teach the overlay to catch it** — extend [`tools/scripts/proof_shots.py`](tools/scripts/proof_shots.py)
   `--annotate` (`ANNOTATE_JS`) so that measure is **highlighted/labelled from then on** (a guide, a px
   label, or a flag in the `MISALIGNED/CLIPPED/…` verdict). The overlay is a living gate: each learned
   spacing/cut-off defect becomes an automatic check, so eyeballing can't miss it again. Keep the doc
   ([00](00-playwright-proof-howto.md)) and the script in sync.
3. **Re-prove it in the fix response** — the fix-flow overlay comment (see [01](01-proof-reporting-protocol.md))
   MUST show the **new annotated** screenshot proving the specific measure is now correct (the gap is now
   24px / nothing is clipped / the header sits over its column). Screenshots alone aren't enough for a
   spacing/cut-off fix — the overlay is the proof it's actually fixed.

If a finding is spacing/cut-off/alignment and you did NOT extend the overlay, you are off track — do step 2
before closing it.

## #1 RECURRING BUG — amarillo DataTable header alignment (bitten us 4×) — STOP AND CHECK
Every amarillo `DataTable` centres its header labels by default → headers float centred over
left-aligned data. **This keeps recurring because the fix is NOT obvious:**
- The column **`align: 'left'` prop does NOT left-align the header label** — it only affects the CELL
  (body) content. Setting `align:'left'` and thinking you're done is the exact trap (Logdaten table,
  #2180, shipped centred headers despite `align:'left'`).
- The header label lives in an inner `div` inside `.MuiTableCell-head`; you MUST target it via
  **`styleOverride`**. Put this on EVERY `<DataTable>` (copy verbatim):
  ```tsx
  styleOverride={{ root: { '& .MuiTableCell-head > div': { justifyContent: 'flex-start' } } }}
  ```
  (Merge into an existing `styleOverride.root` if the table already has one — see the zebra/white-card
  and action-button rules below.) Then MEASURE/screenshot: header text must sit directly above its
  column data at BOTH 1280 and 1920. `measure-amarillo-spacing` can confirm. No exceptions — a
  DataTable without this override is a defect.
- **PROOF-REVIEW GATE (why #2180 still shipped centred):** when you review ANY table screenshot, do
  NOT just claim "headers aligned" — actually LOOK: trace each header label straight down; it must sit
  directly over its column's data (left edges matching). A centred/offset header = the styleOverride is
  missing. If unsure, open a known-good table for comparison (PUM Personendaten, or the directive-search
  Trefferliste) and match them side by side. #2180 shipped because the agent used `align:'left'`,
  asserted "left-aligned" without checking, and never compared to an existing table. Compare-to-known-good
  is mandatory for tables.
- **AUTOMATE the gate:** run the proof with [`tools/scripts/proof_shots.py`](tools/scripts/proof_shots.py)
  **`--annotate`** — it overlays a guide at each table column's data-left (**green** when the header aligns,
  **red + `+Npx`** when offset) AND draws **red gap lines with px labels** for the UX designer: the
  left/right page margins, the vertical gaps between stacked top-level blocks, and the gap to the page
  bottom. It prints `ALIGNMENT: OK` / `MISALIGNED …` + the measured `gaps(...)`. Treat MISALIGNED as a
  blocker; post the `*_annotated.png` as a separate PR comment ([01](01-proof-reporting-protocol.md)). This
  turns the eyeball check into numbers the agent can't fudge. (Uses `contentLeft` text-vs-text compare so
  the 16px MuiTableCell padding doesn't report a phantom offset; empty-header rowActions/checkbox columns
  are excluded.) It **also flags cut-offs**: a red `CLIP Npx` box + a `CLIPPED` verdict when text is
  truncated inside its box (ellipsis/overflow) or an element is cut at the viewport edge. Per the CLOSED
  LOOP rule above, extend this overlay whenever a new spacing/cut-off/alignment finding is learned.

## #2 RECURRING BUG — form gaps: 24px, and pick the RIGHT gap mechanism
Amarillo has NO layout/spacing layer, so gaps between fields/sections are the app's job via
`common/constants/spacing.ts` **FORM_SPACING** tokens (literal px): `FIELD_GAP` **24px** (between input
fields), `SUBMIT_GAP`/`SECTION_GAP` **24px** (field row → button / → next section), `GROUP_GAP` 24px,
`INLINE_GAP`/`CHECKBOX_LABEL_GAP` 8px, `NOTE_GAP` 4px, `HEADING_TOP` 16px, `HEADING_TO_FIELDS` 0.35em.
Target **24px** between fields and above the submit/button row (matches every other form).
- **MUI `columnSpacing`/`rowSpacing` use amarillo's 4px base unit** (NOT 8px): `={6}` = **24px**,
  `={4}` = 16px, `={2}` = 8px. Logdaten filter first shipped `={4}`/`={2}` (16px/8px — too small).
- **Full-width field rows → use MUI `columnSpacing={6}`/`rowSpacing={6}` (24px), NOT CSS `gap`.** MUI
  spacing is width-accounted, so a full 12-column row (e.g. 4+4+2+2) stays on ONE line; a CSS `columnGap`
  is ADDED on top and overflows → a field wraps to the next row (`Bis` wrapped at 1280 when we tried CSS
  gap). Reserve CSS `gap`/`columnGap` (`FORM_SPACING.FIELD_GAP`) for a NON-full row like `SearchMask`
  `fieldsGrid` (md:3×3 = 9 cols, room to spare); use margins for vertical block rhythm.
- Verify with `proof_shots.py --annotate` (it labels the horizontal gaps between input controls + the
  row→button / block→table gaps in px) and cross-check against SearchMask/PUM. Use `measure-amarillo-spacing`.

### Build EVERY new form/page right the FIRST time (defaults — so it isn't a re-test finding)
- **Left-align the content column with sibling sections.** All stacked blocks on a page (header/session
  bar, a card section, a form) must share ONE left edge. The app column is **90% width, centered**
  (`upperSectionContainer` → left at 5% of viewport). A form nested in `TitleWrapper` lands at **7.25%**
  (its `container` is `width: md 95%` + `alignItems:center`, so its 90% child is 90%-of-95% centered) →
  ~29px right of a card above it = a misalignment the UX reviewer WILL flag (#2209). Fix by passing
  `TitleWrapper`'s optional `containerStyles={{ width: '100%' }}` for that screen (its 90% children then
  center to 5%); never widen the shared `TitleWrapper.container` globally. **Verify left edges are equal
  in px** (measure `getBoundingClientRect().left` of each block — don't eyeball), see the form-overlay
  recipe in [00](00-playwright-proof-howto.md).
- **Bottom action row = REUSE `BackButton`(secondary+`reverse`, left) + `SubmitButton`(right)** on one
  baseline, spanning the field column — copy `CreateDirectiveOrderForm`'s `actions`/`backButtonInline`/
  `submitButtonInline` (see [09](09-frontend-patterns.md)). Give the kept submit an explicit `testId`.
- **A reviewer's explicit per-screen value overrides the 24px default** (e.g. Yujiao's #2209: 16px field/
  column gaps, 48px field→action-row). Honor it as literal px with a `// #<ticket>` comment; use a single
  CSS `gap` on the fields container for BOTH row+column, and put the 48px on the action ROW (not the button).

## Repo design tooling
- Skill **`measure-amarillo-spacing`** (`.agents/skills/measure-amarillo-spacing/`) — use it to
  verify gaps/margins/paddings match amarillo spacing tokens. Read it before judging spacing.
- UI kit: `@postag/amarillo.ui` (MUI-based). Prefer amarillo components + spacing scale (theme
  `spacing()` / `gap`, `padding` numeric steps) over ad-hoc px.

## Hard checklist (reject the screenshot / fix the code if any fail)
- [ ] **DataTable head vs body alignment** — amarillo `DataTable` centres header labels by default;
      every table needs a `styleOverride` left-aligning `.MuiTableCell-head > div` so headers sit
      over their column data. (Recurring issue — see also global memory amarillo-datatable-header-alignment.)
- [ ] **No cut-off content** — buttons/labels/action columns fully visible, not clipped at the
      viewport edge or inside a container (check the 1280 width especially).
- [ ] **Content aligns to the yellow session header** — page content left/right edges line up with
      the `sessionInformationBox` (width 90% / margin auto). (This was work item #2190.)
      GOTCHA: use `margin: '0 auto'`, NOT `margin: 'auto'` — page containers are flex children of the
      full-height `main`, so plain `auto` also centres VERTICALLY → big empty gap under the header.
- [ ] **No huge vertical gap under the header** — short pages must sit top-aligned, not floating
      centred (see the margin gotcha above).
- [ ] **Header/typography sizes** — headings use the correct amarillo variant (h3 page title, h4
      section, h5 sub) — not oversized/undersized vs siblings.
- [ ] **Gaps/margins consistent** — spacing between sections/cards/fields matches our other pages
      and the amarillo scale; no cramped or oversized gaps.
- [ ] **Button semantics** — icon matches intent (cancel/abort = `close`/X, forward/next = arrow).
      (Work item #2191: cancel had a forward arrow.)
- [ ] **Responsive** — the 1280 and 1920 shots both look intentional (no overflow, no giant empty
      gutters, no wrapping that breaks layout).
- [ ] **Proof image relevance / blank-frame check** — the screenshot must make the caption's claim
      visually obvious. A DOM assertion is not proof if the PNG is mostly empty space or the relevant
      component is a tiny top-left island. Run `proof_pixels.py` on the component region and add a
      close-up/region shot when the full-page context is too sparse.

## Verify note-by-note (no slip-ups)
Check the ticket/requirement **detail by detail** — an exact "16px" gap, a named label, a field order,
a status, a specific value. Confirm EACH against the running UI/proof, not "looks about right". One
missed detail = a full extra round-trip (UX/tester re-tests → flags → re-fix → re-verify → re-test).

## If a defect is found
Start the fix flow: identify what's wrong + which design/style it violates → spawn a fix agent →
re-verify → re-proof → THEN post the PR comment. Do not post proof of a half-right screen.

## amarillo DataTable — remove the white "card" surface but KEEP zebra (UX #2197, REQ-DACT-003)
The amarillo `DataTable` has **NO Paper wrapper**. Its `TableContainer` (`.MuiTableContainer-root`)
and the outer `MuiBox-root` are **already `background: transparent`** — do NOT waste time hunting a
`.MuiPaper-root`; there isn't one. The "white card" look comes entirely from the **cells**:
- Header cells `thead .MuiTableCell-head` render **white** (`#fff`) — plus an inner white `div`.
- `variant='zebra'` colours the **cells** (not the `<tr>`): white band vs `#F1F4F5` (== the page bg
  `layout/styles.ts` container). The cell (`td`/`th`) carries the colour, so overriding the `<tr>`
  bg alone does nothing — target the cells.

Working `styleOverride.root` (verified via live DOM inspection at 1280/1920):
```
'& thead .MuiTableCell-head': { backgroundColor: 'transparent' },
'& tbody tr:nth-of-type(odd) .MuiTableCell-body':  { backgroundColor: 'transparent' }, // white band → page gray
'& tbody tr:nth-of-type(even) .MuiTableCell-body': { backgroundColor: '#E4EAEC' },     // keep a legible stripe
```
Why the `#E4EAEC` on the even band: the two zebra bands were white / `#F1F4F5`; turning white →
transparent makes it the page gray, so BOTH bands become gray and striping vanishes. Re-tone one
band (a touch darker than the page) to keep visible zebra without any bright-white surface.

**Alignment was ALREADY correct** on the real 90%-width page (`DirectiveOrderSearchPage.pageContainer`
is width 90% / margin auto; TrefferListe `container` is width 100%): measured TableContainer
left=64 right=1216 == the yellow `sessionInformationBox` left=64 right=1216.

### Action buttons MUST fit the 90% container at 1280 (no h-scroll, no clipped label) — UX #2197
REQ-UI-001 MIN width = 1280×1024 → container ≈ 1152px (90%). The `<table>` must be ≤ container width.
Verify by MEASURING: `tableWidth <= contWidth`, `TableContainer.scrollWidth <= clientWidth+1`, and every
action button's `getBoundingClientRect().right <= container.right`. Two-button Aktionen columns overflow:
- amarillo's default row-`button` width is ~320px; **11rem overflowed** (`<table>`≈1288px, "Stornieren"
  **clipped** at the right edge + horizontal scroll). **8rem still overflowed** (table 1192 > 1152).
- **`6.5rem` (104px) makes the table land exactly at 1152** (fits, no scroll) — BUT a fixed narrow
  width alone then **truncated the LABEL** to "Ansehe"/"Stornie…". Why: an amarillo secondary `Button`
  is `[ <div>label</div> | <div><svg>→arrow</svg></div> ]` with emotion-hashed classes (e.g. `css-56sg73`,
  NOT MUI `.MuiButton-endIcon` — that selector does nothing). The trailing arrow ate the text box.
- **WORKING fix** (verified 1280 + 1920: labels full, no scroll, no clip):
  ```
  '& tbody button': { width: '6.5rem !important' },
  '& tbody button > div:has(svg)': { display: 'none' },   // hide arrow (hashed class → target by :has(svg))
  '& tbody button > div': { overflow: 'visible', textOverflow: 'clip', whiteSpace: 'nowrap' }, // stop label ellipsis
  ```
  Do NOT use `width:'auto'` — that lets amarillo's ~320px default back in and blows the table to ~1576px.
  Dropping the row-action arrow also matches #2191 (a row action is not a forward/next affordance).
- Otherwise alignment is fine: the `<table>` can be wider than the container ONLY if it scrolls; the goal
  is to size the action column so the whole table fits WITHOUT scroll at 1280.

## Known past UX/tester findings (avoid repeating)
- #2190 content not aligned to header → constrain page container to width 90% / margin auto. **BUT**
  on a *short* page use `margin: '0 auto'` (horizontal only), NOT `margin: 'auto'`: the shared
  `layout.main` is `display:flex; flex:1 0 auto`, so a full `margin:auto` child also centres
  *vertically* → a big empty gap under the yellow header (hit on the Logdaten view #2180, fixed by
  `margin: '0 auto'` in `components/logdaten/styles.ts`). The search page hides this only because its
  content is tall enough to fill the space.
- #2191 cancel button had forward arrow → `icon='close'`.
- #2209 ChooseOrderHolder / "Daten des Auftraggebers eingeben" (directive-orders company & person
  order-holder forms). Four findings: (1) DUPLICATE top "Weiter" — the pre-fill flow
  (`models/directivePrefill`) sets `differentOrderHolderType` WITHOUT `hasDifferentOrderHolder`, the
  ONLY state where the top Weiter AND the company/person form both render; gate the top button on
  `!hasDifferentOrderHolder && !differentOrderHolderType` so the normal default path (type=null) still
  advances. (2) Move Weiter to the form BOTTOM inside an action row (reuse `BackButton` +
  `SubmitButton`, copy `CreateDirectiveOrderForm`'s `actions`/`backButtonInline`/`submitButtonInline`),
  add `Zurück` (Amarillo `secondary` + `reverse`) to its LEFT. (3) Screen-specific spacing — 16px (NOT
  the app-default 24px `FORM_SPACING.FIELD_GAP`): 16px title→first field, 16px between field rows AND
  columns; use a single CSS `gap:'16px'` on the fields `Grid2 container` for both row+col (drop
  per-field margins and `justifyContent:'space-between'`), and override `TitleWrapper`'s title
  `marginBottom` to `'16px'` via the screen's `customStyles` (don't touch shared TitleWrapper). 48px
  last-field→action-row via `marginTop:'48px'` on the row (not the button). (4) Content column — the
  body MUST left-align with the "Auftraggeber*in" section above (the reviewer catches a mismatch fast).
  Root cause: `TitleWrapper.container` is `width: md 95%` + `alignItems:center`, so its 90% children land
  at **7.25%** of the viewport, while the upper section (`upperSectionContainer` width 90%, centered)
  sits at **5%** → body ~29px right of the card. FIX (shared-safe): give `TitleWrapper` an OPTIONAL
  `containerStyles` prop (defaults `{}` → LandingPage / KcrmDirectivePersonData / DirectiveOrdersTypes /
  DomesticAddressSearch unaffected) and pass `{ width: '100%' }` for THIS screen so its 90% children
  center to 5% = the same column as the card. Pixel-verified: `upperTitle/formTitle/Firma/Zurück` all
  `left=64px` @1280 (Δ0). Testids for proof: top Weiter `directives-submit-button` (hidden in prefill),
  bottom Weiter `order-holder-submit-button`, Zurück `back-button`. See the general alignment rule below.
- #2194 search gave no feedback → auto-scroll Trefferliste into view on search completion.
- DACT-change Finding 2: detail page crashed on `data.status` (GET-by-id omits status) → guard it.
- Phone validation too strict → allow spaces `/` `-` and leading `+`.
- #2180 Logdaten table headers centred (`align:'left'` prop, no styleOverride) → add the styleOverride (#1);
  and Logdaten filter gaps 16px/8px (MUI `columnSpacing`/`rowSpacing`) → FORM_SPACING 24px via CSS gap (#2).
- DTRF Trefferliste "Neu erfassen" (PR #1593): the result table needs the same DataTable header
  `styleOverride` **and** compact two-button action styling at 1280. Without it, the Aktionen column
  clips off-screen and only "Ansehen" is visible. Working pattern: lower `.MuiTableCell-root` minWidth,
  set `tbody button` to a compact fixed width, hide the `div:has(svg)` arrow, and keep labels
  `whiteSpace:'nowrap'`; then re-run `proof_shots.py --annotate` with the Trefferliste scrolled into view.
- DTRF prefill proof (PR #1593): the Auftraggeber*in card DOM/text can be correct while the posted
  1920/full-page screenshot looks almost empty because the important card is small in a huge blank frame.
  Do not rely on DOM assertions + a casual glance. Pixel-check the card region with `proof_pixels.py`,
  and post a tighter viewport/close-up proof when the full-page context does not visibly communicate
  the pre-filled data.
- #2179 (add Bisherige/Neue Adresse to PUM & SAM) → **REBUTTED (finding was wrong)**. Directive-type
  facts worth keeping: **PUM = Paketumleitung Dauerhaft** (parcel redirection) — NOT Postvollmacht
  (that's `PV`). PUM has **no manual address**: its target is the linked **Level-90 online customer**
  (REQ-PUM-002, via Online-Kundensuche), and the backend payload `PermanentRedirectionParcelsDataPayload`
  carries only `promoCode`+`ssoCustomerNumber`. Address sections render only for
  `HAS_NEW_DESTINATION_ADDRESS = ['NSA','NID','NAD']` (both Bisherige+Neue render together, gated by that
  set in `CreateDirectiveOrderForm`). **SAM = CollectiveDomesticRedirection** — create mask not built yet
  (absent from `OrderDataPayload`); addresses there belong to building SAM, a separate requirement.
  Directive code↔type map: NID=DomesticRedirection, NAD=ForeignRedirection, SAM/NSA=CollectiveDomesticRedirection,
  PV=PostalAuthorization(Postvollmacht), ASG=DropOffAuthorization, PUM=PermanentRedirectionParcels (see `services/saveDirectiveOrder/enums.ts`).
