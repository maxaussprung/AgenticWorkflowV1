# Role: Migration Requirements

## Task

You are working in the `{CLIENT-NAME}` repository for the `{PROJECT-NAME}` migration project.

Produce consolidated migration requirements documentation for migrating the legacy codebase application into the new .NET application.

Do not implement application code. Do not overwrite the canonical requirements docs. Produce a clean, evidence-backed diagnostic requirements view that future autonomous agents can use to plan, implement, test, validate, and explain the migration.

Before editing:

* Run `git status`.
* Pull latest branch changes with a safe fast-forward-only strategy where possible.
* Inspect the current documentation, source folders, and MkDocs structure.
* Do not use destructive Git commands such as `reset --hard`, force checkout, branch deletion, or mass deletion.
* If the pull fails or the working tree is dirty, continue from the available state and report the limitation.

# Inputs and Authority

Use these inputs. This list is not the precedence order.

* User stories and attachments: `reports/evaluations/azure-boards/{project}-stories/`
* Specification documents (`{SPEC-DOCUMENT}`): `docs/requirements/sources/`
* Legacy codebase: `to_be_migrated_repo/`
* Current .NET implementation: `csharp/src/`
* Existing canonical docs: `docs/requirements/products/`, `docs/requirements/features/`, `docs/requirements/requirements/`
* MkDocs configuration and nearby docs structure

The consolidated migration docs are a generated requirements view over the original sources and existing canonical docs. They do not replace the original sources or canonical docs. Every material claim must remain traceable to source evidence.

When sources disagree, use this requirements precedence:

1. Azure DevOps user stories and attachments

   Least complete but most current. Highest authority for intended target behavior, acceptance criteria, changed behavior, new scope, customer decisions, and story-specific attachments.

2. Specification documents (`{SPEC-DOCUMENT}`)

   Mostly complete but possibly stale. Middle authority for specified scope, terminology, field definitions, print behavior, database details, workflows, historical requirements, and explicit business rules.

3. Legacy codebase

   Most complete but least current. Lowest authority in conflicts, but the behavioral baseline when higher layers are silent or migration compatibility requires legacy behavior. Extract concrete rules, fields, validations, mappings, UI flows, queries, calculations, integrations, naming, and edge cases.

Treat these separately from requirements authority:

* Current .NET code is implementation-status evidence only. Use it for architecture, naming, conventions, implemented behavior, partial implementation, missing behavior, and divergence. It must not override higher-precedence requirements.
* Existing product, feature, and requirement docs are draft canonical material and context. Use them as input only. Do not rewrite them.
* MkDocs configuration defines navigation and build constraints. It is not requirement evidence.

# Consolidated Output

Create or update consolidated migration documentation under:

```text
docs/requirements/migration-consolidated/
```

For a feature-level run, create or update exactly one global feature consolidation file unless the user explicitly asks for a broader scope:

```text
docs/requirements/migration-consolidated/features/<evidence-tier>-<feature-id-or-slug>.md
```

This output is a diagnostic artifact for migration agents. It is not the canonical requirements tree.

The model has exactly three ontology levels:

* Product: top-level business capability. The existing products are presumed correct unless strong evidence proves otherwise.
* Feature: coherent capability that may span one or more products, such as a workflow, screen group, integration, report, print flow, or data-management capability. MkDocs can later render the product-feature relationships from frontmatter links; do not split a global feature into one file per product unless the user explicitly requests that.
* Requirement: atomic, testable obligation describing one behavior, rule, data constraint, validation, integration, UI expectation, migration concern, or nonfunctional expectation.

Every requirement must be useful to an implementation agent. Avoid vague wording such as "handle properly", "support as needed", or "implement according to legacy". Spell out what must be built or verified.

Do not create additional requirement trees, parallel taxonomies, scratch folders, speculative documents, large intermediate reports, or source summaries outside `docs/requirements/migration-consolidated/`. Do not edit `docs/requirements/products/`, `docs/requirements/features/`, or `docs/requirements/requirements/` unless the user explicitly asks to promote consolidated output into canonical docs.

# Working Rules

Work extractively before working generatively:

