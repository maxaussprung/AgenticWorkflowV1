---
name: generate-tdd-tests
description: Generate requirement-driven failing tests for a claimed {PROJECT-NAME} implementation slice before production code is changed. Use during the TDD phase after an OpenSpec change exists, or when a developer asks to create RED tests for backend, frontend, integration, or requirement-level test cases.
---

# Generate TDD Tests

Use this skill to create the RED test side of the {PROJECT-NAME} TDD workflow. The goal is to turn
confirmed requirements and OpenSpec tasks into focused tests before implementation code is changed.

## Required context

Read these before acting:

- `AGENTS.md`
- `docs/architecture/implementation-slice-workflow.md`
- `docs/architecture/csharp-source-architecture.md`
- `docs/requirements/AGENTS.md`
- `docs/requirements/page-types/requirement.md`
- `docs/requirements/page-types/test_case.md`
- `openspec/track.md`
- `openspec/changes/<change-name>/proposal.md`
- `openspec/changes/<change-name>/design.md`
- `openspec/changes/<change-name>/tasks.md`
- Each affected `docs/requirements/requirements/REQ-*.md`

Also read the local `AGENTS.md` files for any code area you will touch, for example:

- `csharp/src/backend/AGENTS.md`
- `csharp/src/frontend/AGENTS.md`

## Preconditions

- Work from the implementation branch for the active OpenSpec change.
- Inspect `git status --porcelain` first. If unrelated uncommitted changes exist, do not
  overwrite them; work around them or stop and report the conflict.
- Never edit `to_be_migrated_repo/` or `legacy-sql/`.
- Do not change production code while generating RED tests unless the developer explicitly asks
  for implementation in the same turn.
- Do not invent business behavior. If a scenario is unclear, mark it as a TODO in the test name,
  test-case page, or summary rather than guessing.

## Identify the test scope

1. Determine the OpenSpec change name from the branch, conversation, or `openspec/track.md`.
   If ambiguous, ask the developer to choose.
2. Extract affected `REQ-*` IDs from the top traceability block and requirements mapping in
   `proposal.md`, `design.md`, and `tasks.md`.
3. Read each affected requirement's user story, formal requirement, acceptance criteria, source
   atlas, exclusions, architecture, and technical dependencies.
4. Read relevant existing tests and implementation patterns before adding new files:
   - Backend unit tests under `csharp/test/backend/{BACKEND-UNIT-TEST-PROJECT}`.
   - Backend integration tests under `csharp/test/backend/{BACKEND-INTEGRATION-TEST-PROJECT}`.
   - Frontend tests under `csharp/src/frontend/src/**/__tests__`.
   - Playwright tests under `csharp/src/frontend/tests`.
5. Build a concise test matrix with one row per acceptance criterion:
   - Requirement ID.
   - Scenario.
   - Test layer: unit, integration, component, service, epic, Playwright, or requirement test case.
   - Existing coverage, if any.
   - New or changed test file.

## Choose test layers

Prefer the smallest test layer that gives confidence:

- **Domain/application rules:** backend unit tests with xUnit, FakeItEasy, and FluentAssertions.
- **Minimal API behavior, serialization, validation pipelines, persistence, or auth-sensitive
  behavior:** backend integration tests.
- **Frontend state, mappers, schemas, hooks, epics, and service adapters:** Jest unit tests.
- **User-visible component states and form behavior:** React Testing Library component tests.
- **End-to-end navigation or multi-page workflows:** Playwright tests.
- **UAT/business traceability:** `docs/requirements/test_cases/` pages when the requirement needs
  a durable manual or integration scenario.

Avoid high-level browser tests for rules that can be fully verified with unit or component tests.
Avoid testing DTO boilerplate, getters, setters, or trivial mappings unless they encode business
rules.

## Write RED tests

1. Add or update tests using the repository's existing naming, folder, fixture, and assertion
   patterns.
2. Give test names business meaning. Include the product/rule language from the requirement where
   useful.
3. Make each test fail for the missing behavior, not because of invalid setup, missing fixtures, or
   syntax errors.
4. Keep tests deterministic:
   - Use `TimeProvider` or fake time for backend date logic.
   - Use fixed clocks or injected dates in frontend utilities when available.
   - Avoid direct wall-clock dependencies in assertions.
5. Keep fixtures minimal and explicit. Prefer local builders only when the surrounding test suite
   already uses that pattern.
6. For validation tests, assert on meaningful failure messages or error keys when the requirement
   specifies them.
7. For API tests, assert status code and response shape. Only assert exact payload fields that are
   required by the scenario.
8. For frontend tests, assert what the user can observe or what the model/service contract returns.
   Do not assert incidental DOM structure.
9. If adding requirement test cases, follow `docs/requirements/page-types/test_case.md`, link the
   affected `REQ-*` IDs, and append factual `change_history` entries.

## Run tests and confirm RED

Run the smallest relevant command first:

- Backend unit tests:
  `dotnet test csharp/test/backend/{BACKEND-UNIT-TEST-PROJECT}/{BACKEND-UNIT-TEST-PROJECT}.csproj --no-restore`
- Backend integration tests:
  `dotnet test csharp/test/backend/{BACKEND-INTEGRATION-TEST-PROJECT}/{BACKEND-INTEGRATION-TEST-PROJECT}.csproj --no-restore`
- Frontend tests from `csharp/src/frontend`:
  `pnpm test -- --runInBand <path-or-pattern>`
- Frontend type/lint when touched code needs it:
  `pnpm typecheck`
  `pnpm lint`
- Requirements site when editing `docs/requirements/`:
  `.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml --strict`

If dependencies are not restored or the environment cannot run a command, do not silently skip it.
Record the command and the concrete blocker.

The expected result is:

- The new tests compile and run.
- At least one new or changed test fails because the production behavior is not implemented yet.
- Existing unrelated tests are not broken by invalid test setup.

If the tests unexpectedly pass, verify whether the behavior already exists. If it does, update
`tasks.md` and the summary accordingly instead of forcing a failing test.

## Update OpenSpec tasks

Update `openspec/changes/<change-name>/tasks.md` after the RED tests are in place:

- Mark test-generation tasks complete only when the tests exist and were run or the run blocker is
  recorded.
- Do not mark implementation tasks complete.
- Add new focused test tasks if the existing checklist missed a requirement scenario.

## Finish condition

Stop after the RED tests and task updates are complete. Report:

- OpenSpec change name.
- Requirement IDs covered.
- Test files added or changed.
- Commands run and whether they produced the expected RED failure.
- Any scenarios intentionally deferred or blocked.
- The next implementation target: the smallest production change needed to make the first failing
  test pass.

Do not proceed into GREEN implementation unless the developer explicitly asks for it.
