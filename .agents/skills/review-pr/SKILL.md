---
name: review-pr
description: Review an Azure DevOps pull request — produce a short, concise description of what the PR does (with a visual old-vs-new example) plus a critical review against this repo's coding standards and guidelines. Use when reviewing a colleague's PR, triaging an incoming PR, or self-reviewing before merge.
metadata:
  author: {project}
  version: "1.0"
---

# Review PR

Produce a **reproducible two-part review** of an Azure DevOps pull request:

1. **Description** — a short, concise summary of what the PR does, with an as-visual-as-possible
   old-vs-new example.
2. **Critical review** — severity-tagged findings on whether the changes follow best-practice
   coding standards and this repository's guidelines, ending in a verdict.

Output stays **in chat by default**. Only post to the PR when the user passes `--comment`.

## Input

The skill input is a **PR ID** (e.g. `1234`) or an **Azure DevOps PR URL**
(e.g. `https://dev.azure.com/{AZURE-DEVOPS-ORG}/{AZURE-DEVOPS-PROJECT}/_git/{REPO-NAME}/pullrequest/1234`). Extract the numeric
`pullRequestId` from a URL.

Flags:
- `--comment` — after showing the review and getting explicit confirmation, post findings as PR
  comment threads (see step 6). Without this flag, never write to the PR.

**If no PR ID is provided:** list open PRs with
`mcp__azure-devops__repo_list_pull_requests_by_repo_or_project` (status `Active`) and use the
**AskUserQuestion tool** to let the user pick. Do **NOT** guess or auto-select a PR.

### Repository coordinates

Resolve from `tools/{project}-work/config.yaml`:
- organization: (from `azure_devops.org_url`)
- `project`: (from config)
- `repositoryId`: (repository name from config)

Read the config rather than hardcoding, in case it changes.

## Steps

### 1. Gather PR metadata

```
mcp__azure-devops__repo_get_pull_request_by_id
  repositoryId: "<repo-name>", project: "<project>", pullRequestId: <id>,
  includeWorkItemRefs: true, includeLabels: true, includeChangedFiles: true
```

Capture: title, description, author, source/target branch, linked work items, labels, status.

### 2. Gather the diff (powers the visual)

```
mcp__azure-devops__repo_get_pull_request_changes
  repositoryId: "<repo-name>", project: "<project>", pullRequestId: <id>,
  includeDiffs: true, includeLineContent: true
```

This returns line-by-line added/removed content. Use it for the change inventory **and** the
old-vs-new example. For large PRs, raise `top` or page with `skip`; if you cap coverage, say so
explicitly in the output (never silently truncate).

### 3. Gather existing reviewer feedback

```
mcp__azure-devops__repo_list_pull_request_threads
  repositoryId: "<repo-name>", project: "<project>", pullRequestId: <id>, status: "Active"
```

Read prior threads so the review does **not** repeat points already raised.

### 4. Pull surrounding context only when needed

When a change is non-obvious in isolation, fetch the surrounding file at the PR's source branch:

```
mcp__azure-devops__repo_get_file_content
  repositoryId: "<repo-name>", project: "<project>", path: "<file>",
  version: "<sourceBranch>", versionType: "Branch"
```

Use sparingly — most judgments come from the diff itself.

### 5. Produce the review (in chat)

#### Part 1 — Description (concise)

- **What & why:** 2–5 sentences in plain language describing the PR's intent and the user-facing
  or architectural effect. Describe behavior, not a file listing.
- **Key changes:** a short bullet list grouped by area (backend / frontend / docs / tests / infra).
- **Old vs new:** for the **1–3 most representative** changes, show stacked fenced code blocks:

  ````
  `path/to/File.cs`
  ```diff
  - old line
  + new line
  ```
  ````

  Or, when clearer, two labelled blocks (`Before:` / `After:`). Choose the changes that best
  convey the PR's essence — do **not** dump the whole diff.
- **Traceability:** list linked work items / `REQ-*` IDs if present; note their absence if the PR
  is clearly ticket-backed.

#### Part 2 — Critical review (against THIS repo's standards)

The source of truth for standards is **`docs/architecture/{project}-technical-guidelines.md`**
(§3 Coding Standards, §15 Quick Reference Checklist, §16 Code Review Process), the constraints in
**`AGENTS.md`**, and **`CONTRIBUTING.md`**. Cite these rather than restating them in full; read the
guidelines doc when a judgment needs the detailed rule.

Tag every finding with a severity, a `file:line` reference, and a concrete, actionable
recommendation (no vague "consider reviewing"):

- **Blocker** (must fix before merge):
  - Any edit under `to_be_migrated_repo/` (frozen, CI-rejected by `azure-pipelines-guardrails.yml`) or
    `legacy-sql/` (frozen, read-only).
  - Committed secrets/credentials or environment-specific config.
  - Committed generated output (`obj/`, build artifacts) in source folders.
  - Missing peer review / self-approval (§16: do not approve your own PR).
  - Ticket-backed behavior change with no requirement/work-item traceability.
- **Major** (should fix):
  - Architecture-boundary violations: Domain depending on outer layers; infra (e.g. Typesense)
    leaking into Application; business logic in endpoints or React components; REST helper called
    directly from components instead of `src/services`; async orchestration outside epics.
  - Missing tests for new behavior (unit coverage SHOULD be ≥70% for new code).
  - Validation/auth/security gaps; input not validated on both client and server; XSS/CSRF risks.
  - Accessibility regressions (WCAG 2.2 AA) for UI changes.
  - Non-conventional commit messages; oversized/multi-concern PR.
- **Minor / Nit:**
  - C# naming (`_camelCase` private fields, `s_camelCase` private statics, `var` discouraged,
    file-scoped namespaces); TS strict, stray `any` outside `src/core/**`, import order.
  - Prettier/ESLint formatting; comments that restate code instead of explaining WHY.
  - Hardcoded user-facing strings instead of `src/translations/` (`de` default, `en`).

End with a one-line **verdict**: `Approve` / `Approve with comments` / `Request changes`, plus a
one-sentence rationale.

### 6. Optional — post findings to the PR (`--comment` only)

Only when the user passed `--comment`:
1. Show the full in-chat review first.
2. Ask for explicit confirmation before writing anything (posting modifies someone else's PR).
3. On confirmation, create threads via `mcp__azure-devops__repo_create_pull_request_thread`:
   - For findings tied to a specific line: set `filePath` and `rightFileStartLine`.
   - One summary thread (no `filePath`) carrying the description + verdict.
4. Report which threads were created. Never post without the flag and never without confirmation.

## Output format

- Two clearly headed sections: **Description** and **Critical Review**.
- Code references as `file:line`.
- Severity labels in **bold**; group findings by severity, highest first.
- Keep it scannable — concise prose, short bullets, only the most telling old-vs-new snippets.
- If any step was skipped or coverage capped (e.g. very large diff), state it explicitly.
