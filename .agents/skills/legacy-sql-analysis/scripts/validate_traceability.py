#!/usr/bin/env python3
"""Validate requirement legacy SQL and ColdFusion traceability evidence.

The validator audits frontmatter under docs/requirements/features and
docs/requirements/requirements. It checks that SQL/CF references resolve to real
files, line references are in range, object references are plausible, and
rationale text is supported by source terms in the referenced file.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


# ===== PROJECT CONFIGURATION =====
# Adjust these values to match your project layout before running the validator.
#
# LEGACY_SQL_DIR   - path relative to the repository root where legacy SQL files live
#                    e.g. "legacy-sql/MyDatabase"
# LEGACY_CF_DIR    - path relative to the repository root for the legacy codebase
#                    e.g. "legacy-codebase/MyApp"
LEGACY_SQL_DIR = "legacy-sql/{LEGACY-DB-DIR}"
LEGACY_CF_DIR = "{LEGACY-CODEBASE-DIR}"
# ===== END PROJECT CONFIGURATION =====


def find_repo_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "AGENTS.md").exists() and (path / "docs" / "requirements").exists():
            return path
    raise RuntimeError(f"Could not locate repository root from {start}")


ROOT = find_repo_root(Path(__file__).resolve())
DOC_ROOT = ROOT / "docs" / "requirements"
SQL_ROOT = ROOT / LEGACY_SQL_DIR
CF_ROOT = ROOT / LEGACY_CF_DIR
REPORT_DIR = ROOT / "reports" / "evaluations"
JSON_OUT = REPORT_DIR / "traceability-source-validation-data.json"
HTML_OUT = REPORT_DIR / "traceability-source-validation.html"


STOPWORDS = {
    "about",
    "against",
    "already",
    "and",
    "around",
    "because",
    "been",
    "being",
    "between",
    "bronze",
    "candidate",
    "cited",
    "column",
    "columns",
    "confirms",
    "context",
    "data",
    "database",
    "display",
    "does",
    "evidence",
    "file",
    "flow",
    "from",
    "helper",
    "import",
    "into",
    "line",
    "linked",
    "local",
    "maps",
    "not",
    "object",
    "only",
    "page",
    "path",
    "rationale",
    "reference",
    "referenced",
    "relevant",
    "requirement",
    "requirements",
    "result",
    "rows",
    "same",
    "search",
    "source",
    "states",
    "static",
    "stored",
    "support",
    "supporting",
    "supports",
    "table",
    "that",
    "the",
    "this",
    "through",
    "used",
    "uses",
    "when",
    "where",
    "with",
}


CONCEPTS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    (
        "customer",
        ("customer", "client", "user", "account", "contact", "name", "firstname", "lastname", "title"),
        ("customer", "client", "user", "account", "contact", "firstname", "lastname", "title", "fk_customer"),
    ),
    (
        "address",
        ("address", "street", "city", "postcode", "zip", "country", "location", "destination"),
        ("address", "street", "city", "postcode", "zip", "country", "location", "destination", "taddress"),
    ),
    (
        "validity/status",
        ("validity", "valid", "status", "cancel", "current", "active", "expired", "inactive"),
        ("valid", "status", "cancel", "current", "active", "expired", "inactive", "validfrom", "validto"),
    ),
    (
        "order/product",
        ("order", "product", "type", "form", "directive", "item", "line"),
        ("order", "product", "type", "form", "directive", "item", "ordertype", "torderheader"),
    ),
    (
        "xml/save/view",
        ("xml", "save", "store", "persist", "view", "read", "load", "reload", "open"),
        ("xml", "save", "store", "persist", "insert", "update", "view", "read", "load", "select", "show"),
    ),
    (
        "audit/log",
        ("audit", "log", "history", "creator", "created", "changed", "modified"),
        ("audit", "log", "history", "creator", "created", "changed", "tlog", "writelog", "logtype"),
    ),
    (
        "authorization/security",
        ("authorization", "authorisation", "permission", "security", "role", "access", "rbac", "authentication"),
        ("authorization", "authorisation", "permission", "security", "role", "access", "rbac", "checkauthorization"),
    ),
    (
        "print/export",
        ("print", "label", "reprint", "sheet", "export", "report", "csv", "download", "excel"),
        ("print", "label", "reprint", "sheet", "export", "report", "csv", "download", "excel", "select"),
    ),
    (
        "billing",
        ("billing", "invoice", "charge", "payment", "collection", "open item"),
        ("billing", "invoice", "charge", "payment", "collection", "open", "tbilling"),
    ),
    (
        "authentication/sso",
        ("sso", "authentication", "login", "session", "token", "identity"),
        ("sso", "authentication", "login", "session", "token", "identity", "ssoid"),
    ),
    (
        "import/staging",
        ("import", "bulk", "staging", "batch", "upload", "queue"),
        ("import", "bulk", "staging", "batch", "upload", "queue", "tstaging"),
    ),
    (
        "search/lookup",
        ("fuzzy", "lookup", "match", "search", "candidate", "find"),
        ("fuzzy", "lookup", "match", "search", "candidate", "find"),
    ),
    (
        "integration/interface",
        ("interface", "webservice", "service", "soap", "notification", "api", "integration"),
        ("interface", "webservice", "service", "soap", "notification", "api", "integration"),
    ),
    (
        "configuration",
        ("configuration", "config", "setting", "parameter", "option"),
        ("configuration", "config", "setting", "parameter", "option", "tconfiguration"),
    ),
    (
        "exception",
        ("exception", "error", "override", "special case"),
        ("exception", "error", "override", "texception"),
    ),
]


@dataclass
class Finding:
    status: str
    source_type: str
    page: str
    source_ref: str
    check: str
    message: str
    evidence: str = ""


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower()


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_+.-]{3,}", norm(value))
        if token not in STOPWORDS and not token.isdigit()
    }


def has_term(text_norm: str, term: str) -> bool:
    term_norm = norm(term)
    if not term_norm:
        return False
    if re.fullmatch(r"[a-z0-9_]+", term_norm) and len(term_norm) <= 3:
        return re.search(rf"(?<![a-z0-9_]){re.escape(term_norm)}(?![a-z0-9_])", text_norm) is not None
    return term_norm in text_norm


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def context(lines: list[str], line_no: int | None, radius: int = 8) -> str:
    if line_no is None:
        return ""
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def read_frontmatter(path: Path) -> dict[str, Any]:
    text = read_text(path)
    if not text.startswith("---"):
        return {}
    return yaml.safe_load(text.split("---", 2)[1]) or {}


def source_pages() -> list[Path]:
    return sorted((DOC_ROOT / "features").glob("FEAT-*.md")) + sorted(
        (DOC_ROOT / "requirements").glob("REQ-*.md")
    )


def source_support(rationale: str, source_text: str, source_context: str = "") -> tuple[str, list[str], list[str]]:
    source_norm = norm(source_text)
    context_norm = norm(source_context)
    rationale_norm = norm(rationale)
    active: list[str] = []
    missing: list[str] = []
    context_supported: list[str] = []
    file_supported: list[str] = []

    for concept, triggers, evidence_terms in CONCEPTS:
        if any(has_term(rationale_norm, trigger) for trigger in triggers):
            active.append(concept)
            if any(has_term(context_norm, term) for term in evidence_terms):
                context_supported.append(concept)
            elif any(has_term(source_norm, term) for term in evidence_terms):
                file_supported.append(concept)
            else:
                missing.append(concept)

    if active:
        if missing:
            return "warn", active, missing
        if file_supported and not context_supported and source_context:
            return "warn", active, []
        return "pass", active, []

    literal_tokens = tokens(rationale)
    if not literal_tokens:
        return "warn", [], ["no checkable rationale terms"]
    matches = {token for token in literal_tokens if token in source_norm}
    if len(matches) >= min(2, len(literal_tokens)):
        return "pass", sorted(matches), []
    if matches:
        return "warn", sorted(matches), sorted(literal_tokens - matches)[:8]
    return "warn", [], sorted(literal_tokens)[:8]


def object_supported(object_name: str, file_path: Path, source_text: str, line_text: str) -> tuple[str, str]:
    object_name = str(object_name or "")
    stem = file_path.stem
    object_parts = [part for part in re.split(r"[.\[\]\s]+", object_name) if part]
    candidates = {stem, object_name, *object_parts}
    source_norm = norm(source_text)
    line_norm = norm(line_text)
    normalized_candidates = {norm(candidate) for candidate in candidates if candidate}
    if norm(object_name) == norm(stem):
        return "pass", "object is represented by the SQL file name"
    if any(candidate and candidate in line_norm for candidate in normalized_candidates):
        return "pass", "object/file stem is present at cited line"
    if any(candidate and candidate in source_norm for candidate in normalized_candidates):
        return "warn", "object/file stem is present in source file but not at cited line"
    return "fail", f"object {object_name!r} was not found in source content"


def parse_cf_entry(entry: str) -> tuple[str, int | None, str] | None:
    match = re.match(r"^(?P<ref>.+?)\s+\(rationale:\s*(?P<rationale>.*)\)$", entry)
    if not match:
        return None
    ref = match.group("ref").strip()
    rationale = match.group("rationale").strip()
    line_match = re.match(r"^(?P<file>.+?):(?P<line>\d+)$", ref)
    if line_match:
        return line_match.group("file"), int(line_match.group("line")), rationale
    return ref, None, rationale


def validate_sql(page: Path, item: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    page_ref = str(page.relative_to(ROOT))
    file_ref = str(item.get("file", ""))
    source_ref = f"{file_ref}:{item.get('line', '')} {item.get('object', '')}".strip()
    rationale = str(item.get("note", ""))
    source_path = ROOT / file_ref

    if not file_ref or not source_path.exists():
        return [
            Finding("fail", "sql", page_ref, source_ref, "file", "SQL source file is missing")
        ]
    if not rationale.startswith("rationale:"):
        findings.append(
            Finding("fail", "sql", page_ref, source_ref, "rationale", "SQL note does not start with rationale:")
        )

    lines = read_text(source_path).splitlines()
    try:
        line_no = int(item.get("line", 0))
    except (TypeError, ValueError):
        line_no = 0
    if line_no < 1 or line_no > len(lines):
        findings.append(
            Finding("fail", "sql", page_ref, source_ref, "line", f"Line {line_no} is outside 1..{len(lines)}")
        )
        line_text = ""
        ctx = ""
    else:
        line_text = lines[line_no - 1]
        ctx = context(lines, line_no)

    object_status, object_message = object_supported(str(item.get("object", "")), source_path, "\n".join(lines), line_text)
    if object_status != "pass":
        findings.append(
            Finding(object_status, "sql", page_ref, source_ref, "object", object_message, line_text.strip())
        )

    support_status, active, missing = source_support(rationale, "\n".join(lines), ctx)
    if support_status != "pass":
        findings.append(
            Finding(
                support_status,
                "sql",
                page_ref,
                source_ref,
                "rationale-support",
                "Rationale concepts need manual review"
                if support_status == "warn"
                else "Rationale concepts are not supported by referenced SQL",
                f"concepts={active}; missing={missing}",
            )
        )
    if not findings:
        findings.append(Finding("pass", "sql", page_ref, source_ref, "all", "SQL reference and rationale validated"))
    return findings


def validate_cf(page: Path, entry: str) -> list[Finding]:
    findings: list[Finding] = []
    page_ref = str(page.relative_to(ROOT))
    parsed = parse_cf_entry(entry)
    if not parsed:
        return [
            Finding("fail", "cf", page_ref, entry, "format", "CF source entry is not '<file[:line]> (rationale: ...)'")
        ]
    file_ref, line_no, rationale = parsed
    source_ref = f"{file_ref}:{line_no}" if line_no else file_ref
    source_path = CF_ROOT / file_ref
    if not source_path.exists():
        return [
            Finding("fail", "cf", page_ref, source_ref, "file", "ColdFusion source file is missing")
        ]
    if not rationale:
        findings.append(Finding("fail", "cf", page_ref, source_ref, "rationale", "ColdFusion rationale is empty"))

    lines = read_text(source_path).splitlines()
    if line_no is not None and (line_no < 1 or line_no > len(lines)):
        findings.append(
            Finding("fail", "cf", page_ref, source_ref, "line", f"Line {line_no} is outside 1..{len(lines)}")
        )
        ctx = ""
    else:
        ctx = context(lines, line_no) if line_no is not None else ""

    support_status, active, missing = source_support(rationale, "\n".join(lines), ctx)
    if support_status != "pass":
        findings.append(
            Finding(
                support_status,
                "cf",
                page_ref,
                source_ref,
                "rationale-support",
                "Rationale concepts need manual review"
                if support_status == "warn"
                else "Rationale concepts are not supported by referenced CF source",
                f"concepts={active}; missing={missing}",
            )
        )
    if line_no is None and support_status == "pass":
        findings.append(
            Finding("warn", "cf", page_ref, source_ref, "granularity", "CF relationship is file-level; add a line number when practical")
        )
    if not findings:
        findings.append(Finding("pass", "cf", page_ref, source_ref, "all", "ColdFusion reference and rationale validated"))
    return findings


def validate() -> dict[str, Any]:
    findings: list[Finding] = []
    pages_with_sql = 0
    pages_with_cf = 0
    sql_entries = 0
    cf_entries = 0

    for page in source_pages():
        meta = read_frontmatter(page)
        sql_items = meta.get("sql_source") or []
        cf_items = meta.get("cf_source") or []
        if sql_items:
            pages_with_sql += 1
        if cf_items:
            pages_with_cf += 1
        for item in sql_items:
            sql_entries += 1
            findings.extend(validate_sql(page, item))
        for entry in cf_items:
            cf_entries += 1
            findings.extend(validate_cf(page, str(entry)))

    status_counts = Counter(f.status for f in findings)
    issue_counts = Counter(f.status for f in findings if f.status != "pass")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "roots": {
            "docs": str(DOC_ROOT.relative_to(ROOT)),
            "legacy_sql": str(SQL_ROOT.relative_to(ROOT)),
            "coldfusion": str(CF_ROOT.relative_to(ROOT)),
        },
        "summary": {
            "pages_scanned": len(source_pages()),
            "pages_with_sql": pages_with_sql,
            "pages_with_cf": pages_with_cf,
            "sql_entries": sql_entries,
            "cf_entries": cf_entries,
            "findings": len(findings),
            "pass": status_counts.get("pass", 0),
            "warn": status_counts.get("warn", 0),
            "fail": status_counts.get("fail", 0),
            "issues": sum(issue_counts.values()),
        },
        "findings": [asdict(f) for f in findings],
    }


def write_html(data: dict[str, Any]) -> None:
    summary = data["summary"]
    issue_rows = [row for row in data["findings"] if row["status"] != "pass"]
    rows_html = "\n".join(
        "<tr>"
        f"<td><span class='status {html.escape(row['status'])}'>{html.escape(row['status'])}</span></td>"
        f"<td>{html.escape(row['source_type'])}</td>"
        f"<td>{html.escape(row['page'])}</td>"
        f"<td>{html.escape(row['source_ref'])}</td>"
        f"<td>{html.escape(row['check'])}</td>"
        f"<td>{html.escape(row['message'])}</td>"
        f"<td>{html.escape(row.get('evidence', ''))}</td>"
        "</tr>"
        for row in issue_rows
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Legacy Source Traceability Validation</title>
  <style>
    :root {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; background: #f6f8fb; }}
    body {{ margin: 0; padding: 32px; }}
    h1 {{ margin-top: 0; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 20px 0; }}
    .card {{ background: white; border: 1px solid #d8e0eb; border-radius: 8px; padding: 14px; }}
    .card strong {{ display: block; font-size: 1.8rem; }}
    input {{ width: 100%; padding: 10px; margin: 12px 0 16px; border: 1px solid #b9c5d6; border-radius: 6px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d8e0eb; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e4eaf2; vertical-align: top; font-size: 13px; }}
    th {{ text-align: left; background: #eef3f8; position: sticky; top: 0; }}
    .status {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 700; font-size: 12px; }}
    .pass {{ background: #d8f3dc; color: #1b5e20; }}
    .warn {{ background: #fff3bf; color: #7a4d00; }}
    .fail {{ background: #ffd6d6; color: #8a1f11; }}
    .note {{ color: #526173; }}
  </style>
</head>
<body>
  <h1>Legacy Source Traceability Validation</h1>
  <p class="note">Generated at {html.escape(data['generated_at'])}. Pass rows are included in JSON; this HTML focuses on warnings and failures.</p>
  <div class="cards">
    <div class="card"><span>Pages scanned</span><strong>{summary['pages_scanned']}</strong></div>
    <div class="card"><span>SQL entries</span><strong>{summary['sql_entries']}</strong></div>
    <div class="card"><span>CF entries</span><strong>{summary['cf_entries']}</strong></div>
    <div class="card"><span>Warnings</span><strong>{summary['warn']}</strong></div>
    <div class="card"><span>Failures</span><strong>{summary['fail']}</strong></div>
  </div>
  <input id="filter" placeholder="Search page, source, check, message..." oninput="filterRows()">
  <table id="issues">
    <thead><tr><th>Status</th><th>Type</th><th>Page</th><th>Source</th><th>Check</th><th>Message</th><th>Evidence</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <script>
    function filterRows() {{
      const q = document.getElementById('filter').value.toLowerCase();
      for (const tr of document.querySelectorAll('#issues tbody tr')) {{
        tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
      }}
    }}
  </script>
</body>
</html>
"""
    HTML_OUT.write_text(html_text, encoding="utf-8")


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    data = validate()
    JSON_OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_html(data)
    summary = data["summary"]
    print(
        f"validated {summary['sql_entries']} SQL and {summary['cf_entries']} CF entries: "
        f"{summary['pass']} pass, {summary['warn']} warn, {summary['fail']} fail"
    )
    print(JSON_OUT)
    print(HTML_OUT)
    return 1 if summary["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
