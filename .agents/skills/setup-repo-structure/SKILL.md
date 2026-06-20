# Skill: setup-repo-structure

**Purpose:** Interactive first-time setup of this repository template for a new project. Guides the user through a series of questions, then performs all placeholder replacements across the entire repo.

**When to use:** After cloning this template for a new project, before any development work starts.

---

## How this skill works

The agent asks a sequence of questions, collects all answers, then performs bulk find-and-replace across the repo. The user only needs to answer the questions — the agent handles all file edits.

All placeholder patterns and their locations are documented in [`project-placeholders.md`](../../../docs/architecture/project-placeholders.md) (under `docs/architecture/`).

---

## Question sequence

Ask the questions in this exact order. Wait for the user's answer before moving to the next. Mark optional questions clearly.

---

### Phase 1 — Core Identity (required)

**Q1. Project name**
> "What is the name of this project? This will appear in documentation headings, CI pipeline display names, and the requirements site title. (Example: `MyApp` or `Customer Portal`)"

- Replaces: `{PROJECT-NAME}`, `{project-name}`
- Also derive a short slug (lowercase, hyphenated): `{PROJECT}`, `{project}` — confirm with user if not obvious from the name

**Q2. Client / organization name**
> "What is the name of the client or organization? (Example: `Accenture GmbH` or `ACME Corp`)"

- Replaces: `{CLIENT-NAME}`, `{client-name}`

**Q3. Team name**
> "What is the name of the development team? (Example: `Platform Team` or `Migration Squad`) [optional — press Enter to skip]"

- Replaces: `{PROJECT-TEAM}`

---

### Phase 2 — Tech Stack (required)

**Q4. Backend language / framework**
> "What is the backend technology? Choose one:
> 1. C# / .NET (ASP.NET Core)
> 2. Java / Spring Boot
> 3. Python / FastAPI or Django
> 4. Node.js / TypeScript
> 5. Other (describe)"

If C# / .NET:
- **Q4a.** "What is the root C# namespace? (Example: `MyCompany.MyApp`)"
  - Replaces: `{BACKEND-NAMESPACE}`
  - Derive project names: `{BACKEND-API-PROJECT}` = `{namespace}.Api`, `{BACKEND-DOMAIN-PROJECT}` = `{namespace}.Domain`, etc.
  - Ask: "Do you want to use the standard layer names (Api, Domain, Application, Infrastructure, SharedKernel) or custom names?"

If other stack:
- Note that Helm charts, Bicep IaC, and pipeline templates are C#/.NET specific. Ask: "Do you want to keep the Azure/C# infrastructure structure as a template, or remove it?"
- Replaces all `{BACKEND-*-PROJECT}` with the equivalent structure for their stack

**Q5. Frontend framework**
> "What is the frontend technology? Choose one:
> 1. React / TypeScript (Vite or CRA)
> 2. Angular
> 3. Vue.js
> 4. No frontend (API only)
> 5. Other (describe)"

**Q6. Application display name (for Helm / deployment)**
> "What short name should be used for Kubernetes deployments and Docker image tags? (lowercase, no spaces — example: `myapp`)"

- Replaces: `{APP-NAME}`, `{IMAGE_PREFIX}`

---

### Phase 3 — Azure DevOps & CI/CD (required if using Azure)

**Q7. Azure DevOps details**
> "What is your Azure DevOps organization name? (the part after `dev.azure.com/` — example: `my-org`)"
- Replaces: `{AZURE-DEVOPS-ORG}`

> "What is your Azure DevOps project name? (example: `MyProject`)"
- Replaces: `{AZURE-DEVOPS-PROJECT}`

> "What is the repository name in Azure DevOps? (example: `MyApp`)"
- Replaces: `{REPO-NAME}`

**Q8. Build agent pool**
> "What build agent pool should the pipelines use? (default: `ubuntu-latest`, or your organization's pool name)"
- Replaces: `{BUILD-AGENT-POOL}`

**Q9. Container registry**
> "What is your Azure Container Registry name (without `.azurecr.io`)? (example: `myregistry`) [optional — skip if not using containers]"
- Replaces: `{CONTAINER-REGISTRY}`

---

### Phase 4 — Legacy System (required)

**Q10. Legacy system name**
> "What is the name of the legacy system being migrated? (example: `Legacy CRM Portal`)"
- Replaces: `{LEGACY-SYSTEM-NAME}`, `{LEGACY-SYSTEM}`

**Q11. Legacy technology**
> "What technology does the legacy system use? (example: `ColdFusion`, `COBOL`, `VB6`, `ASP Classic`)"
- Replaces: `{LEGACY-TECH}`

