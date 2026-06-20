---
name: "Review PR"
description: Review an Azure DevOps pull request — concise description with a visual old-vs-new example plus a critical review against repo coding standards and guidelines
category: Review
tags: [review, pull-request, azure-devops, quality]
---

Use the canonical workflow in `.agents/skills/review-pr/SKILL.md`.

Before acting:

1. Read `.agents/skills/review-pr/SKILL.md` completely.
2. Treat this command's arguments as the skill input (a PR ID or Azure DevOps PR URL, plus the
   optional `--comment` flag).
3. When the skill mentions `/review-pr`, treat that as this Claude Code command.

Do not copy or restate the review workflow here; `.agents/skills/review-pr/SKILL.md` is the source
of truth.
