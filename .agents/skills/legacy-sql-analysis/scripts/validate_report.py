#!/usr/bin/env python3
"""Validate the generated legacy SQL analysis report against its cited sources.

This validator treats the HTML report as generated analysis. It checks that source references are
technically valid and that inferred claims are visible as warnings instead of silent facts. It does
not execute or modify imported legacy SQL.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "pypdf is required. Run with the bundled workspace Python from load_workspace_dependencies."
    ) from exc


def find_repo_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "AGENTS.md").exists() and (path / "legacy-sql").exists():
            return path
    raise SystemExit("Could not locate repository root from validator path.")


ROOT = find_repo_root(Path(__file__).resolve())

# ===== PROJECT CONFIGURATION =====
# All project-specific values are declared here. Adapt these for your project
# before running the validator.

# Name of the legacy database folder under legacy-sql/
LEGACY_DB_NAME = "{LEGACY-DB-NAME}"  # e.g. "Example_Database"

# Namespace directory inside csharp/src/backend/ that contains the Data/Configuration folder
BACKEND_NAMESPACE = "{BACKEND-NAMESPACE}"  # e.g. "YourCompany.YourProject.Infrastructure"

# Set of product codes that must appear in the product_sql section of the report
# Configure these for your project's products
EXPECTED_PRODUCT_CODES = {"PRODUCT-001", "PRODUCT-002", "PRODUCT-003"}

# PDF spec documents that the report must cite (name -> filename under PDF_DIR)
PDF_FILES_CONFIG = {
    "{SPEC-DOCUMENT-NAME}.pdf": "{SPEC-DOCUMENT-NAME}.pdf",
}

# Relative path (from repo root) to the MkDocs coverage page generated from the report
MKDOCS_COVERAGE_PAGE_REL = "docs/requirements/sql-csharp-coverage.md"

# Expected top-level keys in the report JSON
EXPECTED_JSON_KEYS = {
    "generated_at",
    "sql_root",
    "sql_git",
    "pdfs",
    "sql_files",
    "topic_comparison",
    "spec_coverage_overview",
    "db_table_recommendations",
    "domain_model_recommendation_er",
    "recommended_acid_er_diagrams",
    "semantic_map",
    "print_fields",
    "product_sql",
    "csharp_backend",
    "csharp_sql_model",
    "function_logic",
    "legacy_code",
    "diagram_sources",
}

# Expected HTML section ids in the generated report
EXPECTED_SECTION_IDS = {
    "section-001",
    "section-002",
    "chapter-overview",
    "chapter-sql-landscape",
    "overview",
    "plan",
    "sources",
    "diagrams",
    "er-diagrams",
    "comparison",
    "products",
    "chapter-sql-pdf",
    "chapter-csharp-gap",
    "csharp-backend",
    "csharp-sql-model",
    "chapter-function-flows",
    "sql-functions",
    "inventory",
    "chapter-review",
    "risks",
    "appendix",
}

# ===== END PROJECT CONFIGURATION =====

SQL_ROOT = ROOT / "legacy-sql" / LEGACY_DB_NAME
CSHARP_BACKEND_ROOT = ROOT / "csharp" / "src" / "backend"
REPORT_DIR = ROOT / "reports" / "evaluations" / "legacy-sql"
REPORT_HTML = REPORT_DIR / "legacy-sql-analysis.html"
REPORT_JSON = REPORT_DIR / "legacy-sql-analysis-data.json"
VALIDATION_HTML = REPORT_DIR / "legacy-sql-analysis-validation.html"
VALIDATION_JSON = REPORT_DIR / "legacy-sql-analysis-validation-data.json"
MKDOCS_COVERAGE_PAGE = ROOT / MKDOCS_COVERAGE_PAGE_REL
MKDOCS_CONFIG = ROOT / "tools" / "requirements-site" / "mkdocs.yml"
PDF_DIR = ROOT / "docs" / "requirements" / "source-import"
PDF_FILES = {name: PDF_DIR / filename for name, filename in PDF_FILES_CONFIG.items()}
FILE_REF_KEYS = {"evidence", "file_refs", "source_refs", "legacy_sql_evidence", "legacy_evidence", "csharp_evidence"}
SAFE_LEGACY_CODE_WORDS = {"unverified", "missing", "not available", "not proof", "unavailable", "future source", "static", "source evidence", "runtime telemetry"}


@dataclass
class Check:
    status: str
    area: str
    check: str
    subject: str
    source: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


class ReportHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.headings: list[str] = []
        self.tables = 0
        self._heading_tag: str | None = None
        self._heading_buf: list[str] = []
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if "id" in attr_map and attr_map["id"]:
            self.ids.add(attr_map["id"])
        if tag in {"h2", "h3"}:
            self._heading_tag = tag
            self._heading_buf = []
        if tag == "table":
            self.tables += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_tag:
            heading = " ".join("".join(self._heading_buf).split())
            if heading:
                self.headings.append(heading)
            self._heading_tag = None
            self._heading_buf = []

    def handle_data(self, data: str) -> None:
        self._text_parts.append(data)
        if self._heading_tag:
            self._heading_buf.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self._text_parts).split())


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError:
            continue
    return path.read_text(errors="replace")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value)
    return value.casefold().strip()


def compact(value: object, limit: int = 180) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def line_context(text: str, line: int, radius: int = 5) -> str:
    lines = text.splitlines()
    if line < 1 or line > len(lines):
        return ""
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start - 1 : end])


def term_present(text: str, terms: Iterable[str]) -> bool:
    normalized_text = normalize(text)
    return any(normalize(term) and normalize(term) in normalized_text for term in terms)


def add(checks: list[Check], status: str, area: str, check: str, subject: str, source: str, message: str, **evidence: Any) -> None:
    checks.append(Check(status=status, area=area, check=check, subject=subject, source=source, message=message, evidence=evidence))


def load_json_report(checks: list[Check]) -> dict[str, Any]:
    if not REPORT_JSON.exists():
        add(checks, "fail", "Inputs", "JSON exists", rel(REPORT_JSON), "", "Report JSON is missing.")
        return {}
    try:
        data = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add(checks, "fail", "Inputs", "JSON parses", rel(REPORT_JSON), "", f"Invalid JSON: {exc}")
        return {}
    add(checks, "pass", "Inputs", "JSON parses", rel(REPORT_JSON), rel(REPORT_JSON), "Report JSON parsed successfully.")
    return data


def load_html_report(checks: list[Check]) -> tuple[str, ReportHtmlParser]:
    parser = ReportHtmlParser()
    if not REPORT_HTML.exists():
        add(checks, "fail", "Inputs", "HTML exists", rel(REPORT_HTML), "", "Report HTML is missing.")
        return "", parser
    text = REPORT_HTML.read_text(encoding="utf-8")
    try:
        parser.feed(text)
    except Exception as exc:  # HTMLParser is permissive, but keep this explicit.
        add(checks, "fail", "Inputs", "HTML parses", rel(REPORT_HTML), rel(REPORT_HTML), f"HTML parser failed: {exc}")
        return text, parser
    add(checks, "pass", "Inputs", "HTML parses", rel(REPORT_HTML), rel(REPORT_HTML), "Report HTML parsed successfully.")
    return text, parser


def load_pdf_pages(checks: list[Check]) -> dict[str, dict[int, str]]:
    pages: dict[str, dict[int, str]] = {}
    for name, path in PDF_FILES.items():
        if not path.exists():
            add(checks, "fail", "PDF sources", "PDF exists", name, rel(path), "Expected PDF source file is missing.")
            continue
        reader = PdfReader(str(path))
        pages[name] = {index + 1: (page.extract_text() or "") for index, page in enumerate(reader.pages)}
        add(
            checks,
            "pass",
            "PDF sources",
            "PDF parsed",
            name,
            rel(path),
            f"PDF parsed with {len(reader.pages)} pages.",
        )
    return pages


def iter_pdf_refs(obj: Any, path: str = "$") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(obj, dict):
        refs = obj.get("pdf_refs")
        if isinstance(refs, list):
            for index, ref in enumerate(refs):
                if isinstance(ref, dict):
                    yield f"{path}.pdf_refs[{index}]", ref
        for key, value in obj.items():
            if key != "pdf_refs":
                yield from iter_pdf_refs(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from iter_pdf_refs(value, f"{path}[{index}]")


def candidate_terms(parent: dict[str, Any] | None, ref: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    if parent:
        for key in ("object", "primary_object", "capability", "code", "field", "name", "topic", "official_topic", "diagram", "area"):
            value = parent.get(key)
            if isinstance(value, str):
                terms.append(value)
        for key in ("terms", "sql_terms", "doc_terms", "legacy_terms", "csharp_terms", "spec_terms"):
            values = parent.get(key)
            if isinstance(values, list):
                terms.extend(str(value) for value in values)
    for key in ("object", "file"):
        value = ref.get(key)
        if isinstance(value, str):
            terms.append(value)
            terms.append(Path(value).stem)
            terms.append(value.split(".")[-1])
    return [term for term in dict.fromkeys(terms) if term]


def iter_file_refs(obj: Any, path: str = "$", parent: dict[str, Any] | None = None) -> Iterable[tuple[str, dict[str, Any], dict[str, Any] | None]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FILE_REF_KEYS and isinstance(value, list):
                for index, ref in enumerate(value):
                    if isinstance(ref, dict) and isinstance(ref.get("file"), str):
                        yield f"{path}.{key}[{index}]", ref, obj
            elif key not in FILE_REF_KEYS:
                yield from iter_file_refs(value, f"{path}.{key}", obj)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from iter_file_refs(value, f"{path}[{index}]", parent)


def validate_structure(checks: list[Check], data: dict[str, Any], html_text: str, parser: ReportHtmlParser) -> None:
    missing_keys = sorted(EXPECTED_JSON_KEYS - set(data))
    add(
        checks,
        "fail" if missing_keys else "pass",
        "Structure",
        "JSON top-level keys",
        rel(REPORT_JSON),
        rel(REPORT_JSON),
        f"Missing keys: {', '.join(missing_keys)}" if missing_keys else "All expected JSON top-level keys are present.",
    )

    missing_ids = sorted(EXPECTED_SECTION_IDS - parser.ids)
    add(
        checks,
        "fail" if missing_ids else "pass",
        "Structure",
        "HTML section ids",
        rel(REPORT_HTML),
        rel(REPORT_HTML),
        f"Missing section ids: {', '.join(missing_ids)}" if missing_ids else "All expected HTML section ids are present.",
    )

    expected_tables = 15
    add(
        checks,
        "fail" if parser.tables < expected_tables else "pass",
        "Structure",
        "HTML table count",
        rel(REPORT_HTML),
        rel(REPORT_HTML),
        f"Found {parser.tables} tables; expected at least {expected_tables}.",
        table_count=parser.tables,
    )

    section_markers = [
        ("Coverage Overview", data.get("spec_coverage_overview", {}).get("rows", []), "area"),
        ("DB Table Recommendations", data.get("db_table_recommendations", {}).get("rows", []), "legacy_table"),
        ("Domain Model Overlay", [data.get("domain_model_recommendation_er", {})], "title"),
        ("Recommended ACID Target Model: Complete And Focused ER Diagrams", data.get("recommended_acid_er_diagrams", {}).get("diagrams", []), "title"),
        ("Semantic Map", data.get("semantic_map", []), "official_topic"),
        ("Domain Topic Coverage", data.get("topic_comparison", []), "topic"),
        ("Print Datafile Field Mapping", data.get("print_fields", []), "field"),
        ("Products To SQL", data.get("product_sql", []), "code"),
        ("C# Backend Comparison", data.get("csharp_backend", []), "capability"),
        ("Existing C# SQL And Persistence Model", data.get("csharp_sql_model", {}).get("summary", []), "topic"),
        ("SQL Functions: Business Logic", data.get("function_logic", {}).get("details", []), "object"),
    ]
    normalized_html = normalize(html_text)
    for section, rows, key in section_markers:
        if not rows:
            add(checks, "fail", "Structure", "Section has JSON rows", section, rel(REPORT_JSON), "Section has no rows in JSON.")
            continue
        marker = str(rows[0].get(key, ""))
        supported = normalize(section) in normalized_html and normalize(marker) in normalized_html
        add(
            checks,
            "pass" if supported else "fail",
            "Structure",
            "HTML contains JSON section marker",
            section,
            rel(REPORT_HTML),
            f"HTML contains representative marker '{marker}'." if supported else f"HTML does not contain representative marker '{marker}'.",
            row_count=len(rows),
        )


def validate_pdf_refs(checks: list[Check], data: dict[str, Any], pdf_pages: dict[str, dict[int, str]]) -> None:
    refs = list(iter_pdf_refs(data))
    add(
        checks,
        "pass" if refs else "fail",
        "PDF references",
        "PDF refs discovered",
        rel(REPORT_JSON),
        rel(REPORT_JSON),
        f"Discovered {len(refs)} PDF references in report data.",
    )
    for path, ref in refs:
        pdf_name = ref.get("pdf")
        page = ref.get("page")
        terms = [str(term) for term in ref.get("terms", []) if str(term).strip()]
        snippet = str(ref.get("snippet", "") or "")
        source = f"{pdf_name}, page {page}"

        if pdf_name not in pdf_pages:
            add(checks, "fail", "PDF references", "PDF file exists", path, source, "Referenced PDF is not an expected source file.", ref=ref)
            continue
        if not isinstance(page, int) or page not in pdf_pages[pdf_name]:
            add(checks, "fail", "PDF references", "Page exists", path, source, "Referenced page is outside the PDF page range.", ref=ref)
            continue

        page_text = pdf_pages[pdf_name][page]
        found_terms = [term for term in terms if term_present(page_text, [term])]
        normalized_page = normalize(page_text)
        normalized_snippet = normalize(snippet.replace("...", ""))
        snippet_found = bool(normalized_snippet and normalized_snippet in normalized_page)

        if snippet_found and found_terms:
            add(checks, "pass", "PDF references", "Snippet and terms found", path, source, "PDF snippet and matched terms are present on the cited page.", terms=found_terms)
        elif found_terms:
            add(checks, "warn", "PDF references", "Terms found but snippet not exact", path, source, "Matched terms are present, but the snippet could not be found exactly after normalization.", terms=found_terms, snippet=snippet)
        else:
            add(checks, "fail", "PDF references", "Terms found on cited page", path, source, "None of the cited terms were found on the referenced page.", terms=terms, snippet=snippet)


def validate_file_refs(checks: list[Check], data: dict[str, Any]) -> None:
    refs = list(iter_file_refs(data))
    add(
        checks,
        "pass" if refs else "fail",
        "File references",
        "File refs discovered",
        rel(REPORT_JSON),
        rel(REPORT_JSON),
        f"Discovered {len(refs)} file/line references in report data.",
    )
    for path, ref, parent in refs:
        rel_file = str(ref.get("file", ""))
        line = ref.get("line", 1)
        file_path = ROOT / rel_file
        source = f"{rel_file}:{line}"
        if not file_path.exists():
            add(checks, "fail", "File references", "File exists", path, source, "Referenced file is missing.", ref=ref)
            continue
        text = read_text(file_path)
        lines = text.splitlines()
        if not isinstance(line, int) or line < 1 or line > len(lines):
            add(checks, "fail", "File references", "Line exists", path, source, f"Referenced line is outside file range 1..{len(lines)}.", ref=ref)
            continue
        terms = candidate_terms(parent, ref)
        context = line_context(text, line)
        if not terms or term_present(context, terms):
            add(checks, "pass", "File references", "File and line supported", path, source, "Referenced file and line exist, and nearby context supports the cited term.", terms=terms[:8])
        else:
            add(
                checks,
                "warn",
                "File references",
                "Line exists but term is semantic",
                path,
                source,
                "Referenced file and line exist, but nearby context does not contain the expected term exactly; review semantic mapping manually.",
                terms=terms[:8],
            )


def validate_spec_coverage_overview(checks: list[Check], data: dict[str, Any], html_text: str) -> None:
    overview = data.get("spec_coverage_overview", {})
    rows = overview.get("rows", []) if isinstance(overview, dict) else []
    add(
        checks,
        "pass" if rows else "fail",
        "Spec overview",
        "Overview rows present",
        "spec_coverage_overview.rows",
        rel(REPORT_JSON),
        f"Spec overview contains {len(rows)} rows." if rows else "Spec overview rows are missing.",
    )
    if not rows:
        return

    statuses = {row.get("coverage") for row in rows}
    expected_statuses = {"Complete", "Partial", "Missing"}
    unsupported_statuses = sorted(str(status) for status in statuses - expected_statuses)
    missing_statuses = sorted(expected_statuses - statuses)
    add(
        checks,
        "pass" if not unsupported_statuses and not missing_statuses else "fail",
        "Spec overview",
        "Coverage status vocabulary",
        "spec_coverage_overview.rows.coverage",
        rel(REPORT_JSON),
        (
            "The coverage overview uses the expected vocabulary Complete/Partial/Missing."
            if not unsupported_statuses and not missing_statuses
            else f"Unsupported statuses: {unsupported_statuses}; missing statuses: {missing_statuses}."
        ),
        statuses=sorted(str(status) for status in statuses),
    )

    primary_pdf_name = next(iter(PDF_FILES_CONFIG), "")
    primary_pdf_path = f"docs/requirements/source-import/{primary_pdf_name}"
    source_pdf = overview.get("source_pdf")
    wrong_pdf_refs = [
        f"{row.get('area')} -> {ref.get('pdf')}"
        for row in rows
        for ref in row.get("pdf_refs", [])
        if ref.get("pdf") != primary_pdf_name
    ]
    add(
        checks,
        "pass" if source_pdf == primary_pdf_path and not wrong_pdf_refs else "fail",
        "Spec overview",
        "Spec PDF anchoring",
        "spec_coverage_overview.source_pdf",
        rel(REPORT_JSON),
        (
            "Coverage overview is anchored to the primary spec PDF."
            if source_pdf == primary_pdf_path and not wrong_pdf_refs
            else "Coverage overview is not consistently anchored to the primary spec PDF."
        ),
        wrong_pdf_refs=wrong_pdf_refs[:10],
    )

    rows_missing_sources = [
        row.get("area")
        for row in rows
        if not row.get("pdf_refs") or not row.get("legacy_sql_evidence")
    ]
    add(
        checks,
        "pass" if not rows_missing_sources else "warn",
        "Spec overview",
        "Rows have PDF and SQL evidence",
        "spec_coverage_overview.rows",
        rel(REPORT_JSON),
        (
            "Every spec overview row has PDF refs and legacy SQL evidence."
            if not rows_missing_sources
            else "Some spec overview rows are semantic and need manual review because PDF or SQL evidence is sparse."
        ),
        rows=rows_missing_sources,
    )

    has_html = (
        "chapter-overview" in html_text
        and "Coverage" in html_text
        and "Complete" in html_text
        and "Partial" in html_text
        and "Missing" in html_text
    )
    add(
        checks,
        "pass" if has_html else "fail",
        "Spec overview",
        "HTML overview chapter present",
        "chapter-overview",
        rel(REPORT_HTML),
        "HTML contains the overview chapter and coverage summary cards." if has_html else "HTML overview chapter or coverage summary is missing.",
    )


def validate_mkdocs_spec_coverage_page(checks: list[Check], data: dict[str, Any]) -> None:
    overview = data.get("spec_coverage_overview", {})
    rows = overview.get("rows", []) if isinstance(overview, dict) else []
    if not MKDOCS_COVERAGE_PAGE.exists():
        add(
            checks,
            "fail",
            "Spec overview",
            "MkDocs coverage page exists",
            rel(MKDOCS_COVERAGE_PAGE),
            rel(REPORT_JSON),
            "Dedicated MkDocs SQL/C# coverage page is missing.",
        )
        return

    page_text = read_text(MKDOCS_COVERAGE_PAGE)
    required_token_groups = [
        ("SQL Landscape",),
        ("Summary",),
        ("Coverage Matrix",),
        ("Open Gaps",),
        ("Database Table Recommendations",),
        ("Legacy SQL evidence",),
        ("C# evidence",),
        ("Relevant requirements",),
        ("sql-landscape-matrix",),
        ("sql-landscape-recommendations",),
        ("requirements/REQ-",),
    ]
    # Map of alternate label forms (e.g. project-specific labels to their English equivalents).
    # Add entries here if your project uses non-English area labels in the coverage rows.
    english_labels: dict[str, str] = {}
    missing_tokens = [
        " / ".join(tokens)
        for tokens in required_token_groups
        if not any(token in page_text for token in tokens)
    ]
    missing_rows = [
        row.get("area", "")
        for row in rows
        if row.get("area") not in page_text and english_labels.get(row.get("area", "")) not in page_text
    ]
    missing_statuses = [
        status
        for status, count in (overview.get("counts") or {}).items()
        if (status not in page_text and english_labels.get(status, "") not in page_text) or str(count) not in page_text
    ]
    add(
        checks,
        "pass" if not missing_tokens and not missing_rows and not missing_statuses else "fail",
        "Spec overview",
        "MkDocs coverage page mirrors JSON",
        rel(MKDOCS_COVERAGE_PAGE),
        rel(REPORT_JSON),
        (
            "MkDocs SQL/C# coverage page contains the expected sections, statuses, and row labels."
            if not missing_tokens and not missing_rows and not missing_statuses
            else "MkDocs SQL/C# coverage page does not mirror the generated coverage data."
        ),
        missing_tokens=missing_tokens,
        missing_rows=missing_rows,
        missing_statuses=missing_statuses,
    )

    if not MKDOCS_CONFIG.exists():
        add(
            checks,
            "fail",
            "Spec overview",
            "MkDocs nav config exists",
            rel(MKDOCS_CONFIG),
            rel(MKDOCS_COVERAGE_PAGE),
            "MkDocs config is missing.",
        )
        return

    config_text = read_text(MKDOCS_CONFIG)
    coverage_page_filename = Path(MKDOCS_COVERAGE_PAGE_REL).name
    has_nav = coverage_page_filename in config_text
    add(
        checks,
        "pass" if has_nav else "fail",
        "Spec overview",
        "MkDocs coverage page is navigable",
        rel(MKDOCS_CONFIG),
        rel(MKDOCS_COVERAGE_PAGE),
        (
            "MkDocs nav contains the dedicated SQL Landscape page."
            if has_nav
            else "MkDocs nav does not contain the dedicated SQL Landscape page."
        ),
    )


def validate_inventory_counts(checks: list[Check], data: dict[str, Any]) -> None:
    sql_files = data.get("sql_files", [])
    actual_sql_files = sorted(SQL_ROOT.rglob("*.sql"))
    add(
        checks,
        "pass" if len(sql_files) == len(actual_sql_files) else "fail",
        "Inventory",
        "SQL file count",
        rel(SQL_ROOT),
        rel(REPORT_JSON),
        f"Report has {len(sql_files)} SQL files; filesystem has {len(actual_sql_files)}.",
    )

    missing = []
    for item in sql_files:
        path = ROOT / item.get("path", "")
        if not path.exists():
            missing.append(item.get("path", ""))
    add(
        checks,
        "fail" if missing else "pass",
        "Inventory",
        "SQL inventory paths exist",
        rel(SQL_ROOT),
        rel(REPORT_JSON),
        f"Missing inventory paths: {', '.join(missing[:10])}" if missing else "Every SQL inventory path exists.",
        missing_count=len(missing),
    )

    function_sql = [item for item in sql_files if item.get("category") == "Function"]
    function_details = data.get("function_logic", {}).get("details", [])
    add(
        checks,
        "pass" if len(function_sql) == len(function_details) else "fail",
        "Inventory",
        "Function inventory count",
        "SQL category Function",
        rel(REPORT_JSON),
        f"Function SQL files: {len(function_sql)}; function details: {len(function_details)}.",
    )

    category_counts = Counter(item.get("category", "(missing)") for item in sql_files)
    for category, count in sorted(category_counts.items()):
        add(
            checks,
            "pass",
            "Inventory",
            "Category counted",
            category,
            rel(REPORT_JSON),
            f"{count} SQL files classified as {category}.",
            count=count,
        )


def validate_diagrams(checks: list[Check], data: dict[str, Any], html_text: str) -> None:
    diagram_sources = data.get("diagram_sources", [])
    names = {row.get("diagram") for row in diagram_sources}
    expected = {"Core Persistence Hypothesis", "Print Datafile Flow"}
    add(
        checks,
        "pass" if names == expected else "fail",
        "Diagrams",
        "Diagram source rows",
        "diagram_sources",
        rel(REPORT_JSON),
        f"Found diagram source rows: {', '.join(sorted(str(name) for name in names))}.",
    )
    add(
        checks,
        "pass" if "Source Authority And Delivery Flow" not in html_text else "fail",
        "Diagrams",
        "Removed obsolete source-authority diagram",
        "Source Authority And Delivery Flow",
        rel(REPORT_HTML),
        "Source-authority diagram is not rendered in the report." if "Source Authority And Delivery Flow" not in html_text else "Obsolete source-authority diagram is still rendered.",
    )
    mermaid_blocks = [
        html.unescape(block)
        for block in re.findall(r'<pre class="mermaid">(.*?)</pre>', html_text, flags=re.S)
    ]
    sequence_blocks = [block for block in mermaid_blocks if block.lstrip().startswith("sequenceDiagram")]
    participant_lines = [
        line.strip()
        for block in sequence_blocks
        for line in block.splitlines()
        if line.strip().startswith("participant ")
    ]
    unsafe_participants = [
        line
        for line in participant_lines
        if " / " in line or "#" in line or re.search(r"\bas\s+\S+\.\S+", line)
    ]
    longest_sequence_line = max((len(line) for block in sequence_blocks for line in block.splitlines()), default=0)
    sequence_ok = bool(sequence_blocks) and not unsafe_participants and longest_sequence_line <= 140
    add(
        checks,
        "pass" if sequence_ok else "fail",
        "Diagrams",
        "Mermaid sequence syntax guard",
        "SQL function and legacy code sequence diagrams",
        rel(REPORT_HTML),
        f"Found {len(sequence_blocks)} sequence diagrams; longest line is {longest_sequence_line} chars."
        if sequence_ok
        else f"Unsafe sequence participant labels or overly long lines found: {unsafe_participants[:5]}, longest line {longest_sequence_line}.",
        sequence_count=len(sequence_blocks),
        unsafe_participants=unsafe_participants[:10],
        longest_sequence_line=longest_sequence_line,
    )
    function_section = html_text.split("Per-Function Mermaid Flow Diagrams", 1)[-1]
    function_section = function_section.split('<section id="chapter-review"', 1)[0]
    function_mermaid_blocks = [
        html.unescape(block)
        for block in re.findall(r'<pre class="mermaid">(.*?)</pre>', function_section, flags=re.S)
    ]
    expected_function_count = len(data.get("function_logic", {}).get("details", []))
    function_sequence_count = sum(1 for block in function_mermaid_blocks if block.lstrip().startswith("sequenceDiagram"))
    function_flow_count = sum(1 for block in function_mermaid_blocks if block.lstrip().startswith("flowchart"))
    function_flow_node_rx = re.compile(r'^  [A-Za-z][A-Za-z0-9_]*\[".*"\]$')
    function_flow_edge_rx = re.compile(r'^  [A-Za-z][A-Za-z0-9_]*\s+(?:-->|-\.->)(?:\|"[^"]*"\|)?\s+[A-Za-z][A-Za-z0-9_]*$')
    malformed_function_flow_lines: list[str] = []
    for block in function_mermaid_blocks:
        if not block.lstrip().startswith("flowchart"):
            continue
        for line in block.splitlines()[1:]:
            if not (function_flow_node_rx.match(line) or function_flow_edge_rx.match(line)):
                malformed_function_flow_lines.append(line)
                if len(malformed_function_flow_lines) >= 10:
                    break
        if len(malformed_function_flow_lines) >= 10:
            break
    function_flow_ok = (
        function_sequence_count == 0
        and function_flow_count == expected_function_count
        and not malformed_function_flow_lines
    )
    add(
        checks,
        "pass" if function_flow_ok else "fail",
        "Diagrams",
        "Per-function Mermaid flow syntax",
        "Per-Function Mermaid Flow Diagrams",
        rel(REPORT_HTML),
        (
            f"Per-function section renders {function_flow_count} Mermaid flow diagrams and no sequence diagrams."
            if function_flow_ok
            else f"Expected {expected_function_count} well-formed flow diagrams and 0 sequence diagrams; found {function_flow_count} flow and {function_sequence_count} sequence. Malformed lines: {malformed_function_flow_lines[:3]}"
        ),
        expected_function_count=expected_function_count,
        function_flow_count=function_flow_count,
        function_sequence_count=function_sequence_count,
        malformed_function_flow_lines=malformed_function_flow_lines,
    )

    print_row = next((row for row in diagram_sources if row.get("diagram") == "Print Datafile Flow"), None)
    if print_row:
        has_spec_pdf = any(ref.get("pdf", "") in PDF_FILES_CONFIG for ref in print_row.get("pdf_refs", []))
        has_sql = any(str(ref.get("file", "")).startswith(f"legacy-sql/{LEGACY_DB_NAME}") for ref in print_row.get("file_refs", []))
        add(
            checks,
            "pass" if has_spec_pdf and has_sql else "fail",
            "Diagrams",
            "Print flow mixed sources",
            "Print Datafile Flow",
            rel(REPORT_JSON),
            "Print flow cites both spec PDF contract pages and SQL implementation files." if has_spec_pdf and has_sql else "Print flow is missing either spec PDF or SQL evidence.",
        )

    core_text = "this is the likely database save path inferred from SQL files" in html_text
    no_legacy_code_proof = "not production runtime telemetry and does not prove execution frequency" in html_text
    add(
        checks,
        "pass" if core_text and no_legacy_code_proof else "fail",
        "Diagrams",
        "Core flow inference wording",
        "Core Persistence Hypothesis",
        rel(REPORT_HTML),
        "Core persistence diagram is clearly labeled as SQL-inferred, not legacy-code-proven." if core_text and no_legacy_code_proof else "Core persistence diagram does not clearly mark inference limits.",
    )


def validate_products(checks: list[Check], data: dict[str, Any]) -> None:
    rows = data.get("product_sql", [])
    codes = {row.get("code") for row in rows}
    add(
        checks,
        "pass" if codes == EXPECTED_PRODUCT_CODES else "fail",
        "Products",
        "Product code set",
        "product_sql",
        rel(REPORT_JSON),
        f"Found product codes: {', '.join(sorted(str(code) for code in codes))}.",
    )
    primary_pdf_name = next(iter(PDF_FILES_CONFIG), "")
    for row in rows:
        code = row.get("code", "(missing)")
        pdf_refs = row.get("pdf_refs", [])
        has_spec_pdf = any(ref.get("pdf") == primary_pdf_name for ref in pdf_refs)
        has_evidence = bool(row.get("evidence"))
        add(
            checks,
            "pass" if has_spec_pdf else "fail",
            "Products",
            "Spec PDF source",
            str(code),
            rel(REPORT_JSON),
            "Product has spec PDF evidence." if has_spec_pdf else "Product is missing spec PDF evidence.",
        )
        add(
            checks,
            "pass" if has_evidence else "warn",
            "Products",
            "SQL relevance evidence",
            str(code),
            rel(REPORT_JSON),
            "Product has automated SQL relevance evidence." if has_evidence else "Product has no direct SQL relevance evidence; review manually.",
        )


def validate_csharp_backend(checks: list[Check], data: dict[str, Any]) -> None:
    csharp_files = []
    if CSHARP_BACKEND_ROOT.exists():
        csharp_files = [{"path": path, "text": read_text(path)} for path in sorted(CSHARP_BACKEND_ROOT.rglob("*.cs"))]
    all_text = "\n".join(item["text"] for item in csharp_files)
    for row in data.get("csharp_backend", []):
        capability = row.get("capability", "(missing)")
        terms = [str(term) for term in row.get("terms", [])]
        evidence = row.get("evidence", [])
        actual_hits = [term for term in terms if term_present(all_text, [term])]
        if evidence:
            add(
                checks,
                "pass",
                "C# backend",
                "Evidence row present",
                capability,
                rel(REPORT_JSON),
                f"C# comparison row has {len(evidence)} file/line evidence entries.",
            )
        elif actual_hits:
            add(
                checks,
                "fail",
                "C# backend",
                "No-evidence claim",
                capability,
                rel(CSHARP_BACKEND_ROOT),
                f"Report says no evidence, but terms were found in C# backend: {', '.join(actual_hits[:5])}.",
            )
        else:
            add(
                checks,
                "pass",
                "C# backend",
                "No-evidence claim",
                capability,
                rel(CSHARP_BACKEND_ROOT),
                "No matching scan terms were found in C# backend, matching the report row.",
            )


def validate_csharp_sql_model(checks: list[Check], data: dict[str, Any], html_text: str) -> None:
    model = data.get("csharp_sql_model", {})
    add(
        checks,
        "pass" if model else "fail",
        "C# persistence",
        "C# SQL model data present",
        "csharp_sql_model",
        rel(REPORT_JSON),
        "C# SQL/persistence model section is present in report JSON." if model else "C# SQL/persistence model section is missing from report JSON.",
    )
    if not model:
        return

    actual_raw_sql = sorted(rel(path) for path in (ROOT / "csharp").rglob("*.sql")) if (ROOT / "csharp").exists() else []
    reported_raw_sql = sorted(str(path) for path in model.get("raw_sql_files", []))
    add(
        checks,
        "pass" if reported_raw_sql == actual_raw_sql else "fail",
        "C# persistence",
        "Standalone csharp SQL file inventory",
        "csharp_sql_model.raw_sql_files",
        rel(REPORT_JSON),
        f"Report has {len(reported_raw_sql)} standalone .sql files under csharp/; filesystem has {len(actual_raw_sql)}.",
        reported=reported_raw_sql[:10],
        actual=actual_raw_sql[:10],
    )

    schemas = {row.get("schema"): set(row.get("tables", [])) for row in model.get("schemas", [])}
    expected_schema_tables = {
        "auth": {"Roles", "Permissions"},
        "work": {"Lock", "Queue", "ScheduledTask"},
        "dbo/default": {"Orders", "Directives", "Addresses", "Lookups"},
    }
    for schema, expected_tables in expected_schema_tables.items():
        found = schemas.get(schema, set())
        missing = sorted(expected_tables - found)
        add(
            checks,
            "pass" if not missing else "fail",
            "C# persistence",
            "Expected EF schema/table surface",
            schema,
            rel(REPORT_JSON),
            f"Schema {schema} includes expected tables." if not missing else f"Schema {schema} is missing tables: {', '.join(missing)}.",
            found=sorted(found),
        )

    config_rows = model.get("configuration_rows", [])
    actual_config_count = len(list((CSHARP_BACKEND_ROOT / BACKEND_NAMESPACE / "Data" / "Configuration").glob("*.cs")))
    add(
        checks,
        "pass" if len(config_rows) == actual_config_count else "fail",
        "C# persistence",
        "EF configuration count",
        "csharp_sql_model.configuration_rows",
        rel(REPORT_JSON),
        f"Report has {len(config_rows)} EF configuration rows; filesystem has {actual_config_count}.",
    )

    er_diagrams = model.get("er_diagrams", [])
    expected_titles = {
        "C# Directive Order Domain ER Model",
        "C# Directive Catalog And Authorization ER Model",
        "C# Worker Queue ER Model",
    }
    found_titles = {diagram.get("title") for diagram in er_diagrams}
    malformed_sources = [
        diagram.get("title", "(missing)")
        for diagram in er_diagrams
        if not str(diagram.get("mermaid", "")).lstrip().startswith("erDiagram")
    ]
    missing_titles = sorted(expected_titles - found_titles)
    add(
        checks,
        "pass" if not missing_titles and not malformed_sources else "fail",
        "C# persistence",
        "C# domain Mermaid ER diagrams",
        "csharp_sql_model.er_diagrams",
        rel(REPORT_JSON),
        (
            f"Found {len(er_diagrams)} C# Mermaid ER diagrams with expected titles."
            if not missing_titles and not malformed_sources
            else f"Missing titles: {missing_titles}; malformed Mermaid sources: {malformed_sources}."
        ),
        titles=sorted(str(title) for title in found_titles),
    )

    empty_diagrams = [
        diagram.get("title", "(missing)")
        for diagram in er_diagrams
        if not diagram.get("table_count") or not diagram.get("mermaid")
    ]
    add(
        checks,
        "pass" if not empty_diagrams else "fail",
        "C# persistence",
        "C# ER diagram content",
        "csharp_sql_model.er_diagrams",
        rel(REPORT_JSON),
        "Every C# ER diagram has table content and Mermaid source." if not empty_diagrams else f"Empty C# ER diagrams: {empty_diagrams}.",
    )

    legacy_tables = sorted(
        item.get("primary_object")
        for item in data.get("sql_files", [])
        if item.get("category") == "Table" and not item.get("generated")
    )
    coverage_rows = model.get("legacy_table_coverage", [])
    coverage_tables = sorted(row.get("legacy_table") for row in coverage_rows)
    add(
        checks,
        "pass" if coverage_tables == legacy_tables else "fail",
        "C# persistence",
        "Legacy SQL table coverage row count",
        "csharp_sql_model.legacy_table_coverage",
        rel(REPORT_JSON),
        (
            f"Coverage table includes all {len(legacy_tables)} non-generated legacy SQL tables."
            if coverage_tables == legacy_tables
            else "Coverage table does not match non-generated legacy SQL table inventory."
        ),
        missing=sorted(set(legacy_tables) - set(coverage_tables)),
        extra=sorted(set(coverage_tables) - set(legacy_tables)),
    )

    active_csharp_tables: set[str] = set()
    for schema_row in model.get("schemas", []):
        schema = schema_row.get("schema")
        for table_name in schema_row.get("tables", []):
            active_csharp_tables.add(table_name if schema == "dbo/default" else f"{schema}.{table_name}")
    missing_csharp_table_refs = [
        f"{row.get('legacy_table')} -> {table_name}"
        for row in coverage_rows
        for table_name in row.get("csharp_tables", [])
        if table_name not in active_csharp_tables
    ]
    add(
        checks,
        "pass" if not missing_csharp_table_refs else "fail",
        "C# persistence",
        "Legacy coverage C# table references",
        "csharp_sql_model.legacy_table_coverage",
        rel(REPORT_JSON),
        (
            "All mapped C# table names in legacy coverage resolve to active EF migration tables."
            if not missing_csharp_table_refs
            else "Some mapped C# table names do not resolve to active EF migration tables."
        ),
        missing=missing_csharp_table_refs[:20],
    )

    coverage_by_table = {row.get("legacy_table"): row for row in coverage_rows}
    # Configure expected coverage statuses for key legacy tables in your project.
    # Example: {"schema.TableName": "Yes", "schema.OtherTable": "Partial"}
    expected_statuses: dict[str, str] = {}
    wrong_statuses = [
        f"{table_name}: expected {expected_status}, found {coverage_by_table.get(table_name, {}).get('status')}"
        for table_name, expected_status in expected_statuses.items()
        if coverage_by_table.get(table_name, {}).get("status") != expected_status
    ]
    add(
        checks,
        "pass" if not wrong_statuses else "fail",
        "C# persistence",
        "Key legacy table coverage classifications",
        "csharp_sql_model.legacy_table_coverage",
        rel(REPORT_JSON),
        "Key legacy table classifications are present." if not wrong_statuses else "Key legacy table classifications changed unexpectedly.",
        mismatches=wrong_statuses,
    )

    summary_text = normalize(" ".join(row.get("answer", "") for row in model.get("summary", [])))
    has_clear_answer = (
        ("ef core" in summary_text or "entity framework core" in summary_text)
        and "sql server" in summary_text
        and "domain model" in summary_text
    )
    has_html_section = (
        "Existing C# SQL And Persistence Model" in html_text
        and "DirectivesDbContext" in html_text
        and "C# Domain Model ER Diagrams" in html_text
        and "Legacy SQL Tables Already Represented In C#" in html_text
    )
    add(
        checks,
        "pass" if has_clear_answer and has_html_section else "fail",
        "C# persistence",
        "HTML explains C# DB schema and domain model",
        "csharp-sql-model",
        rel(REPORT_HTML),
        "HTML clearly states that C# uses EF Core/SQL Server and has a domain model." if has_clear_answer and has_html_section else "HTML does not clearly explain EF Core/SQL Server and domain-model findings.",
    )


def validate_db_table_recommendations(checks: list[Check], data: dict[str, Any], html_text: str) -> None:
    recommendations = data.get("db_table_recommendations", {})
    rows = recommendations.get("rows", []) if isinstance(recommendations, dict) else []
    coverage_rows = data.get("csharp_sql_model", {}).get("legacy_table_coverage", [])
    overlay = data.get("domain_model_recommendation_er", {})

    def covered(status: str) -> bool:
        normalized_status = normalize(str(status))
        return normalized_status.startswith("yes") or normalized_status.startswith("exact") or normalized_status.startswith("vollstandig")

    expected_tables = {
        row.get("legacy_table")
        for row in coverage_rows
        if row.get("legacy_table") and not covered(row.get("status", ""))
    }
    actual_tables = {row.get("legacy_table") for row in rows if row.get("legacy_table")}
    add(
        checks,
        "pass" if actual_tables == expected_tables else "fail",
        "DB recommendations",
        "Recommendation row scope",
        "db_table_recommendations.rows",
        rel(REPORT_JSON),
        (
            f"Recommendation matrix covers all {len(expected_tables)} partial or missing legacy tables."
            if actual_tables == expected_tables
            else "Recommendation matrix does not match partial/missing legacy-table coverage rows."
        ),
        missing=sorted(expected_tables - actual_tables),
        extra=sorted(actual_tables - expected_tables),
    )

    missing_required_fields = [
        row.get("legacy_table", "<missing>")
        for row in rows
        if not row.get("decision")
        or not row.get("target_model")
        or not row.get("recommendation")
        or not row.get("rationale")
        or not row.get("legacy_evidence")
    ]
    add(
        checks,
        "pass" if not missing_required_fields else "fail",
        "DB recommendations",
        "Recommendation fields populated",
        "db_table_recommendations.rows",
        rel(REPORT_JSON),
        (
            "Every DB recommendation has a decision, target model, recommendation, rationale, and legacy evidence."
            if not missing_required_fields
            else "Some DB recommendations are missing required content."
        ),
        tables=missing_required_fields,
    )

    alternative_wording = []
    alternative_pattern = re.compile(r"(?i)\b(?:oder|or)\b")
    for row in rows:
        combined = " ".join(
            str(row.get(field, ""))
            for field in ("decision", "target_model", "recommendation", "rationale")
        )
        if alternative_pattern.search(combined):
            alternative_wording.append(row.get("legacy_table", "<missing>"))
    add(
        checks,
        "pass" if not alternative_wording else "fail",
        "DB recommendations",
        "Single ACID recommendation wording",
        "db_table_recommendations.rows",
        rel(REPORT_JSON),
        (
            "Every DB recommendation has one target decision without standalone 'oder/or' alternatives."
            if not alternative_wording
            else "Some DB recommendations still contain alternative wording."
        ),
        tables=alternative_wording,
    )

    multi_target_models = [
        row.get("legacy_table", "<missing>")
        for row in rows
        if re.search(r"[,/]|(?i:\b(?:oder|or)\b)", str(row.get("target_model", "")))
    ]
    add(
        checks,
        "pass" if not multi_target_models else "fail",
        "DB recommendations",
        "Single target model per recommendation",
        "db_table_recommendations.rows.target_model",
        rel(REPORT_JSON),
        (
            "Every DB recommendation exposes one target model in the recommendation matrix and ER overlay."
            if not multi_target_models
            else "Some DB recommendations expose multiple target models."
        ),
        tables=multi_target_models,
    )

    mkdocs_text = read_text(MKDOCS_COVERAGE_PAGE) if MKDOCS_COVERAGE_PAGE.exists() else ""
    html_tables_missing = [table for table in actual_tables if table and table not in html_text]
    mkdocs_tables_missing = [table for table in actual_tables if table and table not in mkdocs_text]
    add(
        checks,
        "pass" if not html_tables_missing and not mkdocs_tables_missing else "fail",
        "DB recommendations",
        "Recommendation output rendered",
        "db-table-recommendations",
        f"{rel(REPORT_HTML)}; {rel(MKDOCS_COVERAGE_PAGE)}",
        (
            "All recommendation rows render in the HTML report and SQL Landscape MkDocs page."
            if not html_tables_missing and not mkdocs_tables_missing
            else "Some recommendation rows are missing from generated output."
        ),
        missing_html=html_tables_missing[:20],
        missing_mkdocs=mkdocs_tables_missing[:20],
    )

    broken_requirement_refs = []
    for row in rows:
        for ref in row.get("requirement_refs", []):
            path = ref.get("path")
            if not path or not (ROOT / path).exists():
                broken_requirement_refs.append(f"{row.get('legacy_table')} -> {ref.get('id')} ({path})")
    add(
        checks,
        "pass" if not broken_requirement_refs else "fail",
        "DB recommendations",
        "Requirement links resolve",
        "db_table_recommendations.rows.requirement_refs",
        rel(REPORT_JSON),
        (
            "All requirement links in DB recommendations resolve to local requirement pages."
            if not broken_requirement_refs
            else "Some DB recommendation requirement links do not resolve."
        ),
        broken=broken_requirement_refs[:20],
    )

    rows_without_requirements = [row.get("legacy_table") for row in rows if not row.get("requirement_refs")]
    add(
        checks,
        "pass" if not rows_without_requirements else "warn",
        "DB recommendations",
        "Requirement traceability present where available",
        "db_table_recommendations.rows.requirement_refs",
        rel(REPORT_JSON),
        (
            "Every DB recommendation has at least one requirement link."
            if not rows_without_requirements
            else "Some legacy tables have no direct requirement link; keep them as review items, not implementation commitments."
        ),
        tables=rows_without_requirements,
    )

    current_tables = set(overlay.get("current_tables", [])) if isinstance(overlay, dict) else set()
    recommended_acid_er = data.get("recommended_acid_er_diagrams", {})
    acid_diagrams = recommended_acid_er.get("diagrams", []) if isinstance(recommended_acid_er, dict) else []
    acid_tables = recommended_acid_er.get("tables", []) if isinstance(recommended_acid_er, dict) else []
    acid_relationships = recommended_acid_er.get("relationships", []) if isinstance(recommended_acid_er, dict) else []
    acid_table_names = {row.get("name") for row in acid_tables}
    complete_acid_table_names = set()
    for diagram in acid_diagrams:
        if diagram.get("id") == "complete-acid-er":
            complete_acid_table_names = {row.get("name") for row in diagram.get("tables", [])}
            break
    required_client_csharp_tables = {
        "OrderRoutingPostOfficeBoxes",
        "work.ScheduledTask",
        "OrderOwnerCompanies",
        "work.Lock",
        "OrderRoutingAddresses",
        "OrderOwnerPersons",
        "Lookups",
        "__EFMigrationsHistory",
        "work.Queue",
        "Addresses",
        "ShipmentTypeGroups",
        "ShipmentTypes",
        "Directives",
        "Customers",
        "auth.Permissions",
        "auth.RolePermissions",
        "auth.Roles",
        "CustomerIdentifications",
        "Orders",
        "Companies",
    }
    missing_client_csharp_tables = sorted(required_client_csharp_tables - complete_acid_table_names)
    valid_acid_statuses = {"exists", "extend", "implement"}
    recommended_targets = {
        row.get("target_model")
        for row in rows
        if row.get("target_model") and row.get("target_model") != "NoCSharpDomainTable"
    }
    missing_acid_targets = sorted(target for target in recommended_targets if target not in acid_table_names)
    acid_statuses = {row.get("implementation_status") for row in acid_tables}
    missing_acid_statuses = sorted(valid_acid_statuses - acid_statuses)
    acid_tables_missing_metadata = [
        row.get("name", "<missing>")
        for row in acid_tables
        if row.get("implementation_status") not in valid_acid_statuses or not row.get("entity_id")
    ]
    acid_diagrams_without_columns = [
        diagram.get("title", "<missing>")
        for diagram in acid_diagrams
        if (
            not str(diagram.get("mermaid", "")).lstrip().startswith("erDiagram")
            or " PK" not in str(diagram.get("mermaid", ""))
            or " FK" not in str(diagram.get("mermaid", ""))
            or "||--o{" not in str(diagram.get("mermaid", ""))
            or "STATUS " in str(diagram.get("mermaid", ""))
            or "classDef " in str(diagram.get("mermaid", ""))
            or re.search(r"(?m)^\s*class\s+", str(diagram.get("mermaid", "")))
        )
    ]
    add(
        checks,
        "pass" if acid_diagrams and acid_tables and acid_relationships and not missing_acid_targets and not acid_diagrams_without_columns and not missing_acid_statuses and not acid_tables_missing_metadata and not missing_client_csharp_tables else "fail",
        "DB recommendations",
        "Recommended ACID ER diagrams are concrete",
        "recommended_acid_er_diagrams",
        rel(REPORT_JSON),
        (
            "Recommended ACID ER diagrams contain concrete SQL tables, PK/FK columns, FK relationships, Mermaid-safe ER source, implementation-status metadata, and every client-confirmed current C# table in the complete diagram."
            if acid_diagrams and acid_tables and acid_relationships and not missing_acid_targets and not acid_diagrams_without_columns and not missing_acid_statuses and not acid_tables_missing_metadata and not missing_client_csharp_tables
            else "Recommended ACID ER diagrams are missing concrete tables, PK/FK columns, relationships, Mermaid-safe ER source, implementation-status metadata, target-model coverage, or client-confirmed current C# tables."
        ),
        missing_targets=missing_acid_targets,
        missing_client_csharp_tables=missing_client_csharp_tables,
        missing_statuses=missing_acid_statuses,
        invalid_diagrams=acid_diagrams_without_columns,
        tables_missing_metadata=acid_tables_missing_metadata,
        table_count=len(acid_tables),
        relationship_count=len(acid_relationships),
    )

    acid_html_tokens = [
        "Recommended ACID Target Model: Complete And Focused ER Diagrams",
        "Complete ACID Target Model",
        "SQL Target Tables",
        "FK Relationships",
        "Mermaid source for the ACID ER diagram",
        "Lookups",
        "OrderRoutingPostOfficeBoxes",
        "work.ScheduledTask",
        "__EFMigrationsHistory",
        "BillingRecords",
        "PostOfficeBoxes",
        "BatchImports",
        "Exists in C#",
        "Extend existing C# table",
        "Implement new table",
        "acid-status-exists",
        "acid-status-extend",
        "acid-status-implement",
        "acid-er-status-data",
        "applyAcidErStatusColors",
    ]
    missing_acid_html_tokens = [token for token in acid_html_tokens if token not in html_text]
    add(
        checks,
        "pass" if not missing_acid_html_tokens else "fail",
        "DB recommendations",
        "Recommended ACID ER diagrams rendered in HTML",
        "db-table-recommendations",
        rel(REPORT_HTML),
        (
            "HTML renders the recommended ACID ER diagrams and table/relationship inventory."
            if not missing_acid_html_tokens
            else "HTML is missing the recommended ACID ER diagram section or key target tables."
        ),
        missing=missing_acid_html_tokens,
    )

    active_csharp_tables: set[str] = set()
    for schema_row in data.get("csharp_sql_model", {}).get("schemas", []):
        schema = schema_row.get("schema")
        for table_name in schema_row.get("tables", []):
            active_csharp_tables.add(table_name if schema == "dbo/default" else f"{schema}.{table_name}")
    recommendation_nodes = overlay.get("recommendation_nodes", []) if isinstance(overlay, dict) else []
    mermaid = overlay.get("mermaid", "") if isinstance(overlay, dict) else ""
    required_mermaid_tokens = ["flowchart", "classDef current", "classDef recommended", "classDef notRecommended"]
    missing_mermaid_tokens = [token for token in required_mermaid_tokens if token not in mermaid]
    add(
        checks,
        "pass" if current_tables == active_csharp_tables and len(recommendation_nodes) == len(rows) and not missing_mermaid_tokens else "fail",
        "DB recommendations",
        "Combined C# plus recommendation ER overlay",
        "domain_model_recommendation_er",
        rel(REPORT_JSON),
        (
            "Combined domain overlay includes all active C# tables, every recommendation row, and styled Mermaid classes."
            if current_tables == active_csharp_tables and len(recommendation_nodes) == len(rows) and not missing_mermaid_tokens
            else "Combined domain overlay is incomplete or missing Mermaid styling."
        ),
        missing_current_tables=sorted(active_csharp_tables - current_tables),
        extra_current_tables=sorted(current_tables - active_csharp_tables),
        recommendation_nodes=len(recommendation_nodes),
        recommendation_rows=len(rows),
        missing_mermaid_tokens=missing_mermaid_tokens,
    )

    overlay_html_tokens = [
        "Domain Model Overlay",
        "classDef current",
        "classDef recommended",
        "classDef notRecommended",
        "Mermaid source",
    ]
    missing_overlay_html = [token for token in overlay_html_tokens if token not in html_text]
    add(
        checks,
        "pass" if not missing_overlay_html else "fail",
        "DB recommendations",
        "Combined ER overlay rendered in HTML",
        "db-table-recommendations",
        rel(REPORT_HTML),
        (
            "HTML renders the combined current-C# plus recommendation domain overlay with border-color legend."
            if not missing_overlay_html
            else "HTML is missing the combined domain overlay or its legend."
        ),
        missing=missing_overlay_html,
    )


def validate_function_logic(checks: list[Check], data: dict[str, Any]) -> None:
    sql_functions = {
        item.get("primary_object")
        for item in data.get("sql_files", [])
        if item.get("category") == "Function"
    }
    details = data.get("function_logic", {}).get("details", [])
    detail_objects = [item.get("object") for item in details]
    detail_set = set(detail_objects)
    duplicates = [obj for obj, count in Counter(detail_objects).items() if count > 1]
    missing = sorted(str(obj) for obj in sql_functions - detail_set)
    extra = sorted(str(obj) for obj in detail_set - sql_functions)

    status = "pass" if not duplicates and not missing and not extra else "fail"
    message = "Every SQL function appears exactly once in function detail rows."
    if status == "fail":
        message = f"Duplicates: {duplicates[:10]}; missing: {missing[:10]}; extra: {extra[:10]}."
    add(checks, status, "SQL functions", "One detail per SQL function", "function_logic.details", rel(REPORT_JSON), message)

    grouped_functions = []
    for group in data.get("function_logic", {}).get("groups", []):
        grouped_functions.extend(group.get("functions", []))
    group_duplicates = [obj for obj, count in Counter(grouped_functions).items() if count > 1]
    group_missing = sorted(str(obj) for obj in sql_functions - set(grouped_functions))
    group_status = "pass" if not group_duplicates and not group_missing else "fail"
    group_message = "Every SQL function appears in exactly one function group."
    if group_status == "fail":
        group_message = f"Group duplicates: {group_duplicates[:10]}; group missing: {group_missing[:10]}."
    add(checks, group_status, "SQL functions", "One group per SQL function", "function_logic.groups", rel(REPORT_JSON), group_message)

    for row in details:
        subject = str(row.get("object", "(missing)"))
        source_refs = row.get("source_refs", [])
        add(
            checks,
            "pass" if source_refs else "fail",
            "SQL functions",
            "Function source line",
            subject,
            rel(REPORT_JSON),
            "Function detail has a source line." if source_refs else "Function detail is missing source_refs.",
        )
        business_text = " ".join(str(row.get(key, "")) for key in ("business_logic", "comment", "return_shape"))
        n_business = normalize(business_text)
        if "legacy code" in n_business and not any(word in n_business for word in SAFE_LEGACY_CODE_WORDS):
            add(
                checks,
                "warn",
                "SQL functions",
                "Legacy code usage claim",
                subject,
                rel(REPORT_JSON),
                "Function text mentions legacy code without explicit uncertainty wording.",
            )


def validate_legacy_code(checks: list[Check], data: dict[str, Any], html_text: str) -> None:
    legacy_code = data.get("legacy_code", {})
    add(
        checks,
        "pass" if legacy_code.get("exists") else "fail",
        "Legacy code",
        "Source root exists",
        legacy_code.get("root", "to_be_migrated_repo/"),
        rel(REPORT_JSON),
        "Legacy code source root is present." if legacy_code.get("exists") else "Legacy code source root is missing.",
    )
    add(
        checks,
        "pass" if legacy_code.get("files_scanned", 0) > 0 else "fail",
        "Legacy code",
        "Files scanned",
        legacy_code.get("root", "to_be_migrated_repo/"),
        rel(REPORT_JSON),
        f"Scanned {legacy_code.get('files_scanned', 0)} legacy code files.",
        count=legacy_code.get("files_scanned", 0),
    )
    add(
        checks,
        "pass" if legacy_code.get("datasource") else "warn",
        "Legacy code",
        "Datasource evidence",
        legacy_code.get("datasource", "unknown"),
        rel(REPORT_JSON),
        "Datasource assignment was extracted from Application.cfc." if legacy_code.get("datasource") else "Datasource assignment was not extracted.",
    )
    add(
        checks,
        "pass" if legacy_code.get("files_with_sql_hits", 0) > 0 and legacy_code.get("distinct_sql_objects_hit", 0) > 0 else "fail",
        "Legacy code",
        "Imported SQL object references",
        "static scan",
        rel(REPORT_JSON),
        f"{legacy_code.get('files_with_sql_hits', 0)} files reference {legacy_code.get('distinct_sql_objects_hit', 0)} imported SQL objects.",
    )
    add(
        checks,
        "pass" if legacy_code.get("matched_stored_proc_calls", 0) > 0 else "fail",
        "Legacy code",
        "Stored procedure matches",
        "cfstoredproc",
        rel(REPORT_JSON),
        f"{legacy_code.get('matched_stored_proc_calls', 0)} cfstoredproc calls match imported SQL objects.",
    )
    if legacy_code.get("unmatched_stored_proc_calls", 0):
        add(
            checks,
            "warn",
            "Legacy code",
            "Unmatched stored procedure calls",
            "cfstoredproc",
            rel(REPORT_JSON),
            f"{legacy_code.get('unmatched_stored_proc_calls', 0)} cfstoredproc calls do not match the imported SQL snapshot.",
        )
    top_objects = {row.get("object") for row in legacy_code.get("top_objects", [])}
    # Configure the core table/procedure names your project expects in the legacy code top-objects scan.
    expected_objects: set[str] = set()
    add(
        checks,
        "pass" if not expected_objects or expected_objects <= top_objects else "warn",
        "Legacy code",
        "Expected core references",
        "top_objects",
        rel(REPORT_JSON),
        "Legacy code scan includes expected core table/procedure references." if not expected_objects or expected_objects <= top_objects else f"Missing expected core references from top objects: {sorted(expected_objects - top_objects)}.",
    )
    add(
        checks,
        "pass" if "Legacy Code Static SQL Call-Site Evidence" in html_text else "fail",
        "Legacy code",
        "HTML section rendered",
        "Legacy Code Static SQL Call-Site Evidence",
        rel(REPORT_HTML),
        "Legacy code evidence section is present in the report." if "Legacy Code Static SQL Call-Site Evidence" in html_text else "Legacy code evidence section is missing from the report.",
    )


def validate_inference_warnings(checks: list[Check], html_text: str) -> None:
    expected_phrases = [
        "not production runtime telemetry",
        "does not prove execution frequency",
        "SQL relevance is an automated term-based scan and should be reviewed manually",
        "It is evidence of implementation surface, not a full behavioral parity proof.",
        "Legacy code call-site evidence is summarized separately",
    ]
    for phrase in expected_phrases:
        found = phrase in html_text
        add(
            checks,
            "pass" if found else "warn",
            "Inference limits",
            "Uncertainty wording present",
            compact(phrase, 80),
            rel(REPORT_HTML),
            "Expected uncertainty wording is present." if found else "Expected uncertainty wording is missing or changed.",
        )


def run_git(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(cwd), text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def render_validation_html(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    counts = payload["counts"]
    generated_at = payload["generated_at"]
    rows = []
    for check in checks:
        evidence = check.get("evidence") or {}
        evidence_text = html_escape(json.dumps(evidence, ensure_ascii=False, sort_keys=True)) if evidence else ""
        search = " ".join(str(check.get(key, "")) for key in ("status", "area", "check", "subject", "source", "message"))
        rows.append(
            "<tr class=\"search-item {}\" data-search=\"{}\">"
            "<td><span class=\"status {}\">{}</span></td>"
            "<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}<br><span class=\"muted\">{}</span></td>"
            "</tr>".format(
                html_escape(check["status"]),
                html_escape(search),
                html_escape(check["status"]),
                html_escape(check["status"].upper()),
                html_escape(check["area"]),
                html_escape(check["check"]),
                html_escape(check["subject"]),
                html_escape(check["source"]),
                html_escape(check["message"]),
                evidence_text,
            )
        )
    table_rows = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Legacy SQL Analysis Validation</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d9dee7;
      --pass: #0f766e;
      --warn: #b45309;
      --fail: #b42318;
      --soft: #eef2f7;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); line-height: 1.45; }}
    header {{ background: #1d2939; color: white; padding: 26px 32px 18px; }}
    header h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }}
    header p {{ margin: 0; color: #d7dce5; max-width: 1120px; }}
    nav {{ position: sticky; top: 0; z-index: 5; background: rgba(255,255,255,.96); border-bottom: 1px solid var(--line); padding: 12px 32px; display: flex; gap: 12px; flex-wrap: wrap; }}
    #search {{ min-width: 280px; max-width: 620px; flex: 1; padding: 10px 12px; border: 1px solid var(--line); border-radius: 6px; font-size: 15px; }}
    main {{ padding: 24px 32px 56px; max-width: 1500px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .metric {{ font-size: 30px; font-weight: 750; }}
    .muted {{ color: var(--muted); font-size: 12px; }}
    .table-wrap {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1100px; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: var(--soft); text-transform: uppercase; font-size: 12px; letter-spacing: .04em; }}
    .status {{ display: inline-block; border-radius: 5px; padding: 2px 7px; color: white; font-size: 12px; font-weight: 700; }}
    .status.pass {{ background: var(--pass); }}
    .status.warn {{ background: var(--warn); }}
    .status.fail {{ background: var(--fail); }}
    tr.pass td {{ background: #f8fffd; }}
    tr.warn td {{ background: #fffaf0; }}
    tr.fail td {{ background: #fff5f5; }}
    .hidden-by-search {{ display: none !important; }}
  </style>
</head>
<body>
  <header>
    <h1>Legacy SQL Analysis Validation</h1>
    <p>Generated {html_escape(generated_at)}. This issue matrix validates the generated analysis report against PDFs, SQL files, C# files, and report JSON. Warnings mark inferred or semantic evidence that needs human review.</p>
  </header>
  <nav>
    <input id="search" type="search" placeholder="Search validation: status, area, source, message...">
  </nav>
  <main>
    <section class="grid">
      <div class="card"><div class="metric">{counts.get("pass", 0)}</div><strong>Pass</strong></div>
      <div class="card"><div class="metric">{counts.get("warn", 0)}</div><strong>Warn</strong></div>
      <div class="card"><div class="metric">{counts.get("fail", 0)}</div><strong>Fail</strong></div>
      <div class="card"><div class="metric">{len(checks)}</div><strong>Total Checks</strong></div>
    </section>
    <section class="table-wrap">
      <table>
        <thead><tr><th>Status</th><th>Area</th><th>Check</th><th>Subject</th><th>Source</th><th>Message / Evidence</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </section>
  </main>
  <script>
    const search = document.getElementById('search');
    function matchesText(el, q) {{
      if (!q) return true;
      const haystack = (el.dataset.search || el.textContent).toLowerCase();
      return q.split(/\\s+/).every(part => haystack.includes(part));
    }}
    function applySearch() {{
      const q = search.value.trim().toLowerCase();
      document.querySelectorAll('.search-item').forEach(el => {{
        el.classList.toggle('hidden-by-search', !matchesText(el, q));
      }});
    }}
    search.addEventListener('input', applySearch);
  </script>
</body>
</html>"""


