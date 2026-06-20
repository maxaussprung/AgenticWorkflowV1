#!/usr/bin/env python3
"""Reconcile docs/requirements/ into Azure Boards work items.

Repo is the source of truth for *what should exist*; this tool ensures a
matching work item exists on the board for every eligible page, idempotently.
See docs/architecture/tracking.md for the mapping and enforcement model.

Mapping:
    product      -> Epic        (always eligible)
    feature      -> Feature     (always eligible; parent = its product's Epic)
    requirement  -> User Story  (eligible when status: approved; parent = feature)

The work item is matched by the tag `repo-id:<ID>`. The tool writes only Title,
type, parent link, the `repo-id:<ID>` + `project-sync` tags, and a back-link.
It never touches State, AssignedTo, IterationPath, or effort — the board owns those.

Modes:
    --check   report drift; exit 1 if any eligible page lacks a correct work item.
              With no API token, validates repo-side consistency only and warns.
    --apply   create missing work items and repair parent links / titles.

Auth (for board access): set AZDO_ORG_URL, AZDO_PROJECT, and either AZDO_PAT or
SYSTEM_ACCESSTOKEN (the pipeline build-service token).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ===== CONFIGURATION =====
# All project-specific values are driven by environment variables so this
# script works for any project without editing source.
#
# Required for board access (--check against real board / --apply):
#   AZDO_ORG_URL   — e.g. "https://dev.azure.com/my-org"
#   AZDO_PROJECT   — e.g. "my-project"
#   AZDO_PAT       — Personal Access Token with Work Items: read & write
#                    (alternative: SYSTEM_ACCESSTOKEN for pipeline runs)
#
# Optional:
#   SITE_BASE_URL  — Base URL of the published requirements site, used for
#                    back-links on work items.
#                    e.g. "https://my-site.azurestaticapps.net/requirements-site"
#
# The sync tag applied to every created work item (in addition to repo-id:<ID>):
SYNC_TAG = os.environ.get("AZDO_SYNC_TAG", "project-sync")

REPO_ROOT = Path(__file__).resolve().parents[2]
REQ_DIR = REPO_ROOT / "docs" / "requirements"
SITE_BASE_URL = os.environ.get(
    "SITE_BASE_URL", "https://example.invalid/requirements-site"
)
# ==========================

# repo type -> (Azure work-item type, eligibility predicate)
KIND_BY_TYPE = {
    "product": "Epic",
    "feature": "Feature",
    "requirement": "User Story",
}


@dataclass
class Item:
    repo_id: str
    title: str
    kind: str                      # Azure work-item type
    parent_repo_id: str | None     # repo ID of the parent page, if any
    rel_url: str                   # path under the site, for the back-link
    warnings: list[str] = field(default_factory=list)


def read_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return None


def first(value):
    """Frontmatter fields may be a scalar or a list; take the first scalar."""
    if isinstance(value, list):
        return str(value[0]).strip() if value else None
    if value is None:
        return None
    return str(value).strip()


def discover() -> list[Item]:
    items: list[Item] = []
    for sub, page_type in (("products", "product"), ("features", "feature"),
                           ("requirements", "requirement")):
        for path in sorted((REQ_DIR / sub).glob("*.md")):
            if path.name == "index.md":
                continue
            fm = read_frontmatter(path)
            if not fm or fm.get("type") != page_type:
                continue
            repo_id = str(fm.get("id", "")).strip()
            if not repo_id:
                continue

            if page_type == "requirement" and str(fm.get("status", "")).strip() != "approved":
                continue  # not yet through the governance gate

            parent = None
            if page_type == "feature":
                parent = first(fm.get("Product"))
            elif page_type == "requirement":
                parent = first(fm.get("feature"))

            item = Item(
                repo_id=repo_id,
                title=str(fm.get("title", repo_id)).strip(),
                kind=KIND_BY_TYPE[page_type],
                parent_repo_id=parent,
                rel_url=f"{sub}/{path.stem}/",
            )
            if page_type != "product" and not parent:
                item.warnings.append(f"{repo_id}: missing parent reference")
            items.append(item)
    return items


def validate_repo_side(items: list[Item]) -> list[str]:
    """Repo-only checks that don't need the board: unique IDs, resolvable parents."""
    problems: list[str] = []
    by_id = {it.repo_id: it for it in items}
    seen: set[str] = set()
    for it in items:
        if it.repo_id in seen:
            problems.append(f"duplicate id: {it.repo_id}")
        seen.add(it.repo_id)
        problems.extend(it.warnings)
        if it.parent_repo_id and it.parent_repo_id not in by_id:
            problems.append(
                f"{it.repo_id}: parent {it.parent_repo_id} is not an eligible page "
                f"(missing, or a requirement whose parent feature is absent)"
            )
    return problems


