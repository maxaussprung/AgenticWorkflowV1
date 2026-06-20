# Frontend Agent Instructions

This file applies to `csharp/src/frontend`.

Read the repository root `AGENTS.md` and `docs/architecture/csharp-source-architecture.md` before making frontend changes.

## Architecture Rules

- Preserve existing confirmed {PROJECT-NAME} behavior unless a ticket or requirement explicitly changes it.
- Treat the frontend as a layered modular Next.js 14 / React 18 TypeScript app with Redux Toolkit models, redux-observable/RxJS effects, REST services, i18n, React Hook Form, Zod, {CLIENT-NAME}/ui-library (replace with your project's UI component library), and Emotion styling.
- Keep `src/pages` route files thin. Pages should load translations/static props and delegate rendering to feature components.
- Put feature UI under `src/components`; put reusable UI/hooks/assets under `src/common`.
- Put shared workflow/application state under `src/models` using the local `slice.ts`, `actions.ts`, `epics.ts`, `selectors.ts`, and `types.ts` pattern.
- Put REST adapters and payload/response types under `src/services`.
- Keep low-level REST mechanics in `src/core/api/rest`; do not duplicate fetch/error/header handling in components.
- Use epics for asynchronous application workflows; thunks are intentionally disabled.
- Keep API mocking under `src/mock-server` and Playwright/WireMock test setup under `tests`.
- Keep large feature components from accumulating backend orchestration or payload construction; move mapping to model/service mappers when the surrounding code supports it.

## Frontend Data Flow

- Typical flow: page -> feature component -> form/schema/mapper -> Redux action -> epic -> service -> REST helper -> backend.
- Components should render state from selectors and dispatch actions; epics own async workflows and service calls.
- React Hook Form and Zod are the default form/validation pattern. Pass translation functions into schemas for localized validation messages.
- UI text should come from `next-intl` translation files; default locale is {DEFAULT-LOCALE}, while code comments and technical names remain English.
- The central API base URL comes from `NEXT_PUBLIC_API_BASE_URL`; MSW can be enabled with `NEXT_PUBLIC_ENABLE_MOCK_SERVER`.

## Coding Conventions

- Use pnpm, not npm or yarn.
- Follow the existing TypeScript/React style: strict TypeScript, functional components, single quotes, semicolons, Prettier print width 90.
- Use lower camelCase folders for features/models/services and PascalCase files for React components.
- Use path aliases from `tsconfig.json` instead of long relative import chains where possible.
- Use `{CLIENT-NAME}/ui-library` components and the existing Emotion `styles.ts` pattern before introducing new UI primitives. (Replace `{CLIENT-NAME}/ui-library` with the actual package name for this project.)
- Use `next-intl` translation keys for user-visible text unless the surrounding code clearly uses a fixed literal.
- Preserve the client's domain terminology in user-facing copy and translation keys.
- Keep Redux slice names aligned with model folder names.
- Do not commit secrets or personal feed tokens in `.env*`, `.npmrc`, Docker, or pipeline files.

## Testing

- Add Jest/React Testing Library tests near source in `__tests__` folders for components, hooks, reducers, selectors, services, and epics.
- Add Playwright coverage under `tests/integrationtests`, `tests/systemIntegration`, or `tests/e2e` for browser-level workflows.
- Preserve the existing page-object style under `tests/pages`.
- Use MSW mocks for unit/integration isolation where appropriate.
- From `csharp/src/frontend`, use the relevant script: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm test:it`, `pnpm test:si`, or `pnpm test:e2e`.
- Keep generated coverage and Playwright reports out of source folders.
