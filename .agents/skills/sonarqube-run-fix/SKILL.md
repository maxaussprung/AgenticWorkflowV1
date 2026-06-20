---
name: sonarqube-run-fix
description: Fetch SonarCloud/SonarQube issues for this repo's backend, frontend, or both projects, stop with clear guidance when required Sonar environment variables are missing, then triage and fix safe code-quality issues. Use when the user asks to run SonarQube/SonarCloud fixes, feed Sonar results to the agent, or remediate quality-gate issues.
---

# SonarQube Run Fix

Use this skill to fetch current SonarCloud findings for the repo-owned backend and frontend
projects, triage them, and apply safe fixes in the working tree.

The workflow is intentionally token-driven because this repository does not use an Azure
SonarCloud service connection.

## Required Context

Read these before fixing code:

- `AGENTS.md`
- `.sonarcloud.properties`
- `azure-pipelines-csharp-backend-build.yml`
- `azure-pipelines-csharp-fe-build.yml`
- The local `AGENTS.md` for any code area you will touch, for example:
  - `csharp/src/backend/AGENTS.md`
  - `csharp/src/frontend/AGENTS.md`

## Required Environment

For `both`, these variables must be set:

- `SONAR_TOKEN`
- `SONAR_CLOUD_ORGANIZATION`
- `SONAR_CLOUD_BACKEND_PROJECT_KEY`
- `SONAR_CLOUD_FRONTEND_PROJECT_KEY`

For scoped runs, only the selected project key is required:

- backend: `SONAR_CLOUD_BACKEND_PROJECT_KEY`
- frontend: `SONAR_CLOUD_FRONTEND_PROJECT_KEY`

Optional variables:

- `SONAR_HOST_URL` defaults to `https://sonarcloud.io`
- `SONAR_BRANCH` queries a branch-specific analysis
- `SONAR_PULL_REQUEST` queries a pull-request analysis

If a required variable is missing, report the missing variable names to the developer and
terminate. Do not ask the developer to paste token values into chat, and do not make code edits.

## Fetch Issues

Before running the exporter, determine the project scope from the user's request.

Valid scopes are:

- `backend`
- `frontend`
- `both`

If the developer did not specify a scope, ask them to choose exactly one of these three options
before running the exporter. Do not infer from changed files.

```bash
python3 .agents/skills/sonarqube-run-fix/scripts/export_sonarcloud_issues.py --scope backend
python3 .agents/skills/sonarqube-run-fix/scripts/export_sonarcloud_issues.py --scope frontend
python3 .agents/skills/sonarqube-run-fix/scripts/export_sonarcloud_issues.py --scope both
```

The script writes:

- `reports/test-results/sonarcloud/issues.json`
- `reports/test-results/sonarcloud/backend-issues.json` when backend is queried
- `reports/test-results/sonarcloud/frontend-issues.json` when frontend is queried
- `reports/test-results/sonarcloud/summary.md`

If the script exits because environment variables are missing, relay its message and stop. If the
API fails with authentication or authorization errors, report the status and stop without edits.

## Triage Rules

Work from `summary.md` and the JSON files.

1. Fix issues in this order: security vulnerabilities, bugs, blocker/critical maintainability
   issues, then major code smells.
2. Group issues by file so one focused edit can address related findings.
3. Prefer direct code fixes over suppressions.
4. Do not mark issues false-positive or accepted in SonarCloud unless the developer explicitly
   asks for that.
5. If an issue is in generated code, Dockerfile, pipeline YAML, DTO boilerplate, or another file
   that should not be analyzed, update scanner/coverage configuration instead of editing source.
6. If a finding changes behavior or touches business logic, add or update tests.
7. If a security issue is ambiguous, stop and ask before changing behavior.
8. Never edit `to_be_migrated_repo/` or `legacy-sql/`.

## Fix Workflow

1. Inspect `git status --porcelain`.
2. Fetch issues with the exporter.
3. Read the affected source files before editing.
4. Apply small, reviewable fixes.
5. Run the smallest relevant validation:
   - Backend unit tests:
     `dotnet test {BACKEND-TEST-PROJECT}/{BACKEND-UNIT-TEST-PROJECT}.csproj --no-restore`
   - Backend integration tests when API/persistence behavior changed:
     `dotnet test {BACKEND-TEST-PROJECT}/{BACKEND-INTEGRATION-TEST-PROJECT}.csproj --no-restore`
   - Frontend from `csharp/src/frontend`:
     `pnpm lint`
     `pnpm typecheck`
     `pnpm test:ci`
6. Do not claim SonarCloud is clean until a new SonarCloud analysis has run. Local code fixes do
   not update the server-side issue state by themselves.

## Final Report

Report:

- Queried project scope and artifact paths.
- Number of open issues fetched by project.
- Issues fixed, grouped by file and Sonar rule.
- Validation commands run and their result.
- Issues intentionally left unresolved and why.
- Whether a new CI/SonarCloud run is required to confirm closure.
