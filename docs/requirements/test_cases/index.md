---
title: "Test Cases"
index_of: test_case
nav_children: true
index_columns:
  - Priority
  - status
---

# Test Cases

UAT and integration test cases that verify requirements. Each test case is linked to one or more requirements and features via its frontmatter.

## Example

- [TC-EXAMPLE-001 — Example Test Case: {TEST-NAME}](TC-EXAMPLE-001.md)

## ID Pattern

Test cases follow the pattern `TC-<AREA>-<NNN>` where `<AREA>` matches the requirement area it tests (e.g. `TC-SEARCH-001`) and `<NNN>` is a zero-padded sequence number.

## Governance

Every Tier 1 requirement must have at least one corresponding test case before the requirement can reach `approved` status. The UAT plan is written alongside the spec, not after it.
