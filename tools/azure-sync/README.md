# azure-sync

Reconciles `docs/requirements/` into Azure Boards work items. The repo is the source of
truth for *what should exist*; this tool makes the board match, idempotently. Full design,
mapping, and enforcement model: [`docs/architecture/tracking.md`](../../docs/architecture/tracking.md).

This is a generic tool — configure your Azure DevOps org and project via the environment
variables documented in [Usage](#usage) below.

## Mapping

| Repo page | Work item | Eligible when |
|---|---|---|
| `product`     | Epic       | page exists |
| `feature`     | Feature    | page exists (parent = product's Epic) |
| `requirement` | User Story | `status: approved` (parent = feature) |

Match key: the tag `repo-id:<ID>`. The tool writes only Title, type, parent link, the
`project-sync` + `repo-id:<ID>` tags, and a hyperlink back to the rendered page. It never
writes State, AssignedTo, IterationPath, or effort — the board owns those.

## Usage

```bash
pip install pyyaml

# Repo-side validation only (no creds): unique IDs + resolvable parents.
python tools/azure-sync/sync.py --check

# Against a real project (read-only drift check):
export AZDO_ORG_URL="https://dev.azure.com/HPS-AT-GenAI"
export AZDO_PROJECT="Post"
export AZDO_PAT="<pat with Work Items read>"      # or SYSTEM_ACCESSTOKEN in CI
python tools/azure-sync/sync.py --check

# Create missing work items + repair links (needs Work Items: read & write):
export SITE_BASE_URL="https://<published-site>/requirements-site"
python tools/azure-sync/sync.py --apply
```

`--dry-run` is an alias of `--check`. Exit code is non-zero on drift or repo-side problems,
so it works as a CI gate.

## CI

[`azure-pipelines-board-sync.yml`](azure-pipelines-board-sync.yml): `--check` on PRs into
`master`, `--apply` on merge. Grant the build service **Work Items: read & write** (or set a
secret `AZDO_PAT`) before enabling `--apply`; do a `--check` against the real project first.

## Known limitation

A cross-product feature (`Product:` as a YAML list) is parented under its **first** product's
Epic. Boards hierarchy is single-parent; the other product associations live in the repo.
