# Technical Guidelines for {PROJECT-NAME} — Unified Reference

> Replace `{PROJECT-NAME}` and `{CLIENT-NAME}` with your actual project and client names
> throughout this document. Replace technology-specific names (e.g. `{UI-FRAMEWORK}`,
> `{EVENT-BUS}`, `{SERVICE-A}`, `{SERVICE-B}`, `{AUTH-PROVIDER}`) with the equivalents
> used in your project's approved tech stack.

This document merges three sources into a single authoritative reference for all agents and
developers working on the `{PROJECT-NAME}` implementation:

1. **`{CLIENT-NAME}` External Vendor Development Guidelines** (client PDF or equivalent)
2. **`{PROJECT-NAME}` Architecture Analysis** — static code review of `csharp/src/frontend` and
   `csharp/src/backend` (or equivalent source paths)
3. **This repository's coding conventions** from `AGENTS.md` and `.editorconfig`

Keywords follow RFC 2119: **MUST**, **SHOULD**, **MAY**.

---

## 1. Architecture Classification

### Frontend

```
Next.js layered modular frontend with Redux model modules,
RxJS epics, REST services, next-intl i18n, and {CLIENT-NAME} design system (e.g. Amarillo UI).
```

### Backend

```
Clean Architecture with DDD aggregate modeling,
CQRS-style MediatR handlers, and hexagonal ports/adapters.
```

### Dependency direction (backend)

```
API ──► Application ──► Domain
 │                        ▲
 └──► Infrastructure ─────┘
            ▲
        Contracts / SharedKernel (shared)
```

- Inner layers (Domain, Application) must not depend on outer layers.
- Infrastructure implements ports defined in Application.
- API is the composition root; it wires everything together.

---

## 2. Approved Technology Stack

### Frontend

| Category | Required |
|---|---|
| Framework | React + Next.js (MUST; React alone forbidden for customer-facing/SEO-critical apps) |
| Language | TypeScript — strict mode MUST be enabled in `tsconfig.json` |
| Design system | `{CLIENT-NAME}` design system (MUST for all UIs — e.g. Amarillo UI) |
| State management | Redux Toolkit + Redux Observable (RxJS epics) |
| Forms & validation | React Hook Form + Zod |
| i18n | next-intl (configure locales per project) |
| Styling | Emotion + design-system ThemeProvider |
| REST client | `cross-fetch` via shared REST helper |
| CAPTCHA | FriendlyCaptcha or equivalent (confirm with `{CLIENT-NAME}`) |
| Unit tests | Jest + React Testing Library |
| E2E/integration | Playwright |
| Mocking | MSW (Mock Service Worker) |
| Linter | ESLint (Next.js core web vitals + TS recommended + Prettier) |
| Formatter | Prettier |
| Package manager | pnpm |

### Backend

| Category | Required |
|---|---|
| Platform | .NET 8 (default); confirm worker target if divergent |
| API style | ASP.NET Core minimal APIs |
| Mediator | MediatR (commands/queries for all use cases) |
| Validation | FluentValidation (pipeline behavior) |
| Mapping | AutoMapper |
| Error handling | ErrorOr |
| ORM | EF Core — SQL Server (or project-approved database) |
| OpenAPI | Swagger/OpenAPI configured on all APIs |
| Auth | Microsoft Identity Web / Entra ID (Azure AD) or `{CLIENT-NAME}`-approved IDP |
| Config | Azure App Configuration or equivalent |
| Cache | Redis (prod) / in-memory (dev) via distributed cache abstraction |
| Search | Typesense (or project-approved search backend) behind interface in Infrastructure |
| Messaging | KafkaFlow (or project-approved message broker); message schemas in Avro format |
| Observability | Application Insights + OpenTelemetry |
| Graph/Contacts | Microsoft Graph + `{CLIENT-NAME}` adapter (behind interface) |

### Infrastructure & Platform

