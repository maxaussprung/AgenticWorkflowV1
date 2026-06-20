---
title: "Product dashboard"
type: product-dashboard
hide:
  - toc
---

# Product dashboard

Per product, the requirements that apply to it. A requirement is
assigned to a product through its feature (`Requirement.feature` → `Feature.Product`), so a
cross-cutting feature surfaces its requirements under every product it serves.

!!! note "Source of truth: `openspec/track.md`"
    Implementation status is derived **only** from
    the slice ledger `openspec/track.md` at build time — `done` → Done,
    `claimed`/`in-progress`/`blocked` → In Progress, absent → Open. It is **not** read live from
    the project tracker, so it reflects `track.md` and can lag the actual work-item state until the
    ledger is updated.
