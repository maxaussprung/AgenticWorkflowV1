# Frontend Patterns & Gotchas (Next.js + Redux + redux-observable + amarillo)

Distilled, verified recipes for adding frontend features to `csharp/src/frontend`. Complements the
frontend `AGENTS.md` and the UX checklist ([02](02-ux-design-checklist.md) — read that FIRST for table
header alignment / gaps / `margin: '0 auto'`). Reason from this instead of re-deriving the layout.

## REUSE existing components — never re-implement one (core rule)
Before building ANY UI element, **grep for an existing component that already does it** and use it — do
not hand-roll a parallel one. This is the [README no-double-implementation core rule](README.md#core-principle--no-double-implementation-clean-architecture-follow-the-repos-own-guidelines)
applied to the frontend. It bit us on the Personendaten mask: the agent built the Titel field as a plain
text `<input>` when a **title dropdown component already existed** (title-prefix / title-suffix are
lookup-backed selects, `data-testid="person-title-prefix"`). Applies to ALL components — a Titel/anrede
dropdown, address fields, date pickers, the amarillo `DataTable`, form wrappers, buttons, the customer
search, etc. How to check fast: `Grep pattern="<concept>" glob="*.tsx"` under `src/components/`, and skim
`components/index.ts` (the barrel) — a matching component almost always exists. Reusing it also keeps the
look, validation, i18n and lookup wiring consistent (and passes UX review the first time).

## VERIFY the amarillo component API before using it — its props/variants are LIMITED
amarillo (`@postag/amarillo.ui`) repeatedly surprises with missing/renamed API. Before wiring a component,
check what it actually supports (its types / an existing usage) rather than assuming MUI parity. Confirmed
limits: `Typography` has **no `h6`** (caps at `h5`); there is **no `Alert`** export; `DataTable` has **no
`onRowClick`** and its custom action-cell button loses onClick → use `rowActions` (all detailed below);
`InlineMessage` variants are only `default|info|highlight`. If a requirement names an element amarillo
can't provide (e.g. a Typography `h6`), that is a **limitation to surface** — see the 4th "limitations"
PR comment in [01](01-proof-reporting-protocol.md).

## Read-only list screen — the vertical slice (VERIFIED on Offene Inkassofälle / REQ-COLL-001)
A GET-list screen (fetch on mount → amarillo `DataTable` → row drill-down) mirrors the SamImports /
searchBar models. Files + wiring, in order:
1. **Service** → `services/<feature>/service.ts`: `export const getXRequest = () => restRequest('/path')`
   (from `services/api`; it returns `{ data: <parsed body> }`). `types.ts` mirrors the backend DTO
   (camelCase). `index.ts` re-exports both.
2. **Model** → `models/<feature>/`: `slice.ts` (`createSlice`; state `{ items, loading, error?, hasLoaded }`),
   `actions.ts` (`effectActionCreator(slice.name)` → a `fetchX` effect action; re-export slice reducer
   actions), `epics.ts` (`combineEpics` of fetch/succeeded/failed — see the exact shape below),
   `selectors.ts`, `types.ts`, `index.ts` (`export *` from all).
3. **Register** the reducer in `store/rootReducer.ts` and the epics in `store/rootEpic.ts`.
4. **Component** → `components/<feature>Page/`: `constants/` (header msg-keys + a `detailRoute(id)` fn),
   `columns.tsx`, `styles.ts`, `<Feature>Page.tsx`, `index.ts`. Barrel-export from `components/index.ts`.
5. **Page route** → `pages/<path>/index.ts`: `export default <Feature>Page` + `getStaticProps` picking the
   i18n namespaces (`app, error, locale, sessionInformation, <feature>`). Reachable by URL — there is NO
   app menu (the search page has no menu entry either; `layout/.../navigation` is locale-switch only).
6. **i18n** → add the `<feature>` namespace to BOTH `translations/de/common.json` AND `en/common.json`
   (test-utils renders with the EN file, so tests assert EN labels).

### Epic shape (fetch on mount)
```ts
const fetchXEpic: Epic = (a$) => a$.pipe(filter(fetchX.match),
  mergeMap((action)=> concat(of(startX()),
    of(action).pipe(effect(()=>getXRequest(), fetchX)))));
const okEpic: Epic = (a$) => a$.pipe(filter(fetchX.succeeded.match),
  mergeMap(({payload}:{payload:{data:Row[]}})=>[successX(payload.data)]));
const failEpic: Epic = (a$) => a$.pipe(filter(fetchX.failed.match),
  mergeMap(({payload:{statusCode,message='Not Found'}})=>[errorX(message), apiError({statusCode,message})]));
```
Component dispatches `fetchX()` in a `useEffect([...])` on mount; `navigate({url})` (from `core/models`)
routes (the `navigationEpic` in `coreEpic` turns it into `router.push`).

## GOTCHA: amarillo `DataTable` has NO `onRowClick`, and a custom action-cell button LOSES its onClick
Verified the hard way on Offene Inkassofälle:
- **No `onRowClick` / `onRowSelect` prop** exists on amarillo `DataTable`. For a clickable ROW, delegate:
  put `onClick` on a `<Box>` wrapping the DataTable, in the handler do
  `const tr = (e.target as HTMLElement).closest('tbody tr')` then map `indexOf` in `tr.parentElement.children`
  to your `data[index]`. (jsdom lays out the tbody rows in data order, so this is test-stable.)
- **A per-row action rendered as a custom `Cell: () => <Button onClick=...>` does NOT fire its onClick
  inside the DataTable** (works in isolation, and TrefferListe's does — but under the page's mount→loading→data
  re-renders the amarillo DataTable renders the action cell in a **detached DOM subtree / portal**: a native
  click on the button does NOT bubble to the wrapper Box, and its React onClick never dispatched). Memoizing
  the columns (`useMemo`) did NOT fix it. **Use amarillo's first-class `rowActions` prop instead:**
  `rowActions={[{ label, icon: 'eye', onClick: (row)=>open(row.original) }]}` — its onClick fires reliably.
  The rendered action button has NO `data-testid`; its accessible name is the `label`, so target it in RTL
  with `getByRole('button', { name: '<label>' })`. Valid `icon` values come from amarillo's `iconNamesList`
  (e.g. `eye` = view, `edit`, `delete`, `info`, `search`, `close`, `download`; there is **no** `open_in_new`
  or `visibility`). `eye` (view) is the right read-only "open" affordance and avoids the forward-arrow that
  UX #2191 flagged for row actions.
- The mandatory left-aligned header `styleOverride` (UX checklist #1) still applies:
  `styleOverride={{ root: { '& .MuiTableCell-head > div': { justifyContent: 'flex-start' } } }}`.

## GOTCHA: amarillo `Typography` has NO `h6`; `InlineMessage`/`Alert` limits
- `Typography variant` supports only `h1..h5 | subtitle1 | body1 | body2 | caption | button | label` — **no
  `h6`**. If a design says h6, use `h5` (the smallest supported) and note the adaptation.
- **There is no `Alert` export.** For an inline error use a `Typography` with `sx={{ color: 'error.main' }}`
  (or `InlineMessage`, whose `variant` is only `default | info | highlight` — no `error`; `showNotification`
  from `core/models` is the toast path for error feedback).

## Form action row: REUSE BackButton + SubmitButton, don't hand-roll (verified #2209)
For a form's bottom nav row (Zurück left, Weiter/Save right on one baseline), COPY the
`CreateDirectiveOrderForm` pattern (`components/createDirectiveOrdersPage/.../CreateDirectiveOrderForm.tsx`
+ its `styles.ts`): an action `Grid2` with `styles.actions` (`width:'100%'`, `display:'flex'`,
`justifyContent:'space-between'`, `alignItems:'center'`, `gap:'24px'`) holding shared
`BackButton` (`common/components`; already `variant='secondary'`+`reverse`, label `t('app.back')`,
testid `back-button`; pass `size='auto'` + `customStyles={styles.backButtonInline}`) and `SubmitButton`
(pass `testId=...` + `customStyles={styles.submitButtonInline}` to neutralise its own footer
`marginTop:'auto'`/`paddingBottom:'24px'`). Put the row INSIDE the fields' 90% `gridContainer` (width
100%) so it spans the same column as the fields. Give the kept Submit an explicit `testId` (e.g.
`order-holder-submit-button`) so it stops colliding with the default `submit-button` id. `BackButton`
`onClick` for a first-step mask can be `useRouter().back()` (Next router; global test mock provides
`back`). Both SubmitButton and BackButton render a `Grid2` (default `size=12`) — the `*Inline` styles
set `width:'auto'`/`flexBasis:'auto'` so they hug instead of filling the row.

## Show a control only in the right state — gate on ALL the state, not just one flag (#2209)
A duplicate/overlapping control usually means a render gate checks too few flags. On ChooseOrderHolder
the top "Weiter" was gated only on `!hasDifferentOrderHolder`, but the pre-fill flow sets
`differentOrderHolderType` WITHOUT `hasDifferentOrderHolder`, so BOTH the top button and the
company/person form rendered. Fix: gate on `!hasDifferentOrderHolder && !differentOrderHolderType`.
When two things render together that shouldn't, enumerate every state that reaches that branch (default
vs pre-fill vs checkbox path) before adding a flag — and keep the flag that the normal path relies on
(here the default path has `type=null`, so the top button is still its only way to advance).

## Testing (RTL harness, ResizeObserver stub, async-settle, lint) → [10-testing-patterns.md](10-testing-patterns.md)
All frontend test-writing gotchas (the `test-utils` render harness, the jsdom `ResizeObserver` stub for
amarillo DataTable, the fetch-on-mount async-settle determinism `findBy`/`waitFor` rule, and the
`next lint --file` misses-test-files trap) live in [10-testing-patterns.md](10-testing-patterns.md).
Write component tests from there.