| Category | Required |
|---|---|
| Container platform | AKS (Azure Kubernetes Service) or project-approved platform |
| Service mesh | Linkerd2 ONLY — proxy injection must be enabled |
| Networking | Azure CNI (kubenet forbidden) |
| K8s package manager | Helm v3+ (no raw `kubectl` in production) |
| API management | Azure API Management or equivalent |
| IaC | ARM / Bicep (imperative PowerShell/CLI forbidden except prototyping) |
| Event streaming | ESP (Kafka-based) or equivalent |
| IDP (internal) | Entra ID (Azure AD) or `{CLIENT-NAME}`-approved internal IDP |
| IDP (customers) | `{CLIENT-NAME}`-approved customer-facing IDP (e.g. Azure AD B2C) |
| Secrets | AKS CSI Driver / Key Vault (not plain Kubernetes secrets) |
| Vulnerability scanning | BlackDuck (MUST) or `{CLIENT-NAME}`-approved scanner |
| Code quality | SonarQube — `{CLIENT-NAME}` Quality Gate (MUST) |
| VCS | Git on `{CLIENT-NAME}`-approved platform (e.g. Azure DevOps) |

### Forbidden / Restricted

- `kubenet` networking is NOT permitted.
- Building a custom IDP is forbidden — use identity federation.
- CIFS fileshare MUST NOT be used for new applications.
- React alone (without Next.js) MUST NOT be used for performance-critical or customer-facing apps.
- Blazor MUST NOT be used for performance-critical, SEO-critical, or highly scalable apps.
- Other frontend technologies require `{CLIENT-NAME}` IT Architecture approval.

---

## 3. Coding Standards

### General

- Character encoding: UTF-8 in all interfaces.
- Code SHOULD be self-documenting; complex logic SHOULD explain rationale in inline comments.
- Do not add comments that restate what the code does — only document non-obvious WHY.

### TypeScript / React / Next.js

- TypeScript strict mode MUST be enabled.
- `any` SHOULD be avoided; it is a warning outside `src/core/**`.
- Function components MUST be used — no class components.
- MUST NOT use `useContext` directly — wrap in a custom hook.
- ESLint and Prettier MUST be configured and enforced.
- Pre-commit hooks SHOULD enforce linting, formatting, and typecheck (Husky + lint-staged already
  in place).
- `// @ts-nocheck` must remain exceptional; fix types instead.
- `unused variables` are ESLint errors.
- `no-console` allows only `console.warn` and `console.error`.
- Import order is enforced and alphabetized.

### Prettier rules (from project config)

- Single quotes, semicolons, print width 90, tab width 2.
- Trailing commas for ES5-compatible locations.
- Arrow function parentheses always on.
- JSX single quotes enabled.

### C# / .NET (.editorconfig)

- Spaces for indentation, indent size 4.
- CRLF line endings.
- File-scoped namespaces preferred (warning if not used).
- `using` directives outside namespaces; `System.*` sorted first.
- Braces required. Accessibility modifiers required on non-interface members.
- `var` is NOT preferred, even when the type is apparent.
- Readonly fields encouraged (warning).
- Static local functions preferred. Simple `using` statements preferred.
- Pattern matching, null propagation, object/collection initializers, simplified expressions
  encouraged.

#### C# naming

| Element | Convention |
|---|---|
| Types, namespaces, methods, properties, events, enums, public fields | PascalCase |
| Interfaces | `I` + PascalCase |
| Type parameters | `T` + PascalCase |
| Locals and parameters | camelCase |
| Private instance fields | `_camelCase` |
| Private static fields | `s_camelCase` |

### Language in code

- Code comments, technical names, and developer-facing documentation: **English**.
- Customer-facing copy: translation files (`src/translations/`), never hardcoded in components.
- Official product/domain terminology: use exact business terms even when in the client's language.

### Event / Message naming

- Schema: `{Namespace}.{Aggregate}.{EventName}`
- Event name MUST end in a past-tense verb (e.g., `Order.Shipment.Delivered`).
- Message schemas MUST be in Avro format (or the project-approved schema format).

---

## 4. Frontend Architecture Rules

### Layer responsibilities

