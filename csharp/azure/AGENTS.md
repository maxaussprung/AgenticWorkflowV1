# csharp/azure/ Agent Instructions

Applies to `csharp/azure/` — Azure Pipelines templates, Helm charts, Bicep infrastructure, and
deployment scripts.

Read the repository root [`AGENTS.md`](../../AGENTS.md) and the area [`csharp/AGENTS.md`](../AGENTS.md) first.

## Layout

```
azure/
├── pipeline/          # YAML templates included by csharp/azure-pipelines*.yml
│                      #   stage-build, stage-deploy, stage-e2e-tests,
│                      #   job-build-api, job-build-frontend,
│                      #   job-build-push-docker-image, job-deploy-database,
│                      #   job-install-and-run-playwright, etc.
├── infrastructure/    # Bicep modules (.bicep) for environment provisioning
├── helm/              # Helm charts: backend/, frontend/, kafka-consumers/, typesense/
├── scripts/           # Helper shell scripts (e.g. check_quality_gate.sh)
└── variables/         # Per-environment variable group YAML
```

Top-level pipelines live one level up:
[`../azure-pipelines.yml`](../azure-pipelines.yml) (main),
[`../azure-pipelines-kafka-consumers.yml`](../azure-pipelines-kafka-consumers.yml),
[`../azure-pipelines-typesense.yml`](../azure-pipelines-typesense.yml).

## Conventions

- **Templates over duplication.** New CI logic goes into a `pipeline/job-*.yml` or
  `pipeline/stage-*.yml` template and is included from the top-level pipeline — do not inline
  build/test/deploy steps in the top-level YAML.
- **Naming:** `stage-<purpose>.yml` for stages, `job-<purpose>.yml` for jobs. Match existing
  hyphen-case.
- **Coverage flow** (backend): `dotnet test … --collect "Code Coverage" --settings $(Build.SourcesDirectory)/codeCoverage.runsettings`
  → `dotnet-coverage merge` → `PublishCodeCoverageResults@2`. Do not invent a second coverage path.
- **Quality gate:** SonarQube polling lives in `scripts/check_quality_gate.sh`. Reuse it; do not
  reimplement.
- **Helm:** one chart per deployable (backend / frontend / kafka-consumers / typesense). Bump
  `Chart.yaml` `version` on packaging changes; bump `appVersion` only when shipping a new image
  tag scheme.
- **Bicep:** modules under `infrastructure/modules/` are consumed by the top-level Bicep files;
  keep modules parameter-driven and environment-agnostic.

## Anti-Patterns

- Do not edit `../../azure-pipelines-guardrails.yml` — it is the legacy codebase freeze enforcer.
- Do not commit secrets, PATs, connection strings, or storage keys to YAML / Bicep / Helm
  values. Use Azure DevOps secret variables and Key Vault references.
- Do not run `dotnet ef database update` from pipeline steps directly — use
  [`pipeline/job-deploy-database.yml`](pipeline/job-deploy-database.yml).
- Do not write CI build output back into the repo. Publish via `PublishBuildArtifacts@1` /
  `PublishPipelineArtifact@1` only.
- Do not introduce per-developer pipeline triggers (`pr:` on feature branches) — keep PR
  validation on `master` only.
