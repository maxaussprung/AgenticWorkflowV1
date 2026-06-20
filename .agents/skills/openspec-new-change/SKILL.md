---
name: openspec-new-change
description: Start a new OpenSpec change using the experimental artifact workflow. Use when the user wants to create a new feature, fix, or modification with a structured step-by-step approach.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

Start a new change using the experimental artifact-driven approach.

**Input**: The user's request should include a change name (kebab-case) OR a description of what they want to build.

**Steps**

1. **If no clear input provided, ask what they want to build**

   Use the **AskUserQuestion tool** (open-ended, no preset options) to ask:
   > "What change do you want to work on? Describe what you want to build or fix."

   From their description, derive a kebab-case name (e.g., "add user authentication" → `add-user-auth`).

   **IMPORTANT**: Do NOT proceed without understanding what the user wants to build.

2. **Determine the workflow schema**

   Use the default schema (omit `--schema`) unless the user explicitly requests a different workflow.

   **Use a different schema only if the user mentions:**
   - A specific schema name → use `--schema <name>`
   - "show workflows" or "what workflows" → run `openspec schemas --json` and let them choose

   **Otherwise**: Omit `--schema` to use the default.

3. **Create the change directory**
   ```bash
   openspec new change "<name>"
   ```
   Add `--schema <name>` only if the user requested a specific workflow.
   This creates a scaffolded change at `openspec/changes/<name>/` with the selected schema.

4. **Show the artifact status**
   ```bash
   openspec status --change "<name>"
   ```
   This shows which artifacts need to be created and which are ready (dependencies satisfied).

5. **Get instructions for the first artifact**
   The first artifact depends on the schema (e.g., `proposal` for spec-driven).
   Check the status output to find the first artifact with status "ready".
   ```bash
   openspec instructions <first-artifact-id> --change "<name>"
   ```
   This outputs the template and context for creating the first artifact.

6. **STOP and wait for user direction**

**Output**

After completing the steps, summarize:
- Change name and location
- Schema/workflow being used and its artifact sequence
- Current status (0/N artifacts complete)
- The template for the first artifact
- Prompt: "Ready to create the first artifact? Just describe what this change is about and I'll draft it, or ask me to continue."

**Guardrails**
- Do NOT create any artifacts yet - just show the instructions
- Do NOT advance beyond showing the first artifact template
- If the name is invalid (not kebab-case), ask for a valid name
- If a change with that name already exists, suggest continuing that change instead
- Pass --schema if using a non-default workflow


## Project addendum — requirements traceability

**This repo links every OpenSpec change to the confirmed requirements under `docs/requirements/`.**
Governance: `AGENTS.md` → *"OpenSpec Changes and Requirements Traceability"*. Apply on every change:

- **Top-of-file banner (ALL artifacts).** `proposal.md`, `design.md`, and `tasks.md` must each
  open with a one-line `> **Requirements (traceability):**` blockquote at the very top, listing
  the `REQ-*` IDs the change touches, grouped by capability (flag partial coverage). Cite by ID —
  never restate the requirement text.
- **Forward link (proposal).** Keep the full capability → `REQ-*` mapping in proposal's
  `## Requirements` section.
- **Backward link (at apply time).** When implementing, add `openspec_change: <change-name>` to
  each cited requirement's frontmatter and fill its `### Architecture` / `#### Technical
  Dependencies` with the distilled durable decisions. The requirements site renders this as an
  "Implemented by" row (`tools/requirements-site/overrides/partials/requirement-header.html`).
- **Validate:** `.venv/bin/mkdocs build -f tools/requirements-site/mkdocs.yml --strict` must pass.