| Layer | Responsibility |
|---|---|
| `src/pages` | Route entry points only; keep thin |
| `src/components` | Feature screens and composed UI |
| `src/common` | Reusable UI building blocks |
| `src/core` | Cross-cutting infrastructure (REST helper, low-level API) |
| `src/models` | Redux state modules: actions, reducers, selectors, schemas, mappers |
| `src/services` | Backend API calls — the only place that calls the REST helper |
| `src/store` | Redux composition: reducers, epics, middleware, Next.js wrapper |
| `src/translations` | JSON i18n files |
| `src/mock-server` | MSW setup (enabled via `NEXT_PUBLIC_ENABLE_MOCK_SERVER`) |
| `src/test-utils` | Shared test helpers |
| `src/utils` | General utilities |

### Frontend data flow

```
Page → Component → Form/schema/mapper → Redux action → Epic → Service → REST helper → Backend
```

### Frontend rules

- Keep API calls inside `services`; never call the REST helper directly from components.
- Keep async orchestration inside epics; Redux thunk is disabled.
- Keep domain mapping in model mappers, not UI components.
- Keep validation schemas close to the relevant model/form module.
- Split very large feature components when they become hard to reason about.
- Keep all UI strings in translation files.
- Verify `Accept-Language` header in the REST helper matches the app's default locale.
- Verify `tsconfig` path aliases before use — stale aliases cause silent import failures.
- `allowJs: true` and `skipLibCheck: true` reduce strictness — do not expand these without
  justification.

### Frontend build commands

```
pnpm dev          # development server
pnpm build        # production build
pnpm lint         # ESLint
pnpm typecheck    # TypeScript check (no emit)
pnpm test         # Jest
pnpm test:ci      # Jest CI mode
pnpm test:it      # Playwright integration
pnpm test:si      # Playwright system integration
pnpm test:e2e     # Playwright end-to-end
```

Run `pnpm lint`, `pnpm typecheck`, and relevant tests before merging.

---

## 5. Backend Architecture Rules

### Layer responsibilities

| Layer | Responsibility |
|---|---|
| `API` | HTTP endpoints, auth, OpenAPI, middleware, composition root |
| `Application` | Commands, queries, handlers, validators, pipeline behaviors, port interfaces |
| `Domain` | Aggregates, entities, value objects, domain events, business invariants |
| `Infrastructure` | EF Core, repositories, cache, messaging, search, external system adapters |
| `Contracts` | Request/response DTOs, queue messages, shared API models |
| `SharedKernel` | Shared enums, types, and common abstractions |

### Backend rules

- Keep HTTP concerns in API; endpoints stay thin.
- Keep use cases in Application; handlers own orchestration.
- Keep business invariants in Domain; Domain should stay as framework-free as practical.
- Keep EF Core, messaging, cache, search, and external system details in Infrastructure.
- Define interfaces in Application when the application needs an external capability; implement
  them in Infrastructure.
- Prefer MediatR commands/queries for all use cases.
- Prefer FluentValidation pipeline behavior over ad hoc request validation.
- Avoid putting business logic in endpoints.
- Avoid putting infrastructure technology details in Domain.

### Backend architecture risks to watch

- `TreatWarningsAsErrors` is commented out in `Directory.Build.props` — consider enabling it.
- Verify that worker and main backend target frameworks are aligned or intentionally divergent.
- Application references to search/indexing packages belong in Infrastructure.
- Application DI loading profiles from Infrastructure weakens the dependency boundary.
- Domain references to framework/localization packages should be minimized.
- Test-data generation libraries (e.g. Bogus) must not appear in production business flows.
- `obj` folders must not be committed.

---

## 6. REST API Design

- Architecture is decoupled services exposing RESTful APIs with JSON payloads.
- API First principle: define APIs outside code, conduct peer review before implementation.
- All REST APIs MUST follow `{CLIENT-NAME}` API Guidelines (or project-agreed guidelines).
- APIs MUST use appropriate HTTP methods and status codes.
- Error handling MUST follow the documented error response format (ProblemDetails in .NET).
- All persistence access MUST go through an API managed via API Management.
- Server-side components MUST NOT access databases directly from outside the Infrastructure layer.

### Integration patterns

- External integration: Web API Gateway (preferred), Event Integration Gateway, File Integration
  Gateway.
