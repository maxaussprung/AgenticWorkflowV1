#!/usr/bin/env python3
"""Rank implementation-slice candidates deterministically.

The selector is intentionally read-only. It turns the prose rules in
pick-implementation-slice into a repeatable shortlist so parallel agents do not
choose different "easy" slices from the same repository state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("PyYAML is required to run this selector: python3 -m pip install PyYAML") from exc


PRIORITY_RANK = {"must": 0, "should": 1, "could": 2, "wont": 99, "": 50, None: 50}
SOURCE_RANK = {"gold": 0, "silver": 1, "bronze": 2, "": 10, None: 10}
CSHARP_CONTEXT_RANK = {"partial": 0, "done": 1, "not-started": 2, "": 3, None: 3}
DEFAULT_ACTIVE_STATUSES = {"claimed", "in-progress", "blocked"}

# ===== PROJECT CONFIGURATION =====
# Configure these for your project:
# PRODUCT_TAGS: Set of product/feature tags used in requirement frontmatter
# PRODUCT_CODES: Tuple of product code prefixes used in REQ-* IDs
# EXTERNAL_KEYWORDS: Set of keywords indicating external system dependencies
# CONFIG_PATH: Path to the project work config YAML file
# ==================================

CONFIG_PATH = "tools/{project}-work/config.yaml"  # Configure for your project

PRODUCT_TAGS: set[str] = {
    # Configure these with your project's product/feature tags
    "product-a",
    "product-b",
    "product-c",
}

PRODUCT_CODES: tuple[str, ...] = (
    # Configure these with your project's product code prefixes
    "PROD-A",
    "PROD-B",
    "PROD-C",
)

EXTERNAL_KEYWORDS: frozenset[str] = frozenset({
    # Configure these with keywords indicating external system dependencies in your project
    "external-api",
    "third-party",
    "integration",
})


@dataclass(frozen=True)
class MarkdownPage:
    page_id: str
    path: Path
    meta: dict[str, Any]
    body: str


@dataclass
class TrackState:
    active_statuses: set[str] = field(default_factory=lambda: set(DEFAULT_ACTIVE_STATUSES))
    active_requirements: set[str] = field(default_factory=set)
    active_features: set[str] = field(default_factory=set)
    done_requirements: set[str] = field(default_factory=set)
    done_features: set[str] = field(default_factory=set)
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Candidate:
    requirement_id: str
    feature_id: str
    title: str
    path: str
    score: tuple[Any, ...]
    score_breakdown: dict[str, Any]
    risk_factors: list[str]
    dependency_details: list[dict[str, str]]
    reverse_dependency_counts: dict[str, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--top", type=int, default=15, help="Number of candidates to print.")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument(
        "--explain",
        action="append",
        default=[],
        metavar="REQ-ID",
        help="Print eligibility/scoring detail for a specific requirement. Can be repeated.",
    )
    parser.add_argument(
        "--show-ineligible",
        action="store_true",
        help="With --format json, include ineligible requirement reasons.",
    )
    return parser.parse_args()


def read_frontmatter(path: Path) -> MarkdownPage | None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return None
    meta = yaml.safe_load(match.group(1)) or {}
    page_id = str(meta.get("id") or path.stem)
    return MarkdownPage(page_id=page_id, path=path, meta=meta, body=text[match.end() :])


def load_pages(root: Path, rel_dir: str) -> dict[str, MarkdownPage]:
    pages: dict[str, MarkdownPage] = {}
    for path in sorted((root / rel_dir).glob("*.md")):
        page = read_frontmatter(path)
        if page is not None:
            pages[page.page_id] = page
    return pages


def load_active_statuses(root: Path) -> set[str]:
    config_path = root / CONFIG_PATH
    if not config_path.exists():
        return set(DEFAULT_ACTIVE_STATUSES)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    statuses = data.get("claims", {}).get("active_statuses")
    return set(statuses or DEFAULT_ACTIVE_STATUSES)


def expand_requirement_refs(cell: str) -> list[str]:
    refs: list[str] = []
    last_prefix = ""
    for raw_part in cell.split(","):
        part = raw_part.strip()
        full_match = re.match(r"^(REQ-[A-Z0-9]+)-(\d+)$", part)
        if full_match:
            last_prefix = full_match.group(1)
            refs.append(part)
            continue
        suffix_match = re.match(r"^-(\d+)$", part)
        if suffix_match and last_prefix:
            refs.append(f"{last_prefix}-{suffix_match.group(1)}")
    return refs


def parse_track(root: Path, active_statuses: set[str]) -> TrackState:
    track_path = root / "openspec/track.md"
    state = TrackState(active_statuses=set(active_statuses))
    if not track_path.exists():
        return state

    for line in track_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| FEAT"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 11:
            continue
        features = re.findall(r"FEAT-\d+", cells[0])
        requirements = expand_requirement_refs(cells[1])
        row = {
            "features": features,
            "requirements": requirements,
            "change": cells[2],
            "owner": cells[3],
            "branch": cells[4],
            "azure_work_item": cells[5],
            "status": cells[6],
            "claimed": cells[7],
            "completed": cells[8],
            "pr": cells[9],
            "notes": cells[10],
        }
        state.rows.append(row)
        status = cells[6]
        if status in active_statuses:
            state.active_features.update(features)
            state.active_requirements.update(requirements)
        elif status == "done":
            state.done_features.update(features)
            state.done_requirements.update(requirements)
    return state


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def has_done_tag(page: MarkdownPage) -> bool:
    return "done" in set(as_list(page.meta.get("tags")))


def page_status(page: MarkdownPage) -> str:
    return str(page.meta.get("status") or "").strip().lower()


def has_active_page_status(page: MarkdownPage, track: TrackState) -> bool:
    return page_status(page) in track.active_statuses


def has_done_page_status(page: MarkdownPage) -> bool:
    return page_status(page) == "done"


def requirement_is_done(requirement: MarkdownPage, track: TrackState) -> bool:
    return (
        requirement.page_id in track.done_requirements
        or has_done_page_status(requirement)
        or has_done_tag(requirement)
        or bool(requirement.meta.get("openspec_change"))
    )


def dependency_is_resolved(
    requirement_id: str,
    requirements: dict[str, MarkdownPage],
    features: dict[str, MarkdownPage],
    track: TrackState,
) -> tuple[bool, str]:
    requirement = requirements.get(requirement_id)
    if requirement is None:
        return False, "missing requirement page"
    if requirement.page_id in track.active_requirements:
        return False, "active lock"
    if has_active_page_status(requirement, track):
        return False, f"page status {page_status(requirement)}"
    if requirement_is_done(requirement, track):
        return True, "requirement done"
    feature_id = str(requirement.meta.get("feature") or "")
    feature = features.get(feature_id)
    if feature_id in track.done_features:
        return True, "feature done in track"
    if feature and has_done_page_status(feature):
        return True, "parent feature status done"
    if feature and feature.meta.get("csharp_status") == "done":
        return True, "parent feature csharp_status done"
    return False, "not implemented"


def count_acceptance_criteria(body: str) -> int:
    return len(re.findall(r"(?m)^\d+\.\s+\*\*", body))


def has_product_specific_scope(requirement: MarkdownPage) -> bool:
    tags = set(as_list(requirement.meta.get("tags")))
    title = str(requirement.meta.get("title") or "")
    if tags & PRODUCT_TAGS:
        return True
    return any(re.search(rf"\b{re.escape(code)}\b", title) for code in PRODUCT_CODES)


def product_breadth(requirement: MarkdownPage, features: dict[str, MarkdownPage]) -> tuple[int, str]:
    if has_product_specific_scope(requirement):
        return 0, "product-specific"
    feature = features.get(str(requirement.meta.get("feature") or ""))
    product_count = len(as_list(requirement.meta.get("product")))
    if feature is not None:
        product_count = product_count or len(as_list(feature.meta.get("Product")))
    if product_count > 3:
        return 3, "shared feature across many products"
    if product_count > 1:
        return 1, "shared feature across multiple products"
    return 0, "single product or unspecified"


def find_external_keywords(body: str) -> list[str]:
    found: list[str] = []
    for keyword in EXTERNAL_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", body, re.IGNORECASE):
            found.append(keyword)
    return found


def implementation_risk(requirement: MarkdownPage, features: dict[str, MarkdownPage]) -> tuple[int, list[str]]:
    body = requirement.body
    risk = 0
    factors: list[str] = []

    breadth, breadth_reason = product_breadth(requirement, features)
    risk += breadth
    if breadth:
        factors.append(f"+{breadth} {breadth_reason}")

    if "### Database Implementation" in body or "### Database Description" in body:
        risk += 2
        factors.append("+2 database impact")
    if "### API Description" in body or re.search(r"\bREST endpoint\b", body, re.IGNORECASE):
        risk += 2
        factors.append("+2 API surface")
    if "### Data Migration" in body or "### Coexistence" in body:
        risk += 2
        factors.append("+2 migration/coexistence")

    external_keywords = find_external_keywords(body)
    if external_keywords:
        risk += 2
        factors.append("+2 external integration: " + ", ".join(external_keywords[:5]))

    if requirement.meta.get("kind") == "non-functional":
        risk += 3
        factors.append("+3 non-functional requirement")

    acceptance_count = count_acceptance_criteria(body)
    if acceptance_count > 4:
        extra = (acceptance_count - 4) // 2
        risk += extra
        if extra:
            factors.append(f"+{extra} {acceptance_count} acceptance criteria")

    line_count = len(body.splitlines())
    if line_count > 320:
        risk += 2
        factors.append("+2 long requirement body")
    elif line_count > 220:
        risk += 1
        factors.append("+1 medium requirement body")

    if not factors:
        factors.append("0 low apparent implementation risk")
    return risk, factors


def build_reverse_dependencies(requirements: dict[str, MarkdownPage]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {page_id: [] for page_id in requirements}
    for requirement_id, requirement in requirements.items():
        for dependency in as_list(requirement.meta.get("depends_on")):
            if dependency in reverse:
                reverse[dependency].append(requirement_id)
    return reverse


def evaluate_requirement(
    requirement: MarkdownPage,
    requirements: dict[str, MarkdownPage],
    features: dict[str, MarkdownPage],
    track: TrackState,
    reverse_dependencies: dict[str, list[str]],
) -> tuple[Candidate | None, list[str]]:
    requirement_id = requirement.page_id
    feature_id = str(requirement.meta.get("feature") or "")
    reasons: list[str] = []

    if requirement.meta.get("priority") == "wont":
        return None, ["priority is wont"]
    if requirement_id in track.active_requirements:
        return None, ["requirement has active track lock"]
    if feature_id in track.active_features:
        return None, ["parent feature has active track lock"]
    if has_active_page_status(requirement, track):
        return None, [f"requirement page status is {page_status(requirement)}"]
    feature = features.get(feature_id)
    if feature and has_active_page_status(feature, track):
        return None, [f"parent feature page status is {page_status(feature)}"]
    if requirement_is_done(requirement, track):
        return None, ["requirement already has implementation evidence"]

    dependency_details: list[dict[str, str]] = []
    resolved_dependency_count = 0
    for dependency in as_list(requirement.meta.get("depends_on")):
        resolved, reason = dependency_is_resolved(dependency, requirements, features, track)
        dependency_details.append(
            {
                "id": str(dependency),
                "state": "resolved" if resolved else "unresolved",
                "reason": reason,
            }
        )
        if not resolved:
            return None, [f"dependency {dependency} is unresolved ({reason})"]
        resolved_dependency_count += 1

    active_reverse = 0
    unresolved_reverse = 0
    for dependent_id in reverse_dependencies.get(requirement_id, []):
        if dependent_id in track.active_requirements:
            active_reverse += 1
            continue
        resolved, _ = dependency_is_resolved(dependent_id, requirements, features, track)
        if not resolved:
            unresolved_reverse += 1

    csharp_status = feature.meta.get("csharp_status") if feature else ""
    risk, risk_factors = implementation_risk(requirement, features)
    independence = resolved_dependency_count + (2 * unresolved_reverse) + (4 * active_reverse)
    priority = str(requirement.meta.get("priority") or "")
    source_tier = str(requirement.meta.get("source_tier") or "")
    tier_value = str(requirement.meta.get("tier") or "")

    score = (
        PRIORITY_RANK.get(priority, 50),
        0 if tier_value == "1" else 1,
        risk,
        independence,
        CSHARP_CONTEXT_RANK.get(csharp_status, 3),
        SOURCE_RANK.get(source_tier, 10),
        requirement_id,
    )
    score_breakdown = {
        "priority": priority or "unset",
        "priority_rank": score[0],
        "tier": tier_value or "unset",
        "tier_rank": score[1],
        "implementation_risk": risk,
        "independence": independence,
        "resolved_dependency_count": resolved_dependency_count,
        "unresolved_reverse_dependency_count": unresolved_reverse,
        "active_reverse_dependency_count": active_reverse,
        "feature_csharp_status": csharp_status or "unset",
        "feature_context_rank": score[4],
        "source_tier": source_tier or "unset",
        "source_rank": score[5],
    }
    return (
        Candidate(
            requirement_id=requirement_id,
            feature_id=feature_id,
            title=str(requirement.meta.get("title") or ""),
            path=str(requirement.path),
            score=score,
            score_breakdown=score_breakdown,
            risk_factors=risk_factors,
            dependency_details=dependency_details,
            reverse_dependency_counts={
                "active": active_reverse,
                "unresolved": unresolved_reverse,
            },
        ),
        reasons,
    )


def format_score(score: tuple[Any, ...]) -> str:
    return "/".join(str(item) for item in score[:-1])


def print_table(candidates: list[Candidate], explanations: dict[str, Any], top: int) -> None:
    if not candidates:
        print("No eligible implementation-slice candidates found.")
        return
    selected = candidates[0]
    print(f"Selected: {selected.requirement_id} ({selected.feature_id}) - {selected.title}")
    print(
        "Score order: priority/tier/implementation-risk/independence/"
        "feature-context/source-tier, then requirement ID."
    )
    print()
    print("| Rank | Requirement | Feature | Score | Risk | Independence | Title |")
    print("|---:|---|---|---:|---:|---:|---|")
    for index, candidate in enumerate(candidates[:top], start=1):
        title = candidate.title.replace("|", "\\|")
        print(
            f"| {index} | {candidate.requirement_id} | {candidate.feature_id} | "
            f"{format_score(candidate.score)} | "
            f"{candidate.score_breakdown['implementation_risk']} | "
            f"{candidate.score_breakdown['independence']} | {title} |"
        )

    for requirement_id, explanation in explanations.items():
        print()
        print(f"Explain {requirement_id}:")
        print(json.dumps(explanation, indent=2, ensure_ascii=False))


def main() -> int:
    args = parse_args()
    root = Path(args.repo_root).resolve()
    features = load_pages(root, "docs/requirements/features")
    requirements = load_pages(root, "docs/requirements/requirements")
    track = parse_track(root, load_active_statuses(root))
    reverse_dependencies = build_reverse_dependencies(requirements)

    candidates: list[Candidate] = []
    ineligible: dict[str, list[str]] = {}
    for requirement in requirements.values():
        candidate, reasons = evaluate_requirement(requirement, requirements, features, track, reverse_dependencies)
        if candidate is None:
            ineligible[requirement.page_id] = reasons
        else:
            candidates.append(candidate)
    candidates.sort(key=lambda candidate: candidate.score)

    explanations: dict[str, Any] = {}
    candidate_by_id = {candidate.requirement_id: candidate for candidate in candidates}
    for requirement_id in args.explain:
        if requirement_id in candidate_by_id:
            explanations[requirement_id] = {
                "eligible": True,
                "rank": candidates.index(candidate_by_id[requirement_id]) + 1,
                "candidate": candidate_by_id[requirement_id].__dict__,
            }
        else:
            explanations[requirement_id] = {
                "eligible": False,
                "reasons": ineligible.get(requirement_id, ["requirement not found"]),
            }

    if args.format == "json":
        payload: dict[str, Any] = {
            "selected": candidates[0].__dict__ if candidates else None,
            "candidates": [candidate.__dict__ for candidate in candidates[: args.top]],
            "explanations": explanations,
        }
        if args.show_ineligible:
            payload["ineligible"] = ineligible
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print_table(candidates, explanations, args.top)

    return 0 if candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