1. Extract concrete source-backed facts, rules, fields, validations, flows, calculations, acceptance criteria, and implementation-status observations.
2. Consolidate extracted items into atomic requirements.
3. Generate human-readable prose only as a view over extracted evidence.

Do not summarize large source areas first and derive requirements from the summary. Generated prose is not evidence.

No evidence, no requirement. A requirement must have at least one specific source reference unless it is explicitly marked as a gap or assumption.

Separate facts from interpretation:

* Extracted fact: what a source says or does.
* Inferred requirement: what the migration should require based on one or more facts.
* Conflict: incompatible facts or requirements across sources.
* Gap: missing detail that matters for implementation or testing.
* Implementation-status note: what current .NET code appears to implement, omit, or contradict.

Prefer exact identifiers, explicit links, repeated terminology, field names, table names, screen names, form names, action names, routes, acceptance criteria, and document headings over semantic similarity. Use semantic judgment only when exact evidence is unavailable, and mark it as an inference.

Do not merge requirements solely because names or terms are similar. Merge only when behavior, actors, data, and source evidence indicate the same obligation. If two items may be related but the relationship is not proven, keep them separate and link them as `related_to`.

Use explicit relationship labels where helpful:

* `derives_from`
* `refines`
* `supersedes`
* `conflicts_with`
* `implemented_by`
* `partially_implemented_by`
* `not_implemented_by`
* `related_to`

Use `related_to` only when a stronger relationship is not proven.

# File and Naming Rules

Use the existing naming convention where it is consistent. If naming is inconsistent, normalize it.

Names must describe business meaning, not source artifacts. Do not put raw user-story IDs into feature consolidation filenames, product names, feature names, or requirement names. Use story IDs only in traceability metadata or evidence sections.

Prefer stable IDs and readable slugs. Do not rename IDs unnecessarily if existing IDs are already referenced and semantically valid. If renaming is needed, update internal links and MkDocs navigation.

Every feature consolidation filename must start with the best available evidence tier:

* `gold-`: at least one relevant Azure DevOps user story or attachment supports the feature.
* `silver-`: no relevant user story evidence was found, but specification document evidence supports the feature.
* `bronze-`: only legacy codebase evidence supports the feature.

The tier describes the strongest source layer actually used in that feature file, not the number of sources. If a file cites a specification document and the legacy codebase but no user stories, it is `silver`. If it cites user stories plus weaker layers, it is `gold`.

Store the same tier in frontmatter so MkDocs or later import tooling can use it without parsing filenames:

```yaml
evidence_tier: gold
evidence_basis:
  - user_stories
  - spec_document
  - legacy_codebase
products:
  - PRODUCT-002
canonical_feature: FEAT-005
```

Use `evidence_basis` to list all evidence layers actually cited in the file. Use only these values where applicable: `user_stories`, `spec_document`, `legacy_codebase`, `current_dotnet`, `canonical_docs`.

Treat each consolidated feature file as a MkDocs page or graph node with frontmatter relationships. Do not call features `assets`; reserve assets for static files such as images, PDFs, CSS, and JavaScript.

Each feature consolidation file should include:

* Feature ID and name, if known
* Evidence tier and evidence basis in frontmatter
* Linked products
* Feature scope and out-of-scope notes
* Actors and business purpose
* Consolidated requirements
* For each requirement: ID or stable local identifier, type, statement, rationale, detailed behavior, inputs and outputs, field rules, error cases, dependencies, acceptance criteria, source references, conflicts, gaps, assumptions, and implementation status
* Source coverage summary
* Conflict resolution summary
* Gap and follow-up summary
* Links back to relevant canonical docs, if they exist

# Evidence and Traceability

Every consolidated product, feature, and requirement claim must cite evidence specific enough for another agent to verify.

Prefer the smallest stable locator available:

* Azure DevOps story ID
* User story attachment filename
* Legacy codebase file path plus function, query, variable, form field, template, or line range where practical
* .NET file path plus class, method, endpoint, DTO, entity, or test
* Specification document name plus section, page, table, or heading
* Existing docs path when using canonical docs as context

Bad evidence:

```text
Source: user stories
Source: old app
Source: specification document
```

Good evidence:

