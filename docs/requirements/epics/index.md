---
title: "Epics"
index_of: epic
nav_children: true
index_columns:
  - Priority
  - status
---

# Epics

High-level business capabilities that group related features under a product. An epic represents a coherent area of business value that typically spans multiple features and sprints.

## Example

- [EPIC-EXAMPLE-001 — Example Epic: Search & Discovery](EPIC-EXAMPLE-001.md)

## ID Pattern

Epics follow the pattern `EPIC-<NNN>` where `<NNN>` is a zero-padded sequence number (e.g. `EPIC-001`).

## Relationship to Other Types

```
Product
  └── Epic
        └── Feature
              └── Requirement
```

Each epic links to its parent product via the `product:` frontmatter field. Features link back to their parent epic via their own `epic:` frontmatter field.
