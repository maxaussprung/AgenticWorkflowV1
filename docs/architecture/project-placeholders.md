# Project Placeholders

This file documents every placeholder used throughout this repository template, grouped by category. Use the `/setup-repo-structure` skill to replace them interactively via an agent that asks you each question.

> **Format:** Placeholders appear as `{UPPER-CASE}` or `{lower-case}` in files. Both forms represent the same concept — `{PROJECT-NAME}` and `{project-name}` are the same value, just cased differently depending on context (e.g., display names vs. file paths).

---

## How to replace placeholders

**Option A — Automated (recommended):** Run the `/setup-repo-structure` skill. The agent will ask you each question and then perform the replacements.

**Option B — Manual:** For each placeholder below, find all occurrences with:
```bash
grep -r "{PLACEHOLDER-NAME}" --include="*.md" --include="*.yml" --include="*.yaml" \
  --include="*.py" --include="*.sh" --include="*.html" --include="*.json" \
  --include="*.bicep" --include="*.bicepparam" --include="*.tpl" .
```
Then replace with your chosen value.

---

## Group 1 — Core Project Identity

These are the most frequently used placeholders. Every other group's values derive from these.

| Placeholder | Description | Example | Count |
|------------|-------------|---------|-------|
| `{PROJECT-NAME}` / `{project-name}` | Human-readable project name. Used in headings, docs, CI pipeline display names. | `MyApp` | ~150 |
| `{CLIENT-NAME}` / `{client-name}` | Client / organization name. | `Accenture Client GmbH` | ~56 |
| `{PROJECT}` / `{project}` | Short project identifier. Used in image tags, Docker Compose project name, sync tags. | `myapp` | ~70 |
| `{PROJECT-TEAM}` | Team name for the requirements site header. | `Platform Team` | ~1 |
| `{PLATFORM-NAME}` | Platform name shown in the MkDocs requirements site. | `MyApp Platform` | ~9 |

**Files with the highest concentration:**
- `AGENTS.md`, `CLAUDE.md`, `README.md` (root)
- `docs/architecture/*.md`
- `.agents/subagents/requirements-site/agent_*.md`
- `.claude/agents/*.md`
- `tools/requirements-site/mkdocs.yml`

---

## Group 2 — Backend / Application Code