- Internal domain-to-domain synchronous: Web API Gateway.
- Internal domain-to-domain asynchronous: messaging topics (e.g. Kafka/ESP).
- Integration components MUST NOT implement business logic.
- Messaging topics MUST be producer-driven; one producing domain per topic.
- Synchronous queries: REST via API Gateway (SOAP only for legacy).
- Async reads: messaging topics.
- Timestamps: ISO 8601.

### Data architecture

- Same data = same name; different data = different names.
- Move/copy data as little as possible.
- Workflow: create Data Contract → create artefact (OpenAPI YAML for web, Avro for messaging) →
  document in the project architecture catalogue.
- Foreign-domain data: store referentially only (technical/functional key).

---

## 7. Security

### Authentication

- All applications/APIs MUST use appropriate authentication.
- Internal IDP: `{CLIENT-NAME}`-approved internal IDP (e.g. Entra ID / Azure AD).
- Customer-facing IDP: `{CLIENT-NAME}`-approved customer-facing IDP.
- Do NOT build a custom IDP; use identity federation.
- API preference order: OAuth2/OIDC > JWT > API keys (internal only) > Basic (never).
- Application preference order: SSO > Passwordless > MFA > Social login > username/password
  (never alone).
- JWT: use RS256/ES256, validate signature and claims, HTTPS required, implement token revocation.
- OAuth2: auth code + PKCE for web/mobile; client credentials for M2M.

### Application security

- No sensitive data in client-side code.
- Environment variables MUST be used for configuration secrets.
- Input validation MUST be performed on both client and server.
- Output encoding MUST be used to prevent XSS.
- CSRF protection MUST be implemented for state-changing operations.
- HTTPS MUST be used in all environments (except local dev); HSTS SHOULD be enabled.

### Container / Kubernetes security

- Approved vulnerability scanner (e.g. BlackDuck) for vulnerability management.
- RBAC: prefer RoleBindings over ClusterRoleBindings.
- Secrets: AKS CSI Driver only (not plain Kubernetes secrets).
- Pod Security: enforce Baseline/Restricted standards.
- Network Policy: isolate namespaces, control external visibility, enable mutual TLS.
- Audit logging must be enabled.
- Use only official images from approved registries/verified publishers.
- Check config against CIS Benchmark at least annually.

Required container security context:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 64198     # confirm UID with {CLIENT-NAME} platform team
  runAsGroup: 64198    # confirm GID with {CLIENT-NAME} platform team
  allowPrivilegeEscalation: false
  privileged: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
