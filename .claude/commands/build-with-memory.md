---
name: "Build with Memory"
description: Execute a task with the agent memory in the loop — read .memory/ instructions and topic files first, reuse its tools, and contribute every learning back afterwards
category: Workflow
tags: [memory, workflow, learnings, tools]
---

Use the canonical workflow in `.agents/skills/build-with-memory/SKILL.md`.

Before acting:

1. Read `.agents/skills/build-with-memory/SKILL.md` completely.
2. Treat this command's arguments as the skill input (the task to perform).
3. When the skill mentions `/build-with-memory`, treat that as this Claude Code command.

Do not copy or restate the workflow here; `.agents/skills/build-with-memory/SKILL.md` is the
source of truth.