**Q12. Legacy database name**
> "What is the legacy database name? (example: `LegacyDB` or `CustomerDB`) [optional — skip if no DB analysis planned]"
- Replaces: `{LEGACY-DB-NAME}`, `{LEGACY_DB_NAME}`, `{LEGACY-DB-DIR}`

---

### Phase 5 — Specification Documents (required)

**Q13. Primary specification document**
> "What is the name of the main specification document (requirements source)? This will become SRC-001 in the requirements system. (example: `Technical Requirements Spec` or `Functional Design Document`)"
- Replaces: `{SPEC-DOCUMENT}`, `{SPEC-DOCUMENT-1}`, `{SPECIFICATION-DOCUMENT}`
- Also ask: "What citation prefix does this document use in section references? (example: `§` or `TRD §` or `Annex §`)"
  - Replaces: `{SPEC-DOCUMENT-1-PREFIX}`
  - Update `tools/requirements-site/hooks/cross_refs.py`: `_SPEC_SOURCE_ID = "SRC-{PREFIX}-001"` and `_SPEC_INDEX_REL`

**Q14. Additional specification documents** [optional]
> "Are there additional specification documents to register? (example: a second PDF, a requirements workbook, or an Azure Boards export) [yes/no]"
- If yes: collect name and prefix for each, create SRC-*.md files in `docs/requirements/sources/`
- Replaces: `{SPEC-DOCUMENT-2}`, `{SPEC-DOCUMENT-2-PREFIX}`, `{AZURE-BOARDS-SOURCE}`

---

### Phase 6 — External Services [optional]

**Q15. External services**
> "Does the new application integrate with external services? List them (comma-separated), or press Enter to skip. (example: `SAP, Salesforce, Kafka`)"
- Replaces: `{EXTERNAL-SYSTEM}`, `{SERVICE-A}`, `{SERVICE-B}`, `{EXTERNAL-API}`, `{EXTERNAL-SEARCH-API}`
- Also update `csharp/src/backend/Example/Infrastructure/Mock/` folder names

**Q16. Authentication provider**
> "What authentication provider will be used? (default: `Azure AD`)"
- Replaces: `{AUTH-PROVIDER}`

**Q17. UI framework / component library** [optional]
> "What UI component library does the frontend use? (example: `Material UI`, `Ant Design`, `Tailwind CSS`)"
- Replaces: `{UI-FRAMEWORK}`

---

### Phase 7 — Infrastructure Details [optional / fill later]

Skip this phase if the user does not yet have Azure resource details. These can be filled in later directly in the variable files.

**Q18. Azure subscriptions** [optional]
> "Do you have Azure subscription IDs for the deployment environments? (dev/test/abn/prod) [yes to enter now / no to skip]"
- Replaces: `{SUBSCRIPTION-ID-DEV}`, `{SUBSCRIPTION-ID-TEST}`, `{SUBSCRIPTION-ID-ABN}`, `{SUBSCRIPTION-ID-PROD}`, `{ESP-SUBSCRIPTION-ID}`

**Q19. Azure AD tenant ID** [optional]
> "What is the Azure AD tenant ID? (UUID format) [optional — skip to fill later]"
- Replaces: `{AZURE-AD-TENANT-ID}`

---

### Phase 8 — Version control & submodules [optional]

The template ships `.gitmodules` with **commented-out example** submodule blocks and a generic
`.gitattributes`. Ask whether the project vendors any external repos as git submodules.

**Q20. Submodules** [optional]
> "Will this repo include any external repos as git submodules? Typical ones: (a) the existing
> client/delivery codebase, (b) the legacy codebase being migrated, (c) the legacy SQL database.
> List the ones you want, with their clone URLs — or press Enter to skip (no submodules)."

- For each chosen submodule, uncomment + fill the matching block in `.gitmodules` and replace:
  - Client code: `{CLIENT-REPO-NAME}`, `{CLIENT-REPO-URL}`, `{CLIENT-REPO-BRANCH}` (path `csharp/{CLIENT-REPO-NAME}`)
  - Legacy code: `{LEGACY-CODEBASE-DIR}`, `{LEGACY-CODEBASE-REPO-URL}`, `{LEGACY-CODEBASE-BRANCH}` (path `to_be_migrated_repo/{LEGACY-CODEBASE-DIR}`)
  - Legacy SQL DB: `{LEGACY-DB-NAME}`, `{LEGACY-DB-REPO-URL}` (path `legacy-sql/{LEGACY-DB-NAME}`)