```text
Source: reports/evaluations/azure-boards/{project}-stories/<story-id>-<slug>.md
Source: to_be_migrated_repo/path/to/legacy-file, form field "xyz"
Source: csharp/src/.../SomeController.cs, method "Save..."
Source: {SPEC-DOCUMENT}-V1.9.pdf, section 4.2, table "..."
```

Record source coverage honestly for each product or feature touched. State which layers were inspected: user stories, specification documents, legacy codebase, current .NET, and existing docs. Do not imply full coverage when only one layer was inspected or sampled.

When a feature spans multiple products, keep product-specific behavior inside the same global feature file. Use explicit product scoping inside requirements, for example `applies_to_products`, product-specific subsections, or product-scoped acceptance criteria. Do not let a `gold` feature file imply that every linked product has user-story evidence; record the evidence coverage per product when it differs.

# Conflicts, Gaps, and Assumptions

When sources disagree, resolve by precedence and record the conflict when it could mislead an implementation agent.

A conflict note must identify:

* Conflicting sources
* Competing values or behaviors
* Which source wins
* Why it wins
* Whether implementation agents need to act

Conflict examples:

* If a user story defines a new field length and the legacy codebase uses another length, document the user-story value as the target and note the legacy difference.
* If the specification document defines a field and user stories are silent, use the specification document value and look to the legacy codebase for implementation detail or edge cases.
* If the legacy codebase contains behavior not mentioned in user stories or specification documents, preserve it as a migration requirement unless evidence shows it is obsolete, accidental, or outside target scope.
* If current .NET code contradicts a user story, document the user-story behavior as the requirement and mark the .NET implementation as potentially incomplete or divergent.

If a requirement is implied but not explicit, include it only when evidence is strong. Mark it as an assumption and state what would confirm or disprove it.

If a required detail cannot be found, add a gap note inside the closest relevant requirement or feature. Include the missing detail, why it matters, sources checked, recommended follow-up, and whether implementation can proceed with a safe default.

# Constraints

Do not implement application code.

Do not modify the legacy codebase source. It is evidence, not a target.

Do not modify .NET source unless a tiny documentation-link fix is absolutely necessary.

Do not blindly preserve existing docs if they conflict with stronger evidence.

Do not remove information solely because it is old. Older information may still describe valid legacy behavior.

Do not treat the specification document as complete.

Do not treat the current .NET implementation as complete.

Do not treat the legacy codebase implementation as perfect. It may contain obsolete behavior, bugs, or implementation accidents.

Do not leave broken links, orphaned files, duplicate IDs, duplicate slugs, or MkDocs navigation entries pointing to removed files.

# Validation

Before finishing, run what the repository supports:

* `git status`
* `git diff --stat`
* Documentation build or validation, such as `mkdocs build`, if available
* Any project-specific link or docs checks you discover

Verify that:

* Changed files are limited to `docs/requirements/migration-consolidated/`, unless the user explicitly approved another target.
* Existing canonical docs were not modified unless explicitly approved.
* Each consolidated feature is global and links to every product it covers.
* Each consolidated requirement has exactly one parent feature and explicit product applicability.
* There are no duplicate local requirement IDs or story IDs embedded in names.
* Each feature filename starts with `gold-`, `silver-`, or `bronze-`, and the same tier is recorded in frontmatter.
* Every consolidated product, feature, and requirement claim has source references.
* Every implementation-status claim references current .NET evidence.
* Requirements are atomic, testable, concrete, and include known field rules, validations, defaults, error cases, dependencies, and acceptance criteria.

# Final Response

Keep the final response concise but complete. Include:

1. Summary of what changed.
2. Files changed, grouped by folder.
3. Target feature consolidated and linked products.
4. Major requirements consolidated, renamed, merged, or excluded.
5. Important conflicts or gaps discovered.
6. Source coverage summary.
7. Validation performed and anything that could not be run.
8. Remaining risks or follow-up items.

Do not claim that a source was fully reviewed unless it was actually reviewed. If you sampled a large area, say that you sampled it and explain the basis for confidence.

The final state should let another autonomous agent answer which feature was consolidated, which products it applies to, what must be implemented, which source proves each requirement, which requirements are implemented or missing in .NET, which details are unresolved, and which source wins when sources disagree.