These define the C# (or equivalent) project structure. If your backend is not C#, adapt the project naming convention.

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{BACKEND-NAMESPACE}` | Root C# namespace. | `MyCompany.MyApp` |
| `{BACKEND-API-PROJECT}` | API/controller layer project name. | `MyApp.Api` |
| `{BACKEND-DOMAIN-PROJECT}` | Domain model project name. | `MyApp.Domain` |
| `{BACKEND-APPLICATION-PROJECT}` | Application/use-case layer project name. | `MyApp.Application` |
| `{BACKEND-INFRASTRUCTURE-PROJECT}` | Infrastructure/data-access project name. | `MyApp.Infrastructure` |
| `{BACKEND-SHAREDKERNEL-PROJECT}` | Shared kernel / common types project. | `MyApp.SharedKernel` |
| `{BACKEND-TEST-PROJECT}` | Generic test project name. | `MyApp.Tests` |
| `{BACKEND-UNIT-TEST-PROJECT}` | Unit test project name. | `MyApp.UnitTests` |
| `{BACKEND-INTEGRATION-TEST-PROJECT}` | Integration test project name. | `MyApp.IntegrationTests` |
| `{APP-NAME}` | Short application name used in Helm chart names. | `myapp` |
| `{DEFAULT-LOCALE}` | Default application locale / culture code. | `en-US` |

**Files with the highest concentration:**
- `.agents/skills/generate-tdd-tests/SKILL.md`
- `.agents/skills/complete-implementation-slice/SKILL.md`
- `.agents/skills/mock-implementation-slice/SKILL.md`
- `csharp/azure/helm/*/values.yaml`
- `.agents/subagents/requirements-site/agent_test_author_backend.md`

---

## Group 3 — Azure DevOps & CI/CD

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{AZURE-DEVOPS-ORG}` | Azure DevOps organization name. | `my-org` |
| `{AZURE-DEVOPS-PROJECT}` | Azure DevOps project name. | `MyProject` |
| `{REPO-NAME}` | Repository name in Azure DevOps. | `MyApp` |
| `{SERVICE-CONNECTION}` | Azure DevOps service connection name (general). | `azure-prod-svc` |
| `{SERVICE-CONNECTION-OBJECT-ID-DEV}` | Service connection AAD object ID for dev env. | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `{SERVICE-CONNECTION-OBJECT-ID-TEST}` | Service connection AAD object ID for test env. | `xxxxxxxx-...` |
| `{SERVICE-CONNECTION-OBJECT-ID-ABN}` | Service connection AAD object ID for abn env. | `xxxxxxxx-...` |
| `{SERVICE-CONNECTION-OBJECT-ID-PROD}` | Service connection AAD object ID for prod env. | `xxxxxxxx-...` |
| `{BUILD-AGENT-POOL}` | Build agent pool name. | `ubuntu-latest` |
| `{NUGET-FEED-NAME}` / `{FEED-NAME}` | Azure Artifacts NuGet feed name. | `MyFeed` |
| `{BOARD-TOOL}` | Project management / backlog tool. | `Azure Boards` |

**Files with the highest concentration:**
- `csharp/azure-pipelines*.yml`
- `csharp/azure/pipeline/*.yml`
- `csharp/azure/variables/*.yml`
- `tools/azure-sync/sync.py`
- `.agents/skills/azure-boards-export/scripts/export_azure_boards.py`

---

## Group 4 — Cloud Infrastructure (Azure)

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{CONTAINER-REGISTRY}` | Azure Container Registry hostname (without `.azurecr.io`). | `myregistry` |
| `{IMAGE_PREFIX}` | Docker image name prefix. | `myapp` |
| `{SUBSCRIPTION-ID-DEV}` | Azure subscription ID for dev environment. | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `{SUBSCRIPTION-ID-TEST}` | Azure subscription ID for test environment. | `xxxxxxxx-...` |
| `{SUBSCRIPTION-ID-ABN}` | Azure subscription ID for abn environment. | `xxxxxxxx-...` |
| `{SUBSCRIPTION-ID-PROD}` | Azure subscription ID for prod environment. | `xxxxxxxx-...` |
| `{ESP-SUBSCRIPTION-ID}` | Subscription ID used in Bicep parameters. | `xxxxxxxx-...` |
| `{AKS-RESOURCE-GROUP}` | Resource group containing the AKS cluster. | `rg-myapp-dev` |
| `{AKS-CLUSTER-DEV}` | AKS cluster name for dev. | `aks-myapp-dev` |
| `{AKS-CLUSTER-TEST}` | AKS cluster name for test. | `aks-myapp-test` |
| `{AKS-CLUSTER-ABN}` | AKS cluster name for abn. | `aks-myapp-abn` |
| `{AKS-CLUSTER-PROD}` | AKS cluster name for prod. | `aks-myapp-prod` |
| `{MANAGED-IDENTITY-CLIENT-ID}` | Managed identity client ID (general). | `xxxxxxxx-...` |
| `{MANAGED-IDENTITY-CLIENT-ID-DEV}` | Managed identity client ID for dev. | `xxxxxxxx-...` |
| `{MANAGED-IDENTITY-CLIENT-ID-TEST}` | Managed identity client ID for test. | `xxxxxxxx-...` |
| `{MANAGED-IDENTITY-CLIENT-ID-ABN}` | Managed identity client ID for abn. | `xxxxxxxx-...` |
| `{APIM-HOST}` | Azure API Management host/gateway URL. | `api.myapp.example.com` |
| `{LEANIX-APPLICATION-ID}` | LeanIX application ID (enterprise architecture tool). | `xxxxxxxx-...` |
| `{cluster-domain}` | Kubernetes cluster ingress domain. | `myapp.example.com` |
| `{kubernetes-tenant}` | Kubernetes tenant identifier. | `myapp` |

**Files with the highest concentration:**
- `csharp/azure/helm/*/values*.yaml`
- `csharp/azure/infrastructure/*.bicep`
- `csharp/azure/infrastructure/parameters*.bicepparam`

---

## Group 5 — Authentication & Identity (Azure AD)

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{AZURE-AD-TENANT-ID}` | Azure Active Directory tenant ID. | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `{AZURE-AD-CLIENT-ID-DEV}` | App registration client ID for dev. | `xxxxxxxx-...` |
| `{AZURE-AD-CLIENT-ID-TEST}` | App registration client ID for test. | `xxxxxxxx-...` |
| `{AZURE-AD-CLIENT-ID-ABN}` | App registration client ID for abn. | `xxxxxxxx-...` |
| `{AZURE-AD-CLIENT-ID-PROD}` | App registration client ID for prod. | `xxxxxxxx-...` |
| `{AZURE-AD-GROUP-OBJECT-ID}` | AAD group object ID. | `xxxxxxxx-...` |
| `{AZURE-AD-GROUP-NAME}` | AAD group display name. | `myapp-developers` |
| `{AZURE-AD-LZ-GROUP-OBJECT-ID}` | Landing zone AAD group object ID. | `xxxxxxxx-...` |
| `{AZURE-AD-OBJECT-ID}` | General AAD object ID. | `xxxxxxxx-...` |
| `{TEAM-AAD-GROUP-NAME}` | Team-level AAD group name. | `myapp-team` |
| `{OIDC-ISSUER-URL}` | OIDC issuer URL for authentication. | `https://login.microsoftonline.com/{tenant}/v2.0` |
| `{SWAGGER-CLIENT-ID-DEV}` | Swagger UI OAuth2 client ID for dev. | `xxxxxxxx-...` |
| `{AUTH-PROVIDER}` | Authentication provider name. | `Azure AD` |
| `{USER-PRINCIPAL-NAME}` | Service account UPN for deployments. | `svc-myapp@mycompany.com` |

**Files with the highest concentration:**
- `csharp/azure/infrastructure/parameters*.bicepparam`
- `csharp/azure/variables/*.yml`

---

## Group 6 — Legacy System

These describe the source system being migrated away from.

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{LEGACY-SYSTEM-NAME}` / `{LEGACY-SYSTEM}` | Human-readable name of the legacy system. | `Legacy Portal` |
| `{LEGACY-TECH}` | Technology stack of the legacy system. | `ColdFusion` / `COBOL` / `VB6` |
| `{LEGACY-DB-NAME}` / `{LEGACY_DB_NAME}` | Legacy database name. | `LegacyDB` |
| `{LEGACY-DB-DIR}` | Directory path to legacy SQL files. | `legacy-sql/LegacyDB` |
| `{LEGACY-CODEBASE-DIR}` | Directory path to legacy application code. | `to_be_migrated_repo/legacy-app` |
| `{LEGACY-CF-APP-DIR}` | Path within `to_be_migrated_repo/` to legacy app source. | `CF_apps_Legacy` |
| `{SQL_ROOT}` | Absolute or relative root path for SQL analysis scripts. | `/workspace/legacy-sql` |
| `{SQL_MEMORY_LIMIT_MB}` | Memory limit for SQL analysis. | `4096` |

**Files with the highest concentration:**
- `legacy-sql/AGENTS.md`, `legacy-sql/README.md`
- `to_be_migrated_repo/README.md`
- `.agents/skills/legacy-sql-analysis/SKILL.md` and scripts
- `.agents/subagents/requirements-site/agent_migration_requirements.md`

---

## Group 7 — Specification / Source Documents

These identify the documents from which requirements are extracted.

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{SPEC-DOCUMENT}` / `{SPECIFICATION-DOCUMENT}` | Primary specification document name. | `Technical Requirements Doc` |
| `{SPEC-DOCUMENT-1}` | First specification document ID (SRC-* format). | `SRC-SPEC-001` |
| `{SPEC-DOCUMENT-1-PREFIX}` | Citation prefix used in section references for SPEC-1. | `TRD §` |
| `{SPEC-DOCUMENT-2}` | Second specification document ID. | `SRC-SPEC-002` |
| `{SPEC-DOCUMENT-2-PREFIX}` | Citation prefix for SPEC-2. | `Annex §` |
| `{DOCUMENT-NAME}` | Generic document name placeholder. | `Requirements Workbook` |
| `{AZURE-BOARDS-SOURCE}` | Azure Boards export source ID (SRC-* format). | `SRC-AZDO` |

**Key file:** `docs/requirements/sources/SRC-EXAMPLE-001.md` — the example shows the file format.

**Also update in `tools/requirements-site/hooks/cross_refs.py`:**
```python
_SPEC_SOURCE_ID = "SRC-EXAMPLE-001"  # Replace with your actual spec document ID
_SPEC_INDEX_REL = "sources/spec-section-index.yaml"  # Rename to match
```

---

## Group 8 — External Services & Integrations

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{EXTERNAL-SYSTEM}` / `{SERVICE-A}` / `{SERVICE-B}` | External service your app integrates with. | `SAP` / `Salesforce` |
| `{EXTERNAL-API}` | External API name. | `Payment Gateway API` |
| `{EXTERNAL-SEARCH-API}` | External search service. | `Elasticsearch` / `Typesense` |
| `{UI-FRAMEWORK}` | Frontend UI component library. | `Material UI` / `Ant Design` |
| `{EVENT-BUS}` | Event bus / message broker. | `Apache Kafka` / `Azure Service Bus` |
| `{CLIENT-REPO-URL}` | URL of the client's delivery repository. | `https://dev.azure.com/org/project/_git/repo` |
| `{CLIENT-REPO-NAME}` | Client delivery repo name. | `MyApp-Client` |
| `{CLIENT-REPO-BRANCH}` | Branch to sync to in the client repo. | `main` |
| `{SONARQUBE-URL}` | SonarQube / SonarCloud URL. | `https://sonarcloud.io` |

---

## Group 9 — MkDocs Requirements Site

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{SITE_BASE_URL}` | Base URL where the requirements site is hosted. | `https://myapp.example.com/requirements` |
| `{STATIC-WEB-APP-NAME}` | Azure Static Web App resource name. | `swa-myapp-requirements` |

**File:** `tools/requirements-site/mkdocs.yml` — update `site_name`, `site_url`, logo, and nav entries.

---

## Group 10 — Environment Variables (Runtime)

These appear as Docker/CI environment variable names — replace the value template.

| Placeholder | Description | Example |
|------------|-------------|---------|
| `{PROJECT_NAME_DB_CONNECTION_STRING}` | Env var name for DB connection string. | `MYAPP_DB_CONNECTION_STRING` |
| `{PROJECT_NAME_API_CERTIFICATE_PASSWORD}` | Env var name for API cert password. | `MYAPP_API_CERTIFICATE_PASSWORD` |
| `{PROJECT_API_CERTIFICATE_PASSWORD}` | Same as above (shorter variant). | `MYAPP_CERT_PASSWORD` |
| `{DEFAULT_TOKEN_ENV}` | Env var holding the default auth token. | `MYAPP_DEFAULT_TOKEN` |
| `{API_HTTP_PORT}` | HTTP port the API listens on. | `8080` |
| `{DOCKER_REGISTRY-}` | Docker registry prefix for image names. | `myregistry.azurecr.io/` |

---

## Group 11 — Requirements Content Placeholders

These appear inside example requirement/feature/product files and need to be filled in as you author content (not a one-time setup step).

| Placeholder | Description |
|------------|-------------|
| `{FEATURE-NAME}` | Placeholder feature name in example files. |
| `{DOMAIN-NAME}` | Placeholder domain name. |
| `{PRODUCT-NAME}` | Placeholder product name. |
| `{PRODUCT-CODE}` | Short product code (2–4 chars). |
| `{PRODUCT-NNN}` | Product ID number. |
| `{REQ-ID}` | Requirement ID reference. |
| `{FEAT-ID}` | Feature ID reference. |
| `{EPIC-ID}` | Epic ID reference. |
| `{PRODUCT-ID}` | Product ID reference. |
| `{TOPIC}` | Generic topic name in example eval files. |
| `{TEST-NAME}` | Generic test name placeholder. |
| `{PAGE-TYPE-ID}` | UI page type ID. |
| `{SOURCE-TYPE}` | Source category label. |
| `{NAME}` | Generic name placeholder. |
| `{SEQUENCE}` | Numeric sequence placeholder. |
| `{YYYY-MM-DD}` | Date placeholder — replace with actual date. |

---

## Placeholder filenames & folders (rename on disk)

Placeholders and client/example tokens also appear in **file and folder names** — not just in
file contents. A search-and-replace over contents is **not enough**; these paths must be
**renamed on disk**, and any reference to the old path (nav entries, scripts, doc links,
imports) updated. The `setup-repo-structure` skill does this in its "Rename files and folders"
step.

| Path | Rename to | Why |
|------|-----------|-----|
| `csharp/tools/local-dev/Dockerfile.{project-name}-ui` | `Dockerfile.<project>-ui` | `start-docker.sh` / `start-podman.sh` reference it via the replaced `{project-name}`; the filename must match. |
| `docs/architecture/project-technical-guidelines.md` | `{project-name}-technical-guidelines.md` | Make the doc name match the project. |
| `docs/requirements/sources/SRC-EXAMPLE-001.md` | your real source-document ID (e.g. `SRC-TRD-001.md`) | The ID must match the `id:` and how requirements cite it. |
| `csharp/src/backend/Example/` | your backend root layout (e.g. `{ClientName}.{ProjectName}.*`) | Example backend scaffold; rename to your real project structure. |
| `csharp/src/backend/Example/Infrastructure/Mock/{EXAMPLE-CRM-MOCK,EXAMPLE-DATABASE-MOCK,EXAMPLE-SITE-MOCK}/` | your external service names (e.g. `CustomerService/`, `AddressService/`) | One example folder per mock mechanism (DI-swap / DB-seed / HTTP-WireMock). Rename each folder **and** update its `AGENTS.md` plus the index in `Mock/AGENTS.md`. |
| `openspec/changes/example-feature-change/` | delete, or rename to your first real change | Illustrative OpenSpec change. |
| `docs/requirements/**/*-EXAMPLE-001.md`, `reports/evaluations/EVAL-EXAMPLE-001.md` | replace as you author real content | Example content files; IDs follow each type's pattern. |

**Discovery commands** — run after setup to confirm nothing was missed:

```bash
# Any remaining literal {…} placeholder in a path?
find . -path ./.git -prune -o \( -name '*{*' -o -name '*}*' \) -print
# Anything still named after the template (example folders/files not yet replaced)?
find . -path ./.git -prune -o -iname '*EXAMPLE*' -print
```

---

## Version control (`.gitmodules` / `.gitattributes`)

`.gitmodules` ships with **commented-out example** submodule blocks (no active submodules, no real
URLs). Uncomment and fill only the ones the project actually vendors; otherwise leave them
commented. `.gitattributes` is already generic (LF normalization, CRLF for `*.ps1/.cmd/.bat`,
binary-asset rules) and usually needs no change.

| Placeholder | Used in | Example |
|------------|---------|---------|
| `{CLIENT-REPO-NAME}` / `{CLIENT-REPO-URL}` / `{CLIENT-REPO-BRANCH}` | active client/delivery submodule (path `csharp/{CLIENT-REPO-NAME}`) | `MyApp` / `https://dev.azure.com/org/proj/_git/MyApp` / `main` |
| `{LEGACY-CODEBASE-DIR}` / `{LEGACY-CODEBASE-REPO-URL}` / `{LEGACY-CODEBASE-BRANCH}` | legacy-code submodule (path `to_be_migrated_repo/{LEGACY-CODEBASE-DIR}`) | `legacy-app` / `https://…/_git/legacy-app` / `master` |
| `{LEGACY-DB-NAME}` / `{LEGACY-DB-REPO-URL}` | legacy SQL DB submodule (path `legacy-sql/{LEGACY-DB-NAME}`) | `LegacyDB` / `https://…/_git/LegacyDB` |

