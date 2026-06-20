# Backlog

Open work plus the last 5 closed items per section, grouped by owner. Approach a todo only when explicitly instructed. Older closed items live in [done.md](done.md). See [AGENTS.md → Backlog hygiene](AGENTS.md#backlog-hygiene) for how to log unlisted work, write completion sub-bullets, and trim closed items.

Closed: `[x]`. Open: `[ ]`.

## Owner: requirements engineer

- [ ] **Sign-off on the cross-check** — review the source import overview in `docs/requirements/source-import/` and decide whether any application stubs are missing or need renaming.
- [ ] **Add any missing application stubs** once the cross-check is signed off.
- [ ] **Specification document extraction pass** — go through the project specification document and add structured `source:` entries to existing features/requirements; create any features/requirements the initial pass missed.
- [ ] **Owner assignment** — replace `owner: TBD` with real engineering owners once the team is allocated.
- [ ] **Effort estimates** — set `Sprints` per feature once the team has sized them; the *Estimation* section will then surface totals.

## Owner: architect

- [ ] Once features/requirements are promoted to `status: approved`, populate the `### Architecture` and `#### Technical Dependencies` placeholders on Tier 1 requirements.

## Owner: test case designer

- [ ] **Phase 1 verification** — author UAT test cases against every Phase 1 requirement (`Phase: 1`, `implementation_status: implemented`) to promote the running system to `verified`.

## Owner: Frontend test author

- [ ] **Define the final manual quality gate** — the human/role sign-off over this agent's documented coverage (status `documented` → `released`). Not yet specified.
- [ ] **Wire into the TDD flow** — coordinate with the `generate-tdd-tests` / `pick-implementation-slice` skills (dev agents write RED tests; this agent reviews/augments/documents afterwards).

## Owner: Backend test author

- [ ] **Pilot on a real backend requirement** — run map → review & augment → assess & document on one already-implemented requirement (use its `openspec_change` to find the slice) and emit the first `reports/test-coverage/backend/<REQ>.json`.
- [ ] **Test orchestration skill** — selection of which requirements to test (from `openspec/track.md` / `openspec_change`) and fan-out to the frontend + backend (+ later integration) agents belongs to a planned test skill, not the agents.

## Owner: generalist

- [ ] Populate this backlog section with project-specific setup tasks when the team is confirmed.

## Owner: sitebuilder

- [ ] **Render frontend test coverage** — read `reports/test-coverage/frontend/<REQ-ID>.json` (and later the backend/integration siblings) and render three things: a compact "Tests & Coverage" section on each requirement page (extend `requirement-header.html`), a per-requirement detail view, and an overall rollup in the (currently empty) test section.
