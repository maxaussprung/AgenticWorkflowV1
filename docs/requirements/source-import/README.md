# source-import/

This folder holds **imported source material** — raw or lightly processed content from legacy systems, specifications, and reference documents used during requirements discovery.

## Structure

Organize imports by source type or document category:

```
source-import/
├── {SOURCE-TYPE}/          # e.g. DataContracts/, Specifications/, Diagrams/
│   ├── YYYY-MM-DD-{name}.{ext}
│   └── Archiv/             # Historical versions
└── {OTHER-SOURCE-TYPE}/
```

## Usage

- Files here are **read-only reference material** — never edit imported originals.
- Requirements reference these via `source:` frontmatter in REQ-*.md files.
- The `SRC-*.md` files in `sources/` catalogue which documents have been imported.

## Naming Convention

Use descriptive filenames with a date prefix where possible:
`YYYY-MM-DD-{document-name}.{ext}`