def serializable_payload(checks: list[Check]) -> dict[str, Any]:
    counts = Counter(check.status for check in checks)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "report_html": rel(REPORT_HTML),
            "report_json": rel(REPORT_JSON),
            "mkdocs_coverage_page": rel(MKDOCS_COVERAGE_PAGE),
            "mkdocs_config": rel(MKDOCS_CONFIG),
            "sql_root": rel(SQL_ROOT),
            "csharp_backend_root": rel(CSHARP_BACKEND_ROOT),
            "pdfs": {name: rel(path) for name, path in PDF_FILES.items()},
            "sql_git_commit": run_git(["rev-parse", "HEAD"], SQL_ROOT),
        },
        "counts": dict(counts),
        "checks": [asdict(check) for check in checks],
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[Check] = []
    data = load_json_report(checks)
    html_text, parser = load_html_report(checks)
    pdf_pages = load_pdf_pages(checks)
    if data and html_text:
        validate_structure(checks, data, html_text, parser)
        validate_pdf_refs(checks, data, pdf_pages)
        validate_file_refs(checks, data)
        validate_spec_coverage_overview(checks, data, html_text)
        validate_mkdocs_spec_coverage_page(checks, data)
        validate_inventory_counts(checks, data)
        validate_diagrams(checks, data, html_text)
        validate_products(checks, data)
        validate_csharp_backend(checks, data)
        validate_csharp_sql_model(checks, data, html_text)
        validate_db_table_recommendations(checks, data, html_text)
        validate_function_logic(checks, data)
        validate_legacy_code(checks, data, html_text)
        validate_inference_warnings(checks, html_text)

    payload = serializable_payload(checks)
    VALIDATION_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    VALIDATION_HTML.write_text(render_validation_html(payload), encoding="utf-8")
    print(f"Wrote {rel(VALIDATION_HTML)}")
    print(f"Wrote {rel(VALIDATION_JSON)}")
    print(
        "Validation checks: "
        + ", ".join(f"{status}={payload['counts'].get(status, 0)}" for status in ("pass", "warn", "fail"))
    )
    return 1 if payload["counts"].get("fail", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
