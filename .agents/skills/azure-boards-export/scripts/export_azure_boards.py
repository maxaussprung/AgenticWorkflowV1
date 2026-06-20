#!/usr/bin/env python3
"""Export Azure DevOps board/backlog work items to Markdown."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import posixpath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


# ===== PROJECT CONFIGURATION =====
# Replace these placeholders before running the script, or supply them via
# CLI arguments and environment variables documented in parse_args() below.
#
# AZURE_DEVOPS_ORG     - Azure DevOps organization name
#                        e.g. "myorg" from https://dev.azure.com/myorg/
# AZURE_DEVOPS_PROJECT - Azure DevOps project name
#                        e.g. "MyProject" from https://dev.azure.com/myorg/MyProject/
# PROJECT_SLUG         - Short slug used in output paths and the User-Agent header
#                        e.g. "my-project"
#
# The recommended approach is to pass the board URL as a CLI argument and set
# AZURE_DEVOPS_BEARER_TOKEN (or use --token-file / --auth pat with a PAT) so
# that no credentials appear in source code.
# ==================================

DEFAULT_API_VERSION = "7.1"
DEFAULT_TOKEN_ENV = "AZURE_DEVOPS_BEARER_TOKEN"
MAX_BATCH_SIZE = 200

CORE_FIELD_ORDER = [
    "System.WorkItemType",
    "System.State",
    "System.Reason",
    "System.AssignedTo",
    "System.AreaPath",
    "System.IterationPath",
    "System.Tags",
    "Microsoft.VSTS.Common.Priority",
    "Microsoft.VSTS.Scheduling.Effort",
    "Microsoft.VSTS.Scheduling.StoryPoints",
    "Microsoft.VSTS.Common.BusinessValue",
    "Microsoft.VSTS.Common.ValueArea",
    "System.CreatedBy",
    "System.CreatedDate",
    "System.ChangedBy",
    "System.ChangedDate",
]

HTML_FIELD_ORDER = [
    "System.Description",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
    "Microsoft.VSTS.TCM.ReproSteps",
    "Microsoft.VSTS.Common.SystemInfo",
]

FIELD_LABELS = {
    "System.Id": "ID",
    "System.Title": "Title",
    "System.WorkItemType": "Type",
    "System.State": "State",
    "System.Reason": "Reason",
    "System.AssignedTo": "Assigned To",
    "System.AreaPath": "Area Path",
    "System.IterationPath": "Iteration Path",
    "System.Tags": "Tags",
    "System.CreatedBy": "Created By",
    "System.CreatedDate": "Created",
    "System.ChangedBy": "Changed By",
    "System.ChangedDate": "Changed",
    "System.Description": "Description",
    "Microsoft.VSTS.Common.AcceptanceCriteria": "Acceptance Criteria",
    "Microsoft.VSTS.TCM.ReproSteps": "Repro Steps",
    "Microsoft.VSTS.Common.SystemInfo": "System Info",
    "Microsoft.VSTS.Common.Priority": "Priority",
    "Microsoft.VSTS.Scheduling.Effort": "Effort",
    "Microsoft.VSTS.Scheduling.StoryPoints": "Story Points",
    "Microsoft.VSTS.Common.BusinessValue": "Business Value",
    "Microsoft.VSTS.Common.ValueArea": "Value Area",
}

IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
}

HTML_IMG_SRC_RE = re.compile(
    r"(<img\b[^>]*?\bsrc\s*=\s*[\"'])([^\"']+)([\"'][^>]*>)",
    re.IGNORECASE | re.DOTALL,
)


class AzureDevOpsError(RuntimeError):
    """Raised for Azure DevOps API failures."""


class BoardContext:
    def __init__(
        self,
        organization: str,
        project: str,
        team: str | None,
        board_name: str | None,
        source_url: str,
    ) -> None:
        self.organization = organization
        self.project = project
        self.team = team
        self.board_name = board_name
        self.source_url = source_url

    @property
    def web_base(self) -> str:
        return "https://dev.azure.com/{}/{}".format(
            quote_segment(self.organization), quote_segment(self.project)
        )

    def work_item_url(self, work_item_id: int | str) -> str:
        return f"{self.web_base}/_workitems/edit/{work_item_id}"


class AzureClient:
    def __init__(
        self,
        token: str,
        auth: str,
        api_version: str,
        timeout: int,
        retries: int,
        verbose: bool = False,
    ) -> None:
        self.token = token
        self.auth = auth
        self.api_version = api_version
        self.timeout = timeout
        self.retries = retries
        self.verbose = verbose

    def request_json(self, method: str, url: str, body: dict[str, Any] | None = None) -> Any:
        data, headers = self._prepare_request(body, accept="application/json")
        raw, _headers = self._request(method, url, data, headers)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AzureDevOpsError(f"Expected JSON from {url}, but response was not JSON") from exc

    def download_bytes(self, url: str) -> tuple[bytes, str | None, str | None]:
        headers = self._auth_headers()
        headers["Accept"] = "application/octet-stream,*/*"
        raw, response_headers = self._request("GET", url, None, headers)
        content_type = response_headers.get("Content-Type")
        filename = filename_from_content_disposition(response_headers.get("Content-Disposition"))
        return raw, content_type, filename

    def _prepare_request(
        self, body: dict[str, Any] | None, accept: str
    ) -> tuple[bytes | None, dict[str, str]]:
        headers = self._auth_headers()
        headers["Accept"] = accept
        if body is None:
            return None, headers
        headers["Content-Type"] = "application/json"
        return json.dumps(body).encode("utf-8"), headers

    def _auth_headers(self) -> dict[str, str]:
        if self.auth == "pat":
            encoded = base64.b64encode(f":{self.token}".encode("utf-8")).decode("ascii")
            authorization = f"Basic {encoded}"
        else:
            authorization = f"Bearer {self.token}"
        return {
            "Authorization": authorization,
            "User-Agent": "{project}-azure-boards-export/1.0",
        }

    def _request(
        self,
        method: str,
        url: str,
        data: bytes | None,
        headers: dict[str, str],
    ) -> tuple[bytes, dict[str, str]]:
        for attempt in range(self.retries + 1):
            if self.verbose:
                print(f"{method} {redact_query(url)}", file=sys.stderr)
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read(), dict(response.headers.items())
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    retry_after = parse_retry_after(exc.headers.get("Retry-After"))
                    time.sleep(retry_after if retry_after is not None else 2**attempt)
                    continue
                message = body.strip()[:2000] or exc.reason
                raise AzureDevOpsError(
                    f"{method} {redact_query(url)} failed with HTTP {exc.code}: {message}"
                ) from exc
            except urllib.error.URLError as exc:
                if attempt < self.retries:
                    time.sleep(2**attempt)
                    continue
                raise AzureDevOpsError(f"{method} {redact_query(url)} failed: {exc}") from exc
        raise AzureDevOpsError(f"{method} {redact_query(url)} failed after retries")


class MarkdownHTMLConverter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.href_stack: list[str | None] = []
        self.list_stack: list[dict[str, Any]] = []
        self.in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name.lower(): value or "" for name, value in attrs}
        tag = tag.lower()
        if tag in {"p", "div", "section", "article"}:
            self.blank_line()
        elif tag == "br":
            self.parts.append("\n")
        elif tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "code" and not self.in_pre:
            self.parts.append("`")
        elif tag == "pre":
            self.blank_line()
            self.parts.append("```\n")
            self.in_pre = True
        elif tag == "a":
            href = attrs_dict.get("href")
            self.href_stack.append(href)
            if href:
                self.parts.append("[")
        elif tag == "img":
            src = attrs_dict.get("src", "")
            alt = attrs_dict.get("alt", "")
            if src:
                self.parts.append(f"![{escape_markdown_inline(alt)}]({src})")
        elif tag in {"ul", "ol"}:
            self.blank_line()
            self.list_stack.append({"tag": tag, "index": 1})
        elif tag == "li":
            self.new_line()
            indent = "  " * max(len(self.list_stack) - 1, 0)
            if self.list_stack and self.list_stack[-1]["tag"] == "ol":
                index = self.list_stack[-1]["index"]
                self.list_stack[-1]["index"] += 1
                self.parts.append(f"{indent}{index}. ")
            else:
                self.parts.append(f"{indent}- ")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self.blank_line()
            self.parts.append("#" * min(level + 1, 6) + " ")
        elif tag == "blockquote":
            self.blank_line()
            self.parts.append("> ")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")
        elif tag == "tr":
            self.new_line()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"strong", "b"}:
            self.parts.append("**")
        elif tag in {"em", "i"}:
            self.parts.append("*")
        elif tag == "code" and not self.in_pre:
            self.parts.append("`")
        elif tag == "pre":
            if not self.current_text().endswith("\n"):
                self.parts.append("\n")
            self.parts.append("```")
            self.in_pre = False
            self.blank_line()
        elif tag == "a":
            href = self.href_stack.pop() if self.href_stack else None
            if href:
                self.parts.append(f"]({href})")
        elif tag in {"p", "div", "section", "article", "blockquote"}:
            self.blank_line()
        elif tag in {"ul", "ol"}:
            if self.list_stack:
                self.list_stack.pop()
            self.blank_line()
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.blank_line()
        elif tag == "tr":
            self.new_line()

    def handle_data(self, data: str) -> None:
        if self.in_pre:
            self.parts.append(data)
            return
        text = re.sub(r"\s+", " ", data)
        if not text.strip():
            return
        self.append_text(text)

    def blank_line(self) -> None:
        text = self.current_text().rstrip()
        self.parts = [text]
        if text and not text.endswith("\n\n"):
            self.parts.append("\n\n")

    def new_line(self) -> None:
        text = self.current_text().rstrip()
        self.parts = [text]
        if text and not text.endswith("\n"):
            self.parts.append("\n")

    def append_text(self, text: str) -> None:
        if (
            self.parts
            and self.parts[-1]
            and not self.parts[-1].endswith((" ", "\n", "[", "(", "`"))
            and not text.startswith((" ", ".", ",", ";", ":", "!", "?", ")", "]"))
        ):
            self.parts.append(" ")
        self.parts.append(text)

    def current_text(self) -> str:
        return "".join(self.parts)

    def markdown(self) -> str:
        text = self.current_text()
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def main() -> int:
    args = parse_args()
    try:
        token = read_token(args)
        context = parse_board_url(args.board_url)
        backlog_name = args.backlog_name or context.board_name
        output_dir = Path(args.output_dir) if args.output_dir else default_output_dir(context, backlog_name)
        output_dir.mkdir(parents=True, exist_ok=True)

        client = AzureClient(
            token=token,
            auth=args.auth,
            api_version=args.api_version,
            timeout=args.timeout,
            retries=args.retries,
            verbose=args.verbose,
        )

        if args.list_backlogs:
            for backlog in list_backlogs(client, context):
                print("{}\t{}".format(backlog.get("id", ""), backlog.get("name", "")))
            return 0

        backlog_id = args.backlog_id or resolve_backlog_id(client, context, backlog_name)
        work_item_ids = get_backlog_work_item_ids(client, context, backlog_id)
        if not work_item_ids:
            print("No work items found for backlog.", file=sys.stderr)
            return 0

        items = fetch_work_items(client, context, work_item_ids, expand_relations=True)
        related_lookup = fetch_related_work_items(client, context, items)
        written_files: list[Path] = []
        for item in items:
            markdown_path = render_work_item(
                item=item,
                context=context,
                client=client,
                output_dir=output_dir,
                related_lookup=related_lookup,
                skip_attachments=args.skip_attachments,
            )
            written_files.append(markdown_path)

        if not args.no_index:
            write_index(output_dir, context, backlog_id, items, written_files)

        print(f"Exported {len(written_files)} work items to {output_dir}")
        return 0
    except (AzureDevOpsError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Azure DevOps board/backlog work items to Markdown files."
    )
    parser.add_argument("board_url", help="Azure DevOps board/backlog URL")
    parser.add_argument(
        "--output-dir",
        help="Directory for Markdown and attachments. Defaults to reports/evaluations/azure-boards/<board-slug>.",
    )
    parser.add_argument(
        "--token-env",
        default=DEFAULT_TOKEN_ENV,
        help=f"Environment variable containing the token. Default: {DEFAULT_TOKEN_ENV}.",
    )
    parser.add_argument("--token-file", help="File containing the token.")
    parser.add_argument(
        "--auth",
        choices=["bearer", "pat"],
        default="bearer",
        help="Use bearer token auth or PAT basic auth. Default: bearer.",
    )
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--backlog-id", help="Exact Azure DevOps backlog id to export.")
    parser.add_argument("--backlog-name", help="Backlog name to resolve instead of URL final segment.")
    parser.add_argument(
        "--list-backlogs",
        action="store_true",
        help="List available backlog ids/names for the parsed team and exit.",
    )
    parser.add_argument("--skip-attachments", action="store_true", help="Do not download attachments/images.")
    parser.add_argument("--no-index", action="store_true", help="Do not write _index.md.")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Retries for transient HTTP failures.")
    parser.add_argument("--verbose", action="store_true", help="Log API requests without token values.")
    return parser.parse_args()


def read_token(args: argparse.Namespace) -> str:
    token = os.environ.get(args.token_env, "").strip()
    if not token and args.token_file:
        token = Path(args.token_file).read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"set {args.token_env} or pass --token-file")
    return token


def parse_board_url(board_url: str) -> BoardContext:
    parsed = urllib.parse.urlparse(board_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("board_url must be an absolute Azure DevOps URL")

    raw_parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    organization: str
    project: str
    remaining: list[str]

    if parsed.netloc.lower() == "dev.azure.com":
        if len(raw_parts) < 2:
            raise ValueError("dev.azure.com URL must include organization and project")
        organization, project = raw_parts[0], raw_parts[1]
        remaining = raw_parts[2:]
    elif parsed.netloc.lower().endswith(".visualstudio.com"):
        organization = parsed.netloc.split(".", 1)[0]
        if not raw_parts:
            raise ValueError("visualstudio.com URL must include project")
        project = raw_parts[0]
        remaining = raw_parts[1:]
    else:
        raise ValueError("URL host must be dev.azure.com or *.visualstudio.com")

    team = None
    board_name = None
    if "_boards" in remaining:
        try:
            marker = remaining.index("t")
            team = remaining[marker + 1]
            board_name = remaining[marker + 2] if len(remaining) > marker + 2 else None
        except (ValueError, IndexError):
            pass

    return BoardContext(
        organization=organization,
        project=project,
        team=team,
        board_name=board_name,
        source_url=board_url,
    )


def list_backlogs(client: AzureClient, context: BoardContext) -> list[dict[str, Any]]:
    ensure_team(context)
    payload = client.request_json("GET", work_api_url(client, context, ["backlogs"]))
    return payload.get("value", [])


def resolve_backlog_id(client: AzureClient, context: BoardContext, backlog_name: str | None) -> str:
    if not backlog_name:
        raise ValueError("could not infer backlog name from URL; pass --backlog-id or --backlog-name")
    candidates = list_backlogs(client, context)
    normalized = normalize_key(backlog_name)
    for backlog in candidates:
        for key in ("id", "name"):
            value = str(backlog.get(key, ""))
            if normalize_key(value) == normalized:
                return value
    available = ", ".join(
        "{} ({})".format(backlog.get("name", ""), backlog.get("id", "")) for backlog in candidates
    )
    raise ValueError(
        f"could not resolve backlog '{backlog_name}'. Available backlogs: {available or 'none'}"
    )


def get_backlog_work_item_ids(client: AzureClient, context: BoardContext, backlog_id: str) -> list[int]:
    payload = client.request_json(
        "GET", work_api_url(client, context, ["backlogs", backlog_id, "workItems"])
    )
    ids: list[int] = []
    seen: set[int] = set()
    for item_id in extract_ids_from_payload(payload):
        if item_id not in seen:
            ids.append(item_id)
            seen.add(item_id)
    return ids


def extract_ids_from_payload(payload: Any) -> list[int]:
    ids: list[int] = []
    if isinstance(payload, dict):
        for key in ("workItems", "value"):
            value = payload.get(key)
            if isinstance(value, list):
                ids.extend(extract_ids_from_payload(value))
        if isinstance(payload.get("id"), int):
            ids.append(payload["id"])
        target = payload.get("target")
        if isinstance(target, dict) and isinstance(target.get("id"), int):
            ids.append(target["id"])
        url = payload.get("url")
        if isinstance(url, str):
            parsed_id = relation_work_item_id(url)
            if parsed_id is not None:
                ids.append(parsed_id)
    elif isinstance(payload, list):
        for value in payload:
            ids.extend(extract_ids_from_payload(value))
    return ids


def fetch_work_items(
    client: AzureClient,
    context: BoardContext,
    ids: list[int],
    expand_relations: bool,
    fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    items_by_id: dict[int, dict[str, Any]] = {}
    for chunk in chunks(ids, MAX_BATCH_SIZE):
        body: dict[str, Any] = {"ids": chunk, "errorPolicy": "Omit"}
        if expand_relations:
            body["$expand"] = "Relations"
        if fields:
            body["fields"] = fields
        payload = client.request_json("POST", wit_api_url(client, context, ["workitemsbatch"]), body)
        for item in payload.get("value", []):
            item_id = item.get("id")
            if isinstance(item_id, int):
                items_by_id[item_id] = item
    return [items_by_id[item_id] for item_id in ids if item_id in items_by_id]


def fetch_related_work_items(
    client: AzureClient, context: BoardContext, items: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    related_ids: set[int] = set()
    current_ids = {item.get("id") for item in items}
    for item in items:
        for relation in item.get("relations", []) or []:
            related_id = relation_work_item_id(relation.get("url", ""))
            if related_id is not None and related_id not in current_ids:
                related_ids.add(related_id)
    if not related_ids:
        return {}
    fields = ["System.Id", "System.Title", "System.WorkItemType", "System.State"]
    related_items = fetch_work_items(client, context, sorted(related_ids), False, fields=fields)
    return {item["id"]: item for item in related_items if isinstance(item.get("id"), int)}


def render_work_item(
    item: dict[str, Any],
    context: BoardContext,
    client: AzureClient,
    output_dir: Path,
    related_lookup: dict[int, dict[str, Any]],
    skip_attachments: bool,
) -> Path:
    item_id = item["id"]
    fields = item.get("fields", {})
    title = str(fields.get("System.Title") or f"Work item {item_id}")
    file_path = output_dir / f"{item_id}-{slugify(title)}.md"
    attachment_dir = output_dir / "attachments" / str(item_id)

    downloaded_attachments: list[tuple[str, Path]] = []
    if not skip_attachments:
        downloaded_attachments = download_relation_attachments(item, client, attachment_dir)

    lines: list[str] = [
        f"# #{item_id} {title}",
        "",
        f"- Azure DevOps: [open work item]({context.work_item_url(item_id)})",
        f"- Exported: {utc_now_iso()}",
        "",
    ]

    metadata_rows = metadata_for_item(fields)
    if metadata_rows:
        lines.extend(["## Metadata", "", markdown_table(["Field", "Value"], metadata_rows), ""])

    html_sections = html_sections_for_item(fields)
    for field_name, raw_value in html_sections:
        section_title = field_label(field_name)
        value = str(raw_value)
        if not skip_attachments:
            value = localize_inline_images(value, client, attachment_dir, output_dir, context)
        markdown_value = html_to_markdown(value)
        if markdown_value:
            lines.extend([f"## {section_title}", "", markdown_value, ""])

    extra_rows = extra_fields_for_item(fields)
    if extra_rows:
        lines.extend(["## Additional Fields", "", markdown_table(["Field", "Value"], extra_rows), ""])

    relation_rows = relation_rows_for_item(item, context, related_lookup)
    if relation_rows:
        lines.extend(["## Relations", "", markdown_table(["Relation", "Target", "Comment"], relation_rows), ""])

    if downloaded_attachments:
        lines.extend(["## Attachments", ""])
        for label, path in downloaded_attachments:
            relative = Path(os.path.relpath(path, output_dir)).as_posix()
            lines.append(f"- [{escape_markdown_inline(label)}]({relative})")
        lines.append("")

    hyperlinks = hyperlink_rows_for_item(item)
    if hyperlinks:
        lines.extend(["## Hyperlinks", "", markdown_table(["URL", "Comment"], hyperlinks), ""])

    file_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return file_path


def metadata_for_item(fields: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for field_name in CORE_FIELD_ORDER:
        if field_name in fields and not is_empty(fields[field_name]):
            rows.append([field_label(field_name), format_field_value(fields[field_name])])
    return rows


def html_sections_for_item(fields: dict[str, Any]) -> list[tuple[str, Any]]:
    sections: list[tuple[str, Any]] = []
    used: set[str] = set()
    for field_name in HTML_FIELD_ORDER:
        value = fields.get(field_name)
        if isinstance(value, str) and value.strip():
            sections.append((field_name, value))
            used.add(field_name)
    for field_name, value in sorted(fields.items()):
        if field_name in used:
            continue
        if isinstance(value, str) and looks_like_html(value):
            sections.append((field_name, value))
    return sections


def extra_fields_for_item(fields: dict[str, Any]) -> list[list[str]]:
    excluded = set(CORE_FIELD_ORDER + HTML_FIELD_ORDER + ["System.Title"])
    rows: list[list[str]] = []
    for field_name in sorted(fields):
        value = fields[field_name]
        if field_name in excluded or is_empty(value):
            continue
        if isinstance(value, str) and looks_like_html(value):
            continue
        rows.append([field_label(field_name), format_field_value(value)])
    return rows


def relation_rows_for_item(
    item: dict[str, Any], context: BoardContext, related_lookup: dict[int, dict[str, Any]]
) -> list[list[str]]:
    rows: list[list[str]] = []
    for relation in item.get("relations", []) or []:
        rel = relation.get("rel", "")
        if rel == "AttachedFile" or rel == "Hyperlink":
            continue
        name = relation_name(relation)
        url = relation.get("url", "")
        comment = relation.get("attributes", {}).get("comment", "")
        related_id = relation_work_item_id(url)
        if related_id is not None:
            related = related_lookup.get(related_id)
            if related:
                fields = related.get("fields", {})
                title = fields.get("System.Title", f"Work item {related_id}")
                work_type = fields.get("System.WorkItemType", "Work Item")
                state = fields.get("System.State", "")
                label = f"#{related_id} {title} ({work_type}, {state})".strip()
            else:
                label = f"#{related_id}"
            target = f"[{escape_markdown_inline(label)}]({context.work_item_url(related_id)})"
        elif url:
            target = f"[{escape_markdown_inline(url)}]({url})"
        else:
            target = ""
        rows.append([name, target, str(comment)])
    return rows


def hyperlink_rows_for_item(item: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for relation in item.get("relations", []) or []:
        if relation.get("rel") != "Hyperlink":
            continue
        url = relation.get("url", "")
        comment = relation.get("attributes", {}).get("comment", "")
        rows.append([f"[{escape_markdown_inline(url)}]({url})", str(comment)])
    return rows


def download_relation_attachments(
    item: dict[str, Any], client: AzureClient, attachment_dir: Path
) -> list[tuple[str, Path]]:
    downloaded: list[tuple[str, Path]] = []
    for index, relation in enumerate(item.get("relations", []) or [], start=1):
        if relation.get("rel") != "AttachedFile":
            continue
        url = relation.get("url")
        if not url:
            continue
        attributes = relation.get("attributes", {})
        filename = attributes.get("name") or filename_from_url(url) or f"attachment-{index}"
        data, content_type, header_filename = client.download_bytes(add_api_version(url, client.api_version))
        final_name = safe_attachment_name(header_filename or filename, content_type)
        path = unique_path(attachment_dir / final_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        downloaded.append((final_name, path))
    return downloaded


def localize_inline_images(
    html_text: str,
    client: AzureClient,
    attachment_dir: Path,
    markdown_base: Path,
    context: BoardContext,
) -> str:
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        prefix, src, suffix = match.groups()
        decoded_src = html.unescape(src)
        try:
            counter += 1
            if decoded_src.startswith("data:"):
                data, content_type = decode_data_uri(decoded_src)
                filename = f"inline-image-{counter}{extension_for_content_type(content_type)}"
            else:
                absolute_url = decoded_src
                if not decoded_src.startswith(("http://", "https://")):
                    absolute_url = urllib.parse.urljoin(context.web_base + "/", decoded_src)
                data, content_type, header_filename = client.download_bytes(
                    add_api_version(absolute_url, client.api_version)
                )
                filename = header_filename or filename_from_url(absolute_url) or f"inline-image-{counter}"
                filename = safe_attachment_name(filename, content_type)
            path = unique_path(attachment_dir / filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            relative = Path(os.path.relpath(path, markdown_base)).as_posix()
            return prefix + html.escape(relative, quote=True) + suffix
        except (AzureDevOpsError, ValueError, OSError) as exc:
            print(f"warning: could not download inline image {decoded_src}: {exc}", file=sys.stderr)
            return match.group(0)

    return HTML_IMG_SRC_RE.sub(replace, html_text)


def write_index(
    output_dir: Path,
    context: BoardContext,
    backlog_id: str,
    items: list[dict[str, Any]],
    written_files: list[Path],
) -> None:
    rows: list[list[str]] = []
    for item, path in zip(items, written_files):
        fields = item.get("fields", {})
        item_id = item.get("id", "")
        title = str(fields.get("System.Title") or f"Work item {item_id}")
        rel_path = Path(os.path.relpath(path, output_dir)).as_posix()
        rows.append(
            [
                str(item_id),
                format_field_value(fields.get("System.WorkItemType", "")),
                format_field_value(fields.get("System.State", "")),
                f"[{escape_markdown_inline(title)}]({rel_path})",
            ]
        )
    lines = [
        "# Azure Boards Export",
        "",
        f"- Source board: [{context.source_url}]({context.source_url})",
        f"- Organization: {context.organization}",
        f"- Project: {context.project}",
        f"- Team: {context.team or 'TODO'}",
        f"- Backlog: {context.board_name or backlog_id}",
        f"- Backlog id: {backlog_id}",
        f"- Exported: {utc_now_iso()}",
        f"- Work items: {len(items)}",
        "",
        markdown_table(["ID", "Type", "State", "Title"], rows),
        "",
    ]
    (output_dir / "_index.md").write_text("\n".join(lines), encoding="utf-8")


def work_api_url(client: AzureClient, context: BoardContext, segments: list[str]) -> str:
    ensure_team(context)
    path = [
        quote_segment(context.organization),
        quote_segment(context.project),
        quote_segment(context.team or ""),
        "_apis",
        "work",
        *[quote_segment(segment) for segment in segments],
    ]
    return build_devops_url(path, {"api-version": client.api_version})


def wit_api_url(client: AzureClient, context: BoardContext, segments: list[str]) -> str:
    path = [
        quote_segment(context.organization),
        quote_segment(context.project),
        "_apis",
        "wit",
        *[quote_segment(segment) for segment in segments],
    ]
    return build_devops_url(path, {"api-version": client.api_version})


def build_devops_url(path_segments: list[str], query: dict[str, str]) -> str:
    path = "/" + "/".join(path_segments)
    return urllib.parse.urlunparse(
        ("https", "dev.azure.com", path, "", urllib.parse.urlencode(query), "")
    )


def add_api_version(url: str, api_version: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key.lower() == "api-version" for key, _value in query):
        query.append(("api-version", api_version))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def ensure_team(context: BoardContext) -> None:
    if not context.team:
        raise ValueError("could not infer team from URL; board URL must contain /_boards/board/t/<team>/")


def chunks(values: list[int], size: int) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def quote_segment(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def slugify(value: str) -> str:
    import unicodedata

    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    return slug[:80] or "work-item"


def default_output_dir(context: BoardContext, backlog_name: str | None) -> Path:
    parts = [context.organization, context.project, context.team or "team", backlog_name or "backlog"]
    return Path("reports") / "evaluations" / "azure-boards" / slugify("-".join(parts))


def field_label(field_name: str) -> str:
    if field_name in FIELD_LABELS:
        return FIELD_LABELS[field_name]
    tail = field_name.split(".")[-1]
    tail = re.sub(r"([a-z])([A-Z])", r"\1 \2", tail)
    return tail.replace("_", " ")


def format_field_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        display = value.get("displayName") or value.get("name")
        unique = value.get("uniqueName") or value.get("mailAddress")
        if display and unique:
            return f"{display} <{unique}>"
        if display:
            return str(display)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, list):
        return ", ".join(format_field_value(item) for item in value)
    return str(value).strip()


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def looks_like_html(value: str) -> bool:
    return bool(re.search(r"</?[A-Za-z][^>]*>", value))


def html_to_markdown(value: str) -> str:
    parser = MarkdownHTMLConverter()
    parser.feed(value)
    parser.close()
    markdown = parser.markdown()
    if markdown:
        return markdown
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    escaped_headers = [table_cell(header) for header in headers]
    lines = [
        "| " + " | ".join(escaped_headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(table_cell(value) for value in padded[: len(headers)]) + " |")
    return "\n".join(lines)


def table_cell(value: Any) -> str:
    text = format_field_value(value)
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    text = re.sub(r"\s*\n\s*", "<br>", text)
    return text


def escape_markdown_inline(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def relation_name(relation: dict[str, Any]) -> str:
    attributes = relation.get("attributes", {})
    return str(attributes.get("name") or relation.get("rel") or "Relation")


def relation_work_item_id(url: str) -> int | None:
    match = re.search(r"/workItems/(\d+)(?:\b|$)", url, re.IGNORECASE)
    if not match:
        match = re.search(r"/_workitems/edit/(\d+)(?:\b|$)", url, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def filename_from_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("fileName", "filename", "name"):
        if key in query and query[key]:
            return urllib.parse.unquote(posixpath.basename(query[key][0]))
    basename = posixpath.basename(parsed.path)
    return urllib.parse.unquote(basename) if basename else None


def filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"filename\*=UTF-8''([^;]+)", value, re.IGNORECASE)
    if match:
        return urllib.parse.unquote(match.group(1).strip("\""))
    match = re.search(r"filename=\"?([^\";]+)\"?", value, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def safe_attachment_name(filename: str, content_type: str | None = None) -> str:
    name = posixpath.basename(filename).strip() or "attachment"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "-", name).strip(" .-") or "attachment"
    suffix = Path(name).suffix
    if not suffix and content_type:
        name += extension_for_content_type(content_type)
    return name


def extension_for_content_type(content_type: str | None) -> str:
    if not content_type:
        return ""
    media_type = content_type.split(";", 1)[0].strip().lower()
    return IMAGE_EXTENSIONS.get(media_type, "")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(2, 10000):
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise OSError(f"could not find unique path for {path}")


def decode_data_uri(value: str) -> tuple[bytes, str | None]:
    match = re.match(r"data:([^;,]+)?(;base64)?,(.*)$", value, re.DOTALL)
    if not match:
        raise ValueError("invalid data URI")
    content_type = match.group(1)
    is_base64 = bool(match.group(2))
    payload = match.group(3)
    if is_base64:
        return base64.b64decode(payload), content_type
    return urllib.parse.unquote_to_bytes(payload), content_type


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def redact_query(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    safe_query = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in {"token", "access_token", "authorization"}:
            safe_query.append((key, "REDACTED"))
        else:
            safe_query.append((key, value))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(safe_query)))


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
