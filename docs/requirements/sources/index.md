---
title: "Source documents"
index_of: source-document
nav_children: true
---

# Source documents

The official source material the requirements are extracted from. Each document has its own page with a download link and an auto-generated traceability matrix listing every feature, requirement, and test case that references it via its structured `source:` field.

## Source Priority

Define the project's source priority here (highest to lowest). Example:

1. Project backlog / user story export (e.g. Azure Boards, Jira)
2. Specification documents (e.g. requirements specification, functional design, requirements workbook)
3. Legacy application / code analysis

## Example

- [SRC-EXAMPLE-001 — Example Source: {DOCUMENT-NAME}](SRC-EXAMPLE-001.md)

## How traceability works

Every feature or requirement page can name one or more source-document references in its frontmatter:

```yaml
source:
  - document: SRC-EXAMPLE-001
    section: "Example §1 (Feature Description)"
```

The matching source-document page picks those entries up automatically and groups them under their section. Renaming or re-numbering sections happens here in one place; no page-by-page maintenance.
