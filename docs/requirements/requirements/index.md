---
title: "Requirements"
index_of: requirement
nav_children: true
index_columns:
  - Priority
  - source_tier
  - kind
---

# Requirements

Atomic, testable "The system shall…" statements that define what the system must do.

Each requirement is typed, cross-linked to its parent feature and source documents, and carries acceptance criteria, exclusions, and an architecture section (owned by the architect).

## Example

- [REQ-EXAMPLE-001 — Example: Advanced Search for {FEATURE-NAME}](REQ-EXAMPLE-001.md)

## ID Pattern

Requirements follow the pattern `REQ-<AREA>-<NNN>` where `<AREA>` is a short tag for the functional area (e.g. `SEARCH`, `AUTH`, `IMPORT`) and `<NNN>` is a zero-padded sequence number.

## Key Frontmatter Fields

| Field | Description |
|---|---|
| `feature` | The parent `FEAT-*` ID this requirement belongs to |
| `product` | One or more `PRODUCT-*` IDs this requirement contributes to |
| `status` | Governance lifecycle: `draft` → `review` → `approved` |
| `priority` | MoSCoW: `must`, `should`, `could`, `wont` |
| `source` | Source document references with section citations |
| `depends_on` | Other `REQ-*` IDs this requirement depends on |