- If the user skips, **leave every block commented out** — do not invent submodule URLs.
- `.gitattributes` is already generic (LF normalization, CRLF for `*.ps1/.cmd/.bat`, binary asset rules);
  only adjust it if the project adds new binary/text file types.

---

## Execution: Performing the replacements

Replacement happens at **two levels** — do not forget the second:

1. **File contents** — the find-and-replace passes in Steps 1–5 below.
2. **File and folder NAMES** — some paths contain a placeholder (e.g.
   `Dockerfile.{project-name}-ui`) or a client/example token (e.g. `Mock/EXAMPLE-CRM-MOCK/`,
   `SRC-EXAMPLE-001.md`) **in the name itself**. These must be **renamed on disk** in Step 6,
   or references to them break. A content-only pass is never enough.

After collecting all answers, perform replacements in this order:

### Step 1 — Core identity replacements
```python
replacements = {
    "{PROJECT-NAME}": answers["project_name"],
    "{project-name}": answers["project_slug"],
    "{PROJECT}": answers["project_slug"],
    "{project}": answers["project_slug"],
    "{CLIENT-NAME}": answers["client_name"],
    "{client-name}": answers["client_name"].lower().replace(" ", "-"),
    "{PROJECT-TEAM}": answers.get("team_name", "TBD"),
    "{PLATFORM-NAME}": f"{answers['project_name']} Platform",
}
```

Apply to ALL files matching:
`*.md *.yml *.yaml *.py *.sh *.html *.json *.bicep *.bicepparam *.tpl *.ts *.tsx`

Exclude `.git/` and `node_modules/`.

### Step 2 — Backend namespace replacements (C# only)
```python
ns = answers["backend_namespace"]  # e.g. "MyCompany.MyApp"
parts = ns.split(".")[-1]  # "MyApp"

replacements.update({
    "{BACKEND-NAMESPACE}": ns,
    "{BACKEND-API-PROJECT}": f"{ns}.Api",
    "{BACKEND-DOMAIN-PROJECT}": f"{ns}.Domain",
    "{BACKEND-APPLICATION-PROJECT}": f"{ns}.Application",
    "{BACKEND-INFRASTRUCTURE-PROJECT}": f"{ns}.Infrastructure",
    "{BACKEND-SHAREDKERNEL-PROJECT}": f"{ns}.SharedKernel",
    "{BACKEND-TEST-PROJECT}": f"{ns}.Tests",
    "{BACKEND-UNIT-TEST-PROJECT}": f"{ns}.UnitTests",
    "{BACKEND-INTEGRATION-TEST-PROJECT}": f"{ns}.IntegrationTests",
    "{APP-NAME}": answers["app_name"],
    "{IMAGE_PREFIX}": answers["app_name"],
})
```

### Step 3 — Azure DevOps replacements
```python
replacements.update({
    "{AZURE-DEVOPS-ORG}": answers["ado_org"],
    "{AZURE-DEVOPS-PROJECT}": answers["ado_project"],
    "{REPO-NAME}": answers["repo_name"],
    "{BUILD-AGENT-POOL}": answers.get("agent_pool", "ubuntu-latest"),
    "{CONTAINER-REGISTRY}": answers.get("container_registry", "{CONTAINER-REGISTRY}"),
})
```

### Step 4 — Legacy system replacements
```python
replacements.update({
    "{LEGACY-SYSTEM-NAME}": answers["legacy_system_name"],
    "{LEGACY-SYSTEM}": answers["legacy_system_name"],
    "{LEGACY-TECH}": answers["legacy_tech"],
    "{LEGACY-DB-NAME}": answers.get("legacy_db_name", "{LEGACY-DB-NAME}"),
    "{LEGACY_DB_NAME}": answers.get("legacy_db_name", "{LEGACY_DB_NAME}"),
    "{LEGACY-DB-DIR}": f"legacy-sql/{answers.get('legacy_db_name', 'LegacyDB')}",
})
```

### Step 5 — Spec document replacements
```python
spec_id = f"SRC-{answers['spec_doc_name'][:4].upper()}-001"
replacements.update({
    "{SPEC-DOCUMENT}": answers["spec_doc_name"],
    "{SPEC-DOCUMENT-1}": spec_id,
    "{SPEC-DOCUMENT-1-PREFIX}": answers.get("spec_prefix", "§"),
    "{SPECIFICATION-DOCUMENT}": answers["spec_doc_name"],
})
# Update cross_refs.py
# _SPEC_SOURCE_ID = spec_id
# _SPEC_INDEX_REL = f"sources/{spec_id.lower()}-section-index.yaml"
```

