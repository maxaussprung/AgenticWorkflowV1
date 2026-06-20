# Copilot instructions

This repo uses a multi-agent setup. See [AGENTS.md](../AGENTS.md) for project orientation, role files, and shared rules.

Role-specific prompts live in `.agents/subagents/requirements-site/copilot/prompts/` — invoke with `/<role>` in Copilot Chat:

- `/sitebuilder` — mkdocs build, theme, hooks, CSS, site assets
- `/requirements-engineer` — hand-authored content under `docs/requirements/`
- `/architect` — solution designs from approved Tier 1 requirements
- `/generalist` — fallback for tasks no specialist owns (top-level framing, cross-cutting work, ad-hoc tooling)
- `/migration-requirements` — diagnostic migration requirements under `docs/requirements/migration-consolidated/`

When asked to do work, identify the role first, then load that role's required reading before acting.
