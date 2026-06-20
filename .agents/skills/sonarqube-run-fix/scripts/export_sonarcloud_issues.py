#!/usr/bin/env python3
"""Export SonarCloud issues for the {PROJECT-NAME} backend/frontend projects.

The script intentionally validates required environment variables before any
network call. It prints non-secret setup guidance and exits with code 2 when
configuration is incomplete.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "test-results" / "sonarcloud"

PROJECTS = {
    "backend": {
        "env": "SONAR_CLOUD_BACKEND_PROJECT_KEY",
    },
    "frontend": {
        "env": "SONAR_CLOUD_FRONTEND_PROJECT_KEY",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export open SonarCloud issues for backend/frontend projects."
    )
    parser.add_argument(
        "--scope",
        choices=("backend", "frontend", "both"),
        required=True,
        help="Project scope to query. Required: backend, frontend, or both.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for JSON and Markdown output.",
    )
    parser.add_argument(
        "--branch",
        default=os.environ.get("SONAR_BRANCH"),
        help="Optional SonarCloud branch name. Defaults to SONAR_BRANCH.",
    )
    parser.add_argument(
        "--pull-request",
        default=os.environ.get("SONAR_PULL_REQUEST"),
        help="Optional SonarCloud pull request id/key. Defaults to SONAR_PULL_REQUEST.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=500,
        help="SonarCloud API page size. Default: 500.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="Safety cap for paginated issue fetching. Default: 20.",
    )
    return parser.parse_args()


def select_projects(scope: str) -> list[str]:
    if scope == "both":
        return ["backend", "frontend"]
    if scope in PROJECTS:
        return [scope]
    raise ValueError(f"Unsupported scope: {scope}")


def require_env(projects: list[str]) -> dict[str, str]:
    required = ["SONAR_TOKEN", "SONAR_CLOUD_ORGANIZATION"]
    required.extend(PROJECTS[project]["env"] for project in projects)

    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        print("SonarCloud issue export cannot run because required environment variables are missing.")
        print("")
        print("Set these variables and rerun the skill:")
        for name in missing:
            print(f"- {name}")
        print("")
        print("Do not paste token values into chat. Export them in your shell or secret store.")
        raise SystemExit(2)

    return {name: os.environ[name] for name in required}


def build_url(host_url: str, path: str, params: dict[str, str | int]) -> str:
    query = urllib.parse.urlencode(params)
    return f"{host_url.rstrip('/')}{path}?{query}"


def auth_headers(token: str, scheme: str) -> dict[str, str]:
    if scheme == "basic":
        encoded = base64.b64encode(f"{token}:".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    return {"Authorization": f"Bearer {token}"}


def request_json(url: str, token: str) -> dict[str, Any]:
    last_error: urllib.error.HTTPError | None = None
    for scheme in ("bearer", "basic"):
        request = urllib.request.Request(url, headers=auth_headers(token, scheme))
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code != 401:
                break

    if last_error is not None:
        detail = last_error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SonarCloud API request failed with HTTP {last_error.code}: {detail}")

    raise RuntimeError("SonarCloud API request failed before a response was received.")


def fetch_project_issues(
    *,
    host_url: str,
    token: str,
    organization: str,
    project_key: str,
    project_name: str,
    branch: str | None,
    pull_request: str | None,
    page_size: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        params: dict[str, str | int] = {
            "organization": organization,
            "componentKeys": project_key,
            "statuses": "OPEN,CONFIRMED,REOPENED",
            "additionalFields": "_all",
            "p": page,
            "ps": page_size,
        }

        if pull_request:
            params["pullRequest"] = pull_request
        elif branch:
            params["branch"] = branch

        url = build_url(host_url, "/api/issues/search", params)
        payload = request_json(url, token)
        page_issues = payload.get("issues", [])

        for issue in page_issues:
            issue["postProject"] = project_name
            issue["postProjectKey"] = project_key
            issue["postPath"] = component_path(issue.get("component", ""))
            issue["postUrl"] = issue_url(host_url, project_key, issue)

        issues.extend(page_issues)

        paging = payload.get("paging", {})
        total = int(paging.get("total", len(issues)))
        if len(issues) >= total or not page_issues:
            break

    return issues


def component_path(component: str) -> str:
    if ":" in component:
        return component.split(":", 1)[1]
    return component


def issue_url(host_url: str, project_key: str, issue: dict[str, Any]) -> str:
    params = urllib.parse.urlencode(
        {
            "id": project_key,
            "issues": issue.get("key", ""),
            "open": issue.get("key", ""),
        }
    )
    return f"{host_url.rstrip('/')}/project/issues?{params}"


def severity_rank(issue: dict[str, Any]) -> int:
    severity = str(issue.get("severity", "")).upper()
    ranks = {
        "BLOCKER": 0,
        "CRITICAL": 1,
        "MAJOR": 2,
        "MINOR": 3,
        "INFO": 4,
    }
    return ranks.get(severity, 99)


def write_outputs(output_dir: Path, issues_by_project: dict[str, list[dict[str, Any]]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    all_issues: list[dict[str, Any]] = []
    for project, issues in issues_by_project.items():
        sorted_issues = sorted(
            issues,
            key=lambda issue: (
                severity_rank(issue),
                str(issue.get("postPath", "")),
                int(issue.get("line") or 0),
            ),
        )
        all_issues.extend(sorted_issues)
        (output_dir / f"{project}-issues.json").write_text(
            json.dumps(sorted_issues, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    all_issues = sorted(
        all_issues,
        key=lambda issue: (
            str(issue.get("postProject", "")),
            severity_rank(issue),
            str(issue.get("postPath", "")),
            int(issue.get("line") or 0),
        ),
    )
    (output_dir / "issues.json").write_text(
        json.dumps(all_issues, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(render_summary(issues_by_project), encoding="utf-8")


def render_summary(issues_by_project: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "# SonarCloud Issue Export",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Totals",
        "",
        "| Project | Open issues |",
        "|---|---:|",
    ]

    for project, issues in issues_by_project.items():
        lines.append(f"| {project} | {len(issues)} |")

    lines.extend(["", "## Issues", ""])

    for project, issues in issues_by_project.items():
        lines.extend([f"### {project}", ""])
        if not issues:
            lines.extend(["No open issues returned.", ""])
            continue

        sorted_issues = sorted(
            issues,
            key=lambda issue: (
                severity_rank(issue),
                str(issue.get("postPath", "")),
                int(issue.get("line") or 0),
            ),
        )
        for issue in sorted_issues:
            line = issue.get("line")
            location = issue.get("postPath") or issue.get("component") or "<unknown>"
            if line:
                location = f"{location}:{line}"
            severity = issue.get("severity") or "-"
            issue_type = issue.get("type") or "-"
            rule = issue.get("rule") or "-"
            message = str(issue.get("message") or "").replace("\n", " ")
            url = issue.get("postUrl") or ""
            lines.append(f"- `{severity}` `{issue_type}` `{rule}` {location} - {message}")
            if url:
                lines.append(f"  SonarCloud: {url}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    projects = select_projects(args.scope)
    env = require_env(projects)

    host_url = os.environ.get("SONAR_HOST_URL", "https://sonarcloud.io")
    token = env["SONAR_TOKEN"]
    organization = env["SONAR_CLOUD_ORGANIZATION"]

    issues_by_project: dict[str, list[dict[str, Any]]] = {}
    for project in projects:
        project_key = env[PROJECTS[project]["env"]]
        issues_by_project[project] = fetch_project_issues(
            host_url=host_url,
            token=token,
            organization=organization,
            project_key=project_key,
            project_name=project,
            branch=args.branch,
            pull_request=args.pull_request,
            page_size=args.page_size,
            max_pages=args.max_pages,
        )

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    write_outputs(output_dir, issues_by_project)

    total = sum(len(issues) for issues in issues_by_project.values())
    print(f"Exported {total} open SonarCloud issues to {output_dir}")
    for project, issues in issues_by_project.items():
        print(f"- {project}: {len(issues)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
