# test-coverage/

This folder holds **test coverage data** linking requirements to test implementations.

## Subfolders

- `backend/` — Per-requirement backend test coverage records
- `frontend/` — Per-requirement frontend test coverage records

## Format

Each coverage file documents which tests cover a given requirement:

```yaml
requirement: REQ-EXAMPLE-001
backend_tests:
  - test: "{TestClass}.{TestMethod}"
    covers: "acceptance criterion 1"
frontend_tests:
  - test: "{describe block} > {it block}"
    covers: "acceptance criterion 2"
coverage_status: partial  # none | partial | full
```