# --------------------------------------------------------------------------- #
# Azure DevOps REST client (only used when a token is configured)
# --------------------------------------------------------------------------- #
class Boards:
    API = "7.1"

    def __init__(self, org_url: str, project: str, token: str, pat: bool):
        self.org_url = org_url.rstrip("/")
        self.project = project
        if pat:
            raw = base64.b64encode(f":{token}".encode()).decode()
            self.auth = f"Basic {raw}"
        else:
            self.auth = f"Bearer {token}"

    def _req(self, method: str, url: str, body: object | None = None,
             content_type: str = "application/json") -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", self.auth)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read() or "{}")
        except urllib.error.HTTPError as exc:  # surface the API error body
            raise SystemExit(f"Azure DevOps API {exc.code}: {exc.read().decode()}")

    def find_by_repo_id(self, repo_id: str) -> int | None:
        url = f"{self.org_url}/{self.project}/_apis/wit/wiql?api-version={self.API}"
        wiql = {"query": (
            "SELECT [System.Id] FROM workitems "
            f"WHERE [System.Tags] CONTAINS 'repo-id:{repo_id}'"
        )}
        res = self._req("POST", url, wiql).get("workItems", [])
        return res[0]["id"] if res else None

    def create(self, kind: str, item: Item, parent_id: int | None) -> int:
        url = (f"{self.org_url}/{self.project}/_apis/wit/workitems/"
               f"${urllib.parse.quote(kind)}?api-version={self.API}")
        ops = [
            {"op": "add", "path": "/fields/System.Title", "value": item.title},
            {"op": "add", "path": "/fields/System.Tags",
             "value": f"{SYNC_TAG}; repo-id:{item.repo_id}"},
            {"op": "add", "path": "/relations/-", "value": {
                "rel": "Hyperlink",
                "url": f"{SITE_BASE_URL}/{item.rel_url}",
                "attributes": {"comment": f"Requirements site — {item.repo_id}"},
            }},
        ]
        if parent_id is not None:
            ops.append({"op": "add", "path": "/relations/-", "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": f"{self.org_url}/_apis/wit/workItems/{parent_id}",
            }})
        return self._req("PATCH", url, ops,
                         content_type="application/json-patch+json")["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="report drift; exit 1 on drift (alias: --dry-run)")
    mode.add_argument("--dry-run", action="store_true", dest="check")
    mode.add_argument("--apply", action="store_true",
                      help="create missing work items and repair links")
    args = ap.parse_args()

    items = discover()
    print(f"discovered {len(items)} eligible pages "
          f"({sum(i.kind == 'Epic' for i in items)} Epic, "
          f"{sum(i.kind == 'Feature' for i in items)} Feature, "
          f"{sum(i.kind == 'User Story' for i in items)} Story)")

    problems = validate_repo_side(items)
    if problems:
        print("repo-side problems:")
        for p in problems:
            print(f"  - {p}")

    org = os.environ.get("AZDO_ORG_URL")
    project = os.environ.get("AZDO_PROJECT")
    pat = os.environ.get("AZDO_PAT")
    sys_token = os.environ.get("SYSTEM_ACCESSTOKEN")
    token, is_pat = (pat, True) if pat else (sys_token, False)

    if not (org and project and token):
        msg = ("no board credentials (AZDO_ORG_URL / AZDO_PROJECT / AZDO_PAT|"
               "SYSTEM_ACCESSTOKEN) — repo-side validation only; board drift NOT checked")
        if args.apply:
            print(f"ERROR: --apply requires board credentials. {msg}")
            return 2
        print(f"WARNING: {msg}")
        return 1 if problems else 0

    boards = Boards(org, project, token, pat=is_pat)
    by_id = {it.repo_id: it for it in items}
    wi_cache: dict[str, int | None] = {}

    def board_id(repo_id: str) -> int | None:
        if repo_id not in wi_cache:
            wi_cache[repo_id] = boards.find_by_repo_id(repo_id)
        return wi_cache[repo_id]

    drift, created = [], 0
    # parents before children so hierarchy links resolve in one pass
    for it in sorted(items, key=lambda i: {"Epic": 0, "Feature": 1, "User Story": 2}[i.kind]):
        existing = board_id(it.repo_id)
        if existing is not None:
            continue
        if args.check:
            drift.append(f"missing {it.kind} for {it.repo_id} ({it.title})")
            continue
        parent_id = board_id(it.parent_repo_id) if it.parent_repo_id else None
        if it.parent_repo_id and parent_id is None:
            drift.append(f"cannot link {it.repo_id}: parent {it.parent_repo_id} not on board yet")
            continue
        new_id = boards.create(it.kind, it, parent_id)
        wi_cache[it.repo_id] = new_id
        created += 1
        print(f"  created {it.kind} #{new_id} for {it.repo_id}")

    if args.apply:
        print(f"applied: created {created} work item(s)")
    if drift:
        print("DRIFT:")
        for d in drift:
            print(f"  - {d}")
    return 1 if (drift or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