### Step 6 — Rename files and folders (names, not just contents)

Steps 1–5 only changed file **contents**. The paths below carry a placeholder or
client/example token **in their name** and must be **renamed on disk**. After each rename,
grep for the old path and fix any reference to it (nav entries, scripts, doc links, imports).

**A. Paths with a literal `{…}` placeholder in the name — always rename:**

- `csharp/tools/local-dev/Dockerfile.{project-name}-ui` → `Dockerfile.<project>-ui`
  (use the same slug chosen for `{project-name}`). `start-docker.sh` and `start-podman.sh`
  reference it via the now-replaced `{project-name}`, so the filename **must** match.

**B. Paths named after the template/previous client — rename once you have the real value:**

- `docs/architecture/project-technical-guidelines.md` → `{project-name}-technical-guidelines.md` (update any links to it)
- `docs/requirements/sources/SRC-EXAMPLE-001.md` → your real source-document ID (e.g. `SRC-TRD-001.md`)
- `csharp/src/backend/Example/` → your backend root layout (e.g. `{ClientName}.{ProjectName}.*` project folders)
- `csharp/src/backend/Example/Infrastructure/Mock/{EXAMPLE-CRM-MOCK,EXAMPLE-DATABASE-MOCK,EXAMPLE-SITE-MOCK}/` → your external service names (rename each folder **and** update its `AGENTS.md` title/links, plus the table + links in `Mock/AGENTS.md`)
- `openspec/changes/example-feature-change/` → delete, or rename to your first real change

**C. `*-EXAMPLE-001.md` content files** (under `docs/requirements/**` and `reports/evaluations/`)
are illustrative templates. Leave them as a reference, or rename/replace them as you author real
content — IDs follow each type's documented pattern (`REQ-<AREA>-<NNN>`, `FEAT-<NNN>`, etc.).

**Discovery — run before finishing** to make sure nothing was missed:

```bash
# Any remaining placeholder filenames?
find . -path ./.git -prune -o \( -name '*{*' -o -name '*}*' \) -print
# Anything still named after the template/old client?
find . -path ./.git -prune -o -iname '*EXAMPLE*' -print   # example folders/files still to be renamed/replaced
```

### Step 7 — Version control

1. **`.gitmodules`** — per Phase 8: uncomment + fill the example blocks for submodules the project
   actually uses, or leave them all commented if it vendors none. Never leave a real client URL in.
2. **`.gitattributes`** — already generic; only extend it if the project introduces new binary/text
   file types.
3. After all renames, also rename any **mock service folders** the project keeps
   (`Mock/EXAMPLE-*-MOCK/` → real service names) and update both the folder's `AGENTS.md` and the
   index/table/links in `Mock/AGENTS.md`.

### Step 8 — Finish

1. **Update `.agents/skills/requirement-synthesis/product-manifest.yaml`** with your actual products.
2. **Report a summary** of what was replaced **and renamed**, plus a checklist of manual steps remaining.

---

## Manual steps reminder (always shown at the end)

After automated replacement, remind the user to:

```
✅ Automated replacements done.

📋 Manual steps still required:
1. Fill Azure AD client IDs and managed identity IDs in csharp/azure/variables/
2. Fill AKS cluster names and resource group names in csharp/azure/variables/
3. Register SRC-*.md source documents in docs/requirements/sources/
4. Update .agents/skills/requirement-synthesis/product-manifest.yaml with your products
5. Update .agents/skills/legacy-sql-analysis/scripts/generate_report.py:
   - concept_mappings spec_terms with your domain terminology
   - PDF_SOURCES with your actual spec document paths
6. Add your project logo and favicon to docs/requirements/assets/
7. See docs/architecture/project-placeholders.md for a complete reference of all remaining {PLACEHOLDER} values
```

---

## Notes for the executing agent

- Make replacements using Edit or Write tools (not shell sed) where files are small enough to read; use Bash sed for large files (>500 lines).
- Always skip `.git/` directory.
- After replacements, run `grep -r "{PROJECT-NAME}" .` to verify no core placeholders remain.
- **Placeholders appear in file/folder NAMES, not only in contents.** A content-only pass leaves paths like `Dockerfile.{project-name}-ui` broken. After the content pass, perform the Step 6 renames, then run `find . -path ./.git -prune -o -name '*{*' -print` to confirm no placeholder paths remain.
- If a replacement would break a YAML or JSON structure (e.g., a value contains characters that need quoting), handle it carefully.
- Do NOT replace placeholders inside code comments that explain what the placeholder means — only replace actual value positions.
- Log every file modified at the end of the run.
