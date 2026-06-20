# {PROJECT-NAME} Requirements

**Detailed specification for the {PROJECT-NAME} migration project.**

This site holds the working set of requirements for {PROJECT-NAME}. Content is extracted from the source material under `source-import/` and refined here into typed, cross-linked pages.

## Tier 1 – Contractual Baseline *(before signing the contract)*

Requirements the vendor is contractually obligated to fulfill (any deviation triggers a formal change request):

- **Business requirements** — goals, success criteria, and constraints
- **Functional requirements** — written as "The system shall...", numbered, atomic, testable, and prioritised (Must / Should / Could / Won't)
- **Non-functional requirements** — performance, availability, security, compliance, scalability
- **Integration specifications** — all third-party systems, data formats, and error handling
- **Domain model** — major entities and relationships (field-level detail not required yet)
- **Key algorithms** — any complex or business-critical logic must be fully specified

## Tier 2 – Detailed Design *(elaborated just in time)*

- Screen layouts and UI design
- Field names, descriptions, validation rules
- Error messages and edge case behaviour
- Report layouts

## Governance

Every Tier 1 requirement maps to a test case. The UAT plan is written alongside the spec — not after it.

---

## How this site is organised

| Section | Purpose |
|---|---|
| [Products](products/index.md) | The top-level grouping — the product catalogue under which everything else sits. |
| [Features](features/index.md) | Coherent slices of capability under a product. |
| [Requirements](requirements/index.md) | Atomic, testable "The system shall…" statements |
| [Test cases](test_cases/index.md) | UAT and integration test cases that verify requirements |
| [Applications](applications/index.md) | Systems in scope — the application landscape that integrates with or is replaced by the new system |
| [Domains](domains/index.md) | Business and capability domains (company-wide reference data) |
| [Page types](page-types/index.md) | Frontmatter contracts and body structure for every type of page on this site |
| [Estimation](estimation/index.md) | Derived sprint estimates per feature with contingency |
