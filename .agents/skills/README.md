# Agent Skills

Reusable [Agent Skills](https://agentskills.io) for this repo. Each skill is a **directory**
containing a `SKILL.md` (YAML frontmatter with `name` + `description`, then instructions):

```
.agents/skills/<skill-name>/SKILL.md
```

## Why `.agents/skills/` (and how each tool finds it)

`.agents/skills/` is the tool-neutral standard location and is the single source of truth:

- **Codex CLI** and **OpenCode** scan `.agents/skills/` natively — no configuration needed.
- **Claude Code** discovers skills under `.claude/skills/`; that path is a **symlink** to this
  directory, so Claude sees the same skills.
- Repo-local compatibility paths such as `.codex/skills` and `.opencode/skills`, when present,
  must be symlinks to this directory rather than duplicate skill copies.

Add a new skill as `.agents/skills/<name>/SKILL.md`; all three assistants pick it up.

## Available skills

### Setup
| Skill | Description |
|-------|-------------|
| `setup-repo-structure` | **First-time repo setup.** Interactive questions → bulk placeholder replacement across the whole repo. Run once after cloning. |

### OpenSpec workflow
| Skill | Description |
|-------|-------------|
| `openspec-new-change` | Start a new OpenSpec change |
| `openspec-propose` | Create proposal + all artifacts in one step |
| `openspec-ff-change` | Fast-forward: create change and all artifacts in one pass |
| `openspec-explore` | Enter explore mode before or during a change |
| `openspec-continue-change` | Create the next artifact for an in-progress change |
| `openspec-apply-change` | Implement the tasks from a change |
| `openspec-verify-change` | Verify implementation matches change artifacts |
| `openspec-archive-change` | Archive a completed change |
| `openspec-bulk-archive-change` | Archive multiple completed changes |
| `openspec-sync-specs` | Sync delta specs from a change back to main specs |
| `openspec-onboard` | Guided walkthrough of the full OpenSpec workflow |

### Implementation workflow
| Skill | Description |
|-------|-------------|
| `pick-implementation-slice` | Select the next implementation slice to work on |
| `complete-implementation-slice` | Implement a full slice (backend + frontend + tests) |
| `mock-implementation-slice` | Implement a slice with mocked external dependencies |
| `generate-tdd-tests` | Generate TDD tests for a requirement or feature |
| `product-synthesis` | Synthesize product-level coverage and analysis |

### Integration & analysis
| Skill | Description |
|-------|-------------|
| `azure-boards-export` | Export Azure Boards work items to the requirements site |
| `legacy-sql-analysis` | Analyse legacy SQL objects and generate traceability report |
| `requirement-synthesis` | Synthesise requirements from multiple source documents |
| `review-pr` | Review a pull request against coding standards |
| `sonarqube-run-fix` | Run SonarQube scan and apply suggested fixes |
| `sync-csharp-to-client-repo` | Sync implemented code to the client delivery repository |