---

## Checklist: Files that always need updating when starting a new project

Run through this list manually after completing the automated setup:

- [ ] `AGENTS.md` — project context paragraph
- [ ] `CLAUDE.md` — any residual project references
- [ ] `README.md` — project name, description, getting started
- [ ] `tools/requirements-site/mkdocs.yml` — `site_name`, `site_url`, logo
- [ ] `tools/requirements-site/hooks/cross_refs.py` — `_SPEC_SOURCE_ID`, `_SPEC_INDEX_REL`, `_SCREEN_INDEXES`, `_SCREEN_FOLDERS`
- [ ] `docs/architecture/project-technical-guidelines.md` — rename this file to match your project (e.g., `{project-name}-technical-guidelines.md`)
- [ ] `csharp/tools/local-dev/Dockerfile.{project-name}-ui` — rename this file once `{project-name}` is replaced (the `start-docker.sh` / `start-podman.sh` scripts reference it as `Dockerfile.{project-name}-ui`)
- [ ] `docs/requirements/sources/` — replace `SRC-EXAMPLE-001.md` with your real source documents
- [ ] `csharp/azure/variables/common-variables.yml` — pipeline variable values
- [ ] `csharp/azure/variables/variables-*.yml` — per-environment values
- [ ] `.agents/skills/requirement-synthesis/product-manifest.yaml` — replace example products
- [ ] `.agents/skills/legacy-sql-analysis/scripts/generate_report.py` — `concept_mappings` spec_terms and PDF_SOURCES
- [ ] `csharp/src/backend/Example/` — rename/replace mock service folders with your actual external service names