```

---

## 8. Testing

### Requirements

| Type | Rule |
|---|---|
| Unit tests | MUST be written for business logic and utility functions |
| Unit coverage | SHOULD be ≥ 70% for new code |
| Unit frameworks | Jest/Vitest + React Testing Library (frontend); xUnit (backend) |
| Integration tests | MUST be written for critical user flows and API integrations |
| Accessibility tests | MUST be automated (axe-core, @axe-core/react, jest-axe) |
| Keyboard navigation | MUST be tested manually |
| Screen reader | SHOULD be tested on at least one major reader |
| All tests | MUST pass in CI/CD before deployment |

### Core Web Vitals thresholds (MUST be validated)

| Metric | Threshold |
|---|---|
| LCP | ≤ 2.5 seconds |
| INP | ≤ 200 milliseconds |
| CLS | ≤ 0.1 |

### Workload testing

- Jobs MUST be idempotent.
- Retry budget: 15% or lower.
- In shared clusters: run one failure experiment at a time; target namespace only.

### Frontend test locations

- Jest unit/component tests: `src/frontend/` (co-located or `test-utils`)
- Playwright tests: `src/frontend/tests/`
- MSW handlers: `src/mock-server/`

### Backend test locations

- C# tests: `csharp/test/`
- Generated test output: `reports/test-results/`

---

## 9. Version Control & CI/CD

### Branching

- Git MUST be used; source code MUST be in `{CLIENT-NAME}`'s approved VCS repository.
- Main branch: small changes only; feature branches for larger development.
- Branches SHOULD be deleted after merge.
- Squash commits for clean history.
- Conventional Commits MUST be used; messages must be meaningful.

### CI/CD

- Automated builds MUST be configured.
- All tests MUST pass before deployment.
- Automated deployment SHOULD be implemented for dev and staging.
- Container images: build with approved ACR tooling; tags MUST identify production-deployed
  versions; images MUST be locked immediately after build.
- Performance regression SHOULD be monitored in CI/CD.
- Dependency scanning SHOULD be automated in CI/CD.
- Cross-browser testing SHOULD be automated.

### Infrastructure as Code

- Declarative deployment: ARM/Bicep required (or project-approved IaC tooling).
- Imperative (PowerShell/Azure CLI for infra creation): forbidden except for prototyping.
- Azure CNI only; kubenet is NOT permitted.

---

## 10. Accessibility

- WCAG 2.2 Level AA MUST be met.
- All interactive elements MUST be keyboard accessible.
- Color contrast: 4.5:1 for normal text, 3:1 for large text.
- Semantic HTML5 elements MUST be used.
- ARIA only when semantic HTML is insufficient; MUST NOT override native semantics.
- Touch targets MUST be at least 44×44 pixels.
- Skip navigation links SHOULD be provided.
- Applications MUST be fully responsive on all screen sizes.
- Viewport meta tag MUST be included; zoom MUST NOT be disabled on mobile.
- Mobile-first approach SHOULD be used.
- Progressive enhancement SHOULD be followed; core functionality MUST work without JavaScript
  where feasible.

### Browser support

MUST support the last 2 major versions of: Chrome, Firefox, Safari, Edge (desktop) and
Chrome Android, Safari iOS (mobile).

---

## 11. Documentation

- `README.md` MUST be at the root and MUST enable running the app and unit tests without
  additional meetings.
- API integrations MUST be documented.
- Architecture documentation MUST follow arc42 template.
- Minimum solution design: introduction/goals, constraints, context/scope, architecture decisions.
- Context diagram is mandatory (domains, applications, interfaces, data objects).
- ADRs use MADR format in the project Domain Wiki or equivalent.
- Architecture material: `docs/architecture/`.
- Confirmed requirements and source observations: `docs/requirements/`.
- Implementation evaluations and reports: `reports/evaluations/`.

### Operations Manual — required sections

1. General description
2. Technical description
3. Deployment procedures
4. Technology stack and staging
5. External components and dependencies
6. Safety/security, certificates, custom domains
7. Data persistence
8. Monitoring/logging
9. Fault management, troubleshooting, system reboot
10. Known issues/solutions
11. Disaster recovery
12. Operational availability
13. Contacts/escalation

---

## 12. Deployment & Go-Live

### Go-live prerequisites (all mandatory)

| # | Prerequisite |
|---|---|
| 1 | Architecture/application catalogue entry registered (e.g. LeanIX) |
| 2 | BIA (Business Impact Analysis) completed — if business-critical/sensitive/customer-facing |
| 3 | CMDB CI registered (name, ownership, dependencies, classification) |
| 4 | Operations Manual complete |
| 5 | Operational handover validated with Ops team |
| 6 | Alert handover (minimum 5 business days before go-live) |
| 7 | Approved RfC with testing evidence and validated rollback |

### Deployment rules

- Deployment procedures MUST be tested in non-production.
- Rollback procedures MUST be validated and documented.
- UAT/performance/security testing evidence REQUIRED in RfC.
- Operations monitors production only.
- Helm charts only in production; no raw `kubectl`.
- Use `--wait` and `--timeout` for Helm deployment validation.
- Resource requests and limits are mandatory in shared clusters.
- Services should be ClusterIP; expose via Ingress/HTTPRoute if needed.
- API Management must point to Ingress, not Service directly.

### Alerting thresholds

| Metric | Critical Threshold |
|---|---|
| HTTP 5xx | > 0 |
| Availability | < 99.9% |
| Consumer lag | > 1000 |
| Queue depth | > 5000 (warning) |
| Sync lag | > 10 min |
| DB CPU | > 85% |
| Backup age | > 24h |

---

## 13. Dependency Management

- All dependencies MUST be kept up-to-date.
- Known vulnerabilities MUST be addressed promptly.
- Approved vulnerability scanner (e.g. BlackDuck) MUST be used for scanning.
- All IT components MUST stay within active lifecycle; latest approved version MUST be used for
  new applications.
- Licensing/TCO must be analyzed before development; licenses centrally managed.

---

## 14. Quality Gates

### Mandatory tools

| Tool | Requirement |
|---|---|
| SonarQube | MUST be used (`{CLIENT-NAME}` Quality Gate) |
| Approved vulnerability scanner | MUST be used for dependency/vulnerability scanning |
| Git | Code MUST be fully versioned |

### Go-live quality gate checklist

- [ ] Architecture catalogue entry registered
- [ ] BIA completed (if applicable)
- [ ] CMDB CI registered
- [ ] Operations Manual complete
- [ ] Operational handover done
- [ ] Alert documentation/handover complete
- [ ] RfC approved with testing evidence
- [ ] All tests passing
- [ ] Rollback procedure validated

---

## 15. Quick Reference Checklist

| # | Requirement | Level |
|---|---|---|
| 1 | Git (approved VCS), conventional commits, feature branches | MUST |
| 2 | TypeScript + Next.js + `{CLIENT-NAME}` design system for web apps | MUST |
| 3 | Follow `{CLIENT-NAME}` REST API Guidelines | MUST |
| 4 | ESLint + Prettier configured | MUST |
| 5 | Unit test coverage ≥ 70% for new code | SHOULD |
| 6 | Tests in CI/CD pipeline (all must pass before deploy) | MUST |
| 7 | Approved dependency scanning | MUST |
| 8 | SonarQube quality gate (`{CLIENT-NAME}`) | MUST |
| 9 | WCAG 2.2 AA accessibility | MUST |
| 10 | Core Web Vitals (LCP ≤ 2.5s, INP ≤ 200ms, CLS ≤ 0.1) | MUST |
| 11 | Peer code review before merge (no self-approval) | MUST |
| 12 | Source code in `{CLIENT-NAME}` repository | MUST |
| 13 | README with full setup instructions | MUST |
| 14 | Helm v3+ for K8s deployments | MUST |
| 15 | Linkerd2 service mesh enabled | MUST |
| 16 | Non-root containers with required security context | MUST |
| 17 | HTTPS everywhere, CSRF/XSS protection | MUST |
| 18 | `{CLIENT-NAME}`-approved IDP for auth (no custom IDP) | MUST |
| 19 | Architecture docs (arc42, context diagram) | MUST |
| 20 | Go-live checklist complete (catalogue, BIA, CMDB, Ops Manual, RfC) | MUST |

---

## 16. Code Review Process

- All code MUST undergo peer review before merging.
- Do NOT approve your own PRs.
- PR descriptions must include meaningful title and rationale.
- Do NOT resolve reviewer comments yourself — notify the reviewer.
- Architecture contradictions must be cleaned up before merge.

| Content Area | Reviewer |
|---|---|
| Architecture changes | IT Architecture or Cloud CoE (or equivalent `{CLIENT-NAME}` team) |
| Technical platform documentation | Owning team |
| HowTos / Known Issues | One non-author reviewer |
| Event Streaming message types | One reviewer from each required group |

---

## 17. Known Risks and Open Items

> Populate this section with project-specific known risks. The example entries below are drawn
> from a reference implementation and should be replaced with `{PROJECT-NAME}`-specific findings.

| Risk | Status |
|---|---|
| `TreatWarningsAsErrors` commented out in `Directory.Build.props` | Open — enable when feasible |
| Worker targets a different .NET version than the main backend | Open — confirm intentionality |
| Application references search/indexing packages (infrastructure leak) | Open — move to Infrastructure |
| Application DI loads mapper profiles from Infrastructure | Open — refactor boundary |
| Domain references framework/localization packages | Open — minimize |
| `Accept-Language` hardcoded in REST helper rather than using app locale | Open — should respect configured locale |
| `tsconfig` path alias mismatch with actual folder name | Open — verify/fix |
| `// @ts-nocheck` present in source files | Open — fix types instead |
| README mentions a library/pattern the codebase does not actually use | Open — README drift |
| Test-data generation library present in production projects | Open — ensure not used in production flows |

---

*Sources: `{CLIENT-NAME}` External Vendor Development Guidelines, `{PROJECT-NAME}` static
architecture analysis of `csharp/src/`, `AGENTS.md`, and `.editorconfig`.*
