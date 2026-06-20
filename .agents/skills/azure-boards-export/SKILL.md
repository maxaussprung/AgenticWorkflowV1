---
name: azure-boards-export
description: Export Azure DevOps Boards or backlog tickets to Markdown files, including work item fields, relations to parent/child/related stories, hyperlinks, attachments, and inline images. Use when a user asks to fetch, mirror, archive, import, or document tickets from an Azure DevOps board/backlog URL with a bearer token, PAT, or an interactive browser login.
---

# Azure Boards Export

Use this skill for repeatable Azure DevOps ticket exports. Prefer the bundled script over hand-written API calls so backlog resolution, relation traversal, attachment downloads, and Markdown rendering stay consistent.

## Fit

Use a skill for this workflow, not a subagent. The core work is deterministic API extraction and file generation. Use a requirements or architecture subagent only after the export, when the user asks to curate exported tickets into requirements, features, test cases, or design decisions.

## Inputs

- Azure DevOps board/backlog URL, for example:
  `https://dev.azure.com/{AZURE-DEVOPS-ORG}/{AZURE-DEVOPS-PROJECT}/_boards/`
- Token supplied outside the prompt, or an authenticated in-app browser session. Prefer `AZURE_DEVOPS_BEARER_TOKEN` for token mode; do not paste tokens into conversation history.
- Output directory. Treat the export as generated evidence by default, usually under `reports/evaluations/azure-boards/<board-slug>/`.

## Token Command

```bash
AZURE_DEVOPS_BEARER_TOKEN="<token>" \
python3 tools/azure-boards-export/scripts/export_azure_boards.py \
  "https://dev.azure.com/{AZURE-DEVOPS-ORG}/{AZURE-DEVOPS-PROJECT}/_boards/" \
  --output-dir reports/evaluations/azure-boards/{project}-stories
```

The script writes one Markdown file per work item, an `_index.md`, and downloaded files under `attachments/<work-item-id>/`.

## Browser Login Command

Use this mode when shell network/DNS is blocked or when the user prefers to log in interactively.

1. Open the board in the in-app browser and ask the user to complete login:

```js
const { setupBrowserRuntime } = await import("<path-to-browser-client.mjs>");
await setupBrowserRuntime({ globals: globalThis });
globalThis.browser = await agent.browsers.get("iab");
const { openAzureBoardsForLogin } = await import("./tools/azure-boards-export/scripts/export_azure_boards_browser.mjs");
await openAzureBoardsForLogin({
  browser,
  boardUrl: "https://dev.azure.com/{AZURE-DEVOPS-ORG}/{AZURE-DEVOPS-PROJECT}/_boards/"
});
```

2. After the user confirms the board is visible and logged in, fetch and write the export:

```js
const { exportAzureBoardsFromBrowser } = await import("./tools/azure-boards-export/scripts/export_azure_boards_browser.mjs");
await exportAzureBoardsFromBrowser({
  browser,
  boardUrl: "https://dev.azure.com/{AZURE-DEVOPS-ORG}/{AZURE-DEVOPS-PROJECT}/_boards/",
  outputDir: "reports/evaluations/azure-boards/{project}-stories"
});
```

Browser mode uses `fetch(..., { credentials: "include" })` inside the logged-in Azure DevOps tab. It does not read or persist passwords, cookies, or bearer tokens.
When that browser runtime blocks page-level request APIs, the browser exporter falls back to
credentialed API navigation for JSON. For image attachments, it can also open the work item
attachment preview and save a clipped screenshot of the rendered image. The same preview-capture
fallback is used for inline `<img>` elements embedded directly in story description or acceptance
criteria fields. Use token mode when you need exact original attachment bytes or non-image files.

For large boards, keep browser calls under the tool timeout by using batch options:
`includeInlineImages: false` for a fast full metadata export, then rerender image-bearing tickets
with `workItemIds: [...]`, `writeIndex: false`, and `includeInlineImages: true`. If the team's
backlog endpoint is blocked but work-item APIs are available, pass known `workItemIds` and a
`backlogId` such as `Microsoft.RequirementCategory` to bypass backlog discovery. Use
`includeRelatedLookup: false` when browser API navigation is slow; relation links are still
exported, but related item titles are not enriched.

## Workflow

1. Parse the supplied board URL into organization, project, team, and backlog/board name.
2. List the team's backlog levels and resolve the board name to a backlog id.
3. Fetch all work item ids from that backlog level.
4. Fetch work items in batches with relations expanded.
5. Download `AttachedFile` relations and inline `<img>` references found in HTML fields.
6. Render one Markdown file per ticket with metadata, HTML field content, attachment links, hyperlinks, and related work item links.
7. Review the output before using it as requirements source material. Do not invent missing business meaning; mark gaps as `TODO`.

## Troubleshooting

- If backlog resolution fails, run with `--list-backlogs` and rerun with `--backlog-id <id>` or `--backlog-name <name>`.
- If the user has a PAT instead of a bearer token, set it in the same environment variable and add `--auth pat`.
- If attachments are inaccessible, verify the token has Work Items read permission and access to the project/team.
- If browser mode saves image previews but not `.docx`, `.doc`, `.prn`, or other non-image
  attachments, rerun token mode. The in-app browser may block binary downloads while still
  allowing rendered image previews.
- If only a subset of cards appears, confirm the board URL points at the intended backlog level and team.
- Keep tokens out of shell history when possible by exporting the environment variable from a secure secret store or reading it from a local token file with `--token-file`.
- If token mode fails with DNS or outbound network errors, use browser login mode. Keep the browser visible while the user completes MFA or SSO.
