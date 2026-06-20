import fs from "node:fs/promises";
import path from "node:path";
import { Buffer } from "node:buffer";

const DEFAULT_API_VERSION = "7.1";
const MAX_BATCH_SIZE = 1;

const CORE_FIELD_ORDER = [
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
];

const HTML_FIELD_ORDER = [
  "System.Description",
  "Microsoft.VSTS.Common.AcceptanceCriteria",
  "Microsoft.VSTS.TCM.ReproSteps",
  "Microsoft.VSTS.Common.SystemInfo",
];

const FIELD_LABELS = new Map([
  ["System.Id", "ID"],
  ["System.Title", "Title"],
  ["System.WorkItemType", "Type"],
  ["System.State", "State"],
  ["System.Reason", "Reason"],
  ["System.AssignedTo", "Assigned To"],
  ["System.AreaPath", "Area Path"],
  ["System.IterationPath", "Iteration Path"],
  ["System.Tags", "Tags"],
  ["System.CreatedBy", "Created By"],
  ["System.CreatedDate", "Created"],
  ["System.ChangedBy", "Changed By"],
  ["System.ChangedDate", "Changed"],
  ["System.Description", "Description"],
  ["Microsoft.VSTS.Common.AcceptanceCriteria", "Acceptance Criteria"],
  ["Microsoft.VSTS.TCM.ReproSteps", "Repro Steps"],
  ["Microsoft.VSTS.Common.SystemInfo", "System Info"],
  ["Microsoft.VSTS.Common.Priority", "Priority"],
  ["Microsoft.VSTS.Scheduling.Effort", "Effort"],
  ["Microsoft.VSTS.Scheduling.StoryPoints", "Story Points"],
  ["Microsoft.VSTS.Common.BusinessValue", "Business Value"],
  ["Microsoft.VSTS.Common.ValueArea", "Value Area"],
]);

const IMAGE_EXTENSIONS = new Map([
  ["image/png", ".png"],
  ["image/jpeg", ".jpg"],
  ["image/jpg", ".jpg"],
  ["image/gif", ".gif"],
  ["image/webp", ".webp"],
  ["image/svg+xml", ".svg"],
  ["image/bmp", ".bmp"],
]);

export async function openAzureBoardsForLogin({ browser, boardUrl }) {
  await (await browser.capabilities.get("visibility")).set(true);
  const tab = await browser.tabs.new();
  await tab.goto(boardUrl);
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 }).catch(() => {});
  return {
    tabId: tab.id,
    title: await tab.title(),
    url: await tab.url(),
  };
}

export async function exportAzureBoardsFromBrowser({
  browser,
  boardUrl,
  outputDir,
  tabId,
  apiVersion = DEFAULT_API_VERSION,
  includeAttachments = true,
  includeInlineImages = includeAttachments,
  workItemIds,
  backlogId: explicitBacklogId,
  writeIndex = true,
  includeRelatedLookup = true,
}) {
  const resetViewport = await setAttachmentViewport(browser, includeAttachments || includeInlineImages);
  try {
    const context = parseBoardUrl(boardUrl);
    const root = resolveOutputDir(outputDir);
    await fs.mkdir(root, { recursive: true });

    const tab = tabId ? await browser.tabs.get(tabId) : await getBestTab(browser, boardUrl);
    const currentUrl = await tab.url();
    if (workItemIds === undefined && (!currentUrl || !currentUrl.startsWith(context.webBase) || currentUrl.includes("/_apis/"))) {
      await tab.goto(boardUrl);
      await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 }).catch(() => {});
    }

    const backlogId = explicitBacklogId
      ?? (workItemIds === undefined
        ? resolveBacklogId((await browserJson(tab, workApiUrl(context, ["backlogs"], apiVersion))).value ?? [], context.boardName)
        : context.boardName || "TODO");
    const selectedWorkItemIds = workItemIds === undefined
      ? await getBacklogWorkItemIds(tab, context, backlogId, apiVersion)
      : unique(workItemIds.map((id) => Number(id)).filter((id) => Number.isInteger(id)));
    if (selectedWorkItemIds.length === 0) {
      if (writeIndex) await writeIndexFile(root, context, backlogId, [], []);
      return { outputDir: root, workItems: 0, attachments: 0, backlogId };
    }

    const items = await fetchWorkItems(tab, context, selectedWorkItemIds, apiVersion, { expandRelations: true });
    const relatedLookup = includeRelatedLookup
      ? await fetchRelatedWorkItems(tab, context, items, apiVersion)
      : new Map();

    let attachmentCount = 0;
    const writtenFiles = [];
    for (const item of items) {
      const result = await renderWorkItem({
        tab,
        context,
        apiVersion,
        outputDir: root,
        item,
        relatedLookup,
        includeAttachments,
        includeInlineImages,
      });
      writtenFiles.push(result.filePath);
      attachmentCount += result.attachmentCount;
    }

    if (writeIndex) await writeIndexFile(root, context, backlogId, items, writtenFiles);
    return {
      outputDir: root,
      workItems: writtenFiles.length,
      attachments: attachmentCount,
      backlogId,
    };
  } finally {
    await resetViewport();
  }
}

async function getBacklogWorkItemIds(tab, context, backlogId, apiVersion) {
  const workItemsPayload = await browserJson(
    tab,
    workApiUrl(context, ["backlogs", backlogId, "workItems"], apiVersion),
  );
  return unique(extractIdsFromPayload(workItemsPayload));
}

async function setAttachmentViewport(browser, includeAttachments) {
  if (!includeAttachments) return async () => {};
  try {
    const viewport = await browser.capabilities.get("viewport");
    await viewport.set({ width: 1920, height: 1200 });
    return async () => {
      await viewport.reset().catch(() => {});
    };
  } catch {
    return async () => {};
  }
}

async function getBestTab(browser, boardUrl) {
  const selected = await browser.tabs.selected();
  if (selected) {
    const selectedUrl = await selected.url();
    if (selectedUrl?.startsWith("https://dev.azure.com/")) return selected;
  }
  for (const info of await browser.tabs.list()) {
    if (info.url === boardUrl || info.url?.startsWith("https://dev.azure.com/")) {
      return await browser.tabs.get(info.id);
    }
  }
  const tab = await browser.tabs.new();
  await tab.goto(boardUrl);
  return tab;
}

async function browserJson(tab, url, body = undefined) {
  const result = await tab.playwright.evaluate(
    async ({ url: requestUrl, body: requestBody }) => {
      const request = typeof fetch === "function" ? fetch.bind(undefined) : undefined;
      if (!request) return { ok: false, requestUnavailable: true };
      const response = await request(requestUrl, {
        method: requestBody === undefined ? "GET" : "POST",
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...(requestBody === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: requestBody === undefined ? undefined : JSON.stringify(requestBody),
      });
      const text = await response.text();
      if (!response.ok) {
        return { ok: false, status: response.status, statusText: response.statusText, text };
      }
      try {
        return { ok: true, json: text ? JSON.parse(text) : {} };
      } catch {
        return { ok: false, status: response.status, statusText: "Invalid JSON", text: text.slice(0, 2000) };
      }
    },
    { url, body },
    { timeoutMs: 60000 },
  );
  if (result.requestUnavailable && body === undefined) {
    return await browserJsonByNavigation(tab, url);
  }
  if (result.requestUnavailable) {
    throw new Error("Azure DevOps browser request failed: browser page request APIs are unavailable for POST requests");
  }
  if (!result.ok) {
    throw new Error(`Azure DevOps browser request failed ${result.status} ${result.statusText}: ${result.text?.slice(0, 1000)}`);
  }
  return result.json;
}

async function browserJsonByNavigation(tab, url) {
  await tab.goto(url).catch(() => {});
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 }).catch(() => {});
  const result = await tab.playwright.evaluate(
    () => {
      const text = document.querySelector("pre")?.textContent?.trim()
        || document.body?.textContent?.trim()
        || document.documentElement?.textContent?.trim()
        || "";
      try {
        return { ok: true, json: JSON.parse(text) };
      } catch (error) {
        return { ok: false, message: error?.message || "Invalid JSON", text: text.slice(0, 1000) };
      }
    },
    undefined,
    { timeoutMs: 60000 },
  );
  if (!result.ok) {
    throw new Error(`Azure DevOps browser request failed: expected JSON after navigating to ${url}, got ${result.text}`);
  }
  const parsed = result.json;
  if (parsed && typeof parsed === "object" && ("typeKey" in parsed || "errorCode" in parsed) && "message" in parsed) {
    throw new Error(`Azure DevOps browser request failed: ${parsed.message}`);
  }
  return parsed;
}

async function browserBytes(tab, url) {
  const result = await tab.playwright.evaluate(
    async (requestUrl) => {
      const request = typeof fetch === "function" ? fetch.bind(undefined) : undefined;
      if (!request) return { ok: false, requestUnavailable: true };
      const response = await request(requestUrl, {
        credentials: "include",
        headers: { Accept: "application/octet-stream,*/*" },
      });
      if (!response.ok) {
        const text = await response.text();
        return { ok: false, status: response.status, statusText: response.statusText, text };
      }
      const contentType = response.headers.get("content-type");
      const contentDisposition = response.headers.get("content-disposition");
      const bytes = new Uint8Array(await response.arrayBuffer());
      let binary = "";
      const chunkSize = 0x8000;
      for (let index = 0; index < bytes.length; index += chunkSize) {
        binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
      }
      return {
        ok: true,
        base64: btoa(binary),
        contentType,
        contentDisposition,
      };
    },
    url,
    { timeoutMs: 120000 },
  );
  if (result.requestUnavailable) {
    const error = new Error("Azure DevOps browser download failed: browser page request APIs are unavailable");
    error.requestUnavailable = true;
    throw error;
  }
  if (!result.ok) {
    throw new Error(`Azure DevOps browser download failed ${result.status} ${result.statusText}: ${result.text?.slice(0, 1000)}`);
  }
  return result;
}

async function downloadAttachment(tab, context, apiVersion, itemId, relation, suggested) {
  try {
    return await browserBytes(tab, addApiVersion(relation.url, apiVersion));
  } catch (error) {
    if (!error.requestUnavailable || !isImageFilename(suggested)) throw error;
    return await captureAttachmentImagePreview(tab, context, itemId, relation, suggested);
  }
}

async function captureAttachmentImagePreview(tab, context, itemId, relation, suggested) {
  try {
    return await captureDirectImagePreview(tab, relation.url, withJpgExtension(suggested));
  } catch {
    // Fall through to the work item preview when Azure does not render the direct image URL.
  }

  await tab.goto(context.workItemUrl(itemId));
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 }).catch(() => {});
  await tab.playwright.waitForTimeout(1000);

  await clickVisibleNode(tab, (line) => line.includes('aria-label="Attachments"') && line.includes('role="tab"'));
  await tab.playwright.waitForTimeout(1000);
  await clickVisibleNode(tab, (line) => line.includes(suggested) && line.includes('role="button"'));
  await tab.playwright.waitForTimeout(1500);

  const attachmentId = attachmentIdFromUrl(relation.url);
  const image = await waitForAttachmentImage(tab, attachmentId);
  if (!image?.rect) {
    throw new Error(`could not render attachment preview for ${suggested}`);
  }

  const clip = normalizeClip(image.rect);
  const bytes = await tab.screenshot({ clip });
  return {
    base64: Buffer.from(bytes).toString("base64"),
    contentType: "image/jpeg",
    contentDisposition: undefined,
    filename: withJpgExtension(suggested),
    previewCapture: true,
  };
}

async function clickVisibleNode(tab, predicate) {
  const dom = String(await tab.dom_cua.get_visible_dom());
  const line = dom.split("\n").find(predicate);
  const id = line?.match(/node_id=(\d+)/)?.[1];
  if (!id) throw new Error("could not find visible Azure DevOps attachment control");
  await tab.dom_cua.click({ node_id: id });
}

async function waitForAttachmentImage(tab, attachmentId) {
  return await waitForRenderedImage(tab, attachmentId);
}

async function waitForRenderedImage(tab, imageKey) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const image = await tab.playwright.evaluate(
      (key) => {
        const match = [...document.images].find((candidate) => candidate.src.includes(key));
        if (!match || !match.naturalWidth || !match.naturalHeight) return null;
        match.scrollIntoView?.({ block: "center", inline: "center" });
        const rect = match.getBoundingClientRect?.();
        if (!rect || rect.width <= 0 || rect.height <= 0) return null;
        return {
          naturalWidth: match.naturalWidth,
          naturalHeight: match.naturalHeight,
          rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        };
      },
      imageKey,
      { timeoutMs: 30000 },
    );
    if (image) return image;
    await tab.playwright.waitForTimeout(500);
  }
  return null;
}

async function waitForAnyRenderedImage(tab) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const image = await tab.playwright.evaluate(
      () => {
        const match = [...document.images].find((candidate) => candidate.naturalWidth && candidate.naturalHeight);
        if (!match) return null;
        match.scrollIntoView?.({ block: "center", inline: "center" });
        const rect = match.getBoundingClientRect?.();
        if (!rect || rect.width <= 0 || rect.height <= 0) return null;
        return {
          naturalWidth: match.naturalWidth,
          naturalHeight: match.naturalHeight,
          rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        };
      },
      undefined,
      { timeoutMs: 30000 },
    );
    if (image) return image;
    await tab.playwright.waitForTimeout(500);
  }
  return null;
}

function imageLookupKey(imageUrl) {
  const attachmentId = String(imageUrl).match(/\/attachments\/([^/?#]+)/i)?.[1];
  if (attachmentId) return attachmentId;
  const parsed = new URL(imageUrl);
  return path.posix.basename(parsed.pathname);
}

async function fetchWorkItems(tab, context, ids, apiVersion, { expandRelations, fields } = {}) {
  const byId = new Map();
  for (const chunk of chunks(ids, MAX_BATCH_SIZE)) {
    const query = {};
    if (expandRelations) query.$expand = "Relations";
    if (fields) query.fields = fields.join(",");
    const payload = chunk.length === 1
      ? await browserJson(tab, witApiUrl(context, ["workItems", String(chunk[0])], apiVersion, query))
      : await browserJson(tab, witApiUrl(context, ["workitems"], apiVersion, { ...query, ids: chunk.join(","), errorPolicy: "Omit" }));
    const values = chunk.length === 1 ? [payload] : (payload.value ?? []);
    for (const item of values) {
      if (Number.isInteger(item.id)) byId.set(item.id, item);
    }
  }
  return ids.filter((id) => byId.has(id)).map((id) => byId.get(id));
}

async function fetchRelatedWorkItems(tab, context, items, apiVersion) {
  const currentIds = new Set(items.map((item) => item.id));
  const relatedIds = new Set();
  for (const item of items) {
    for (const relation of item.relations ?? []) {
      const id = relationWorkItemId(relation.url ?? "");
      if (id !== undefined && !currentIds.has(id)) relatedIds.add(id);
    }
  }
  if (relatedIds.size === 0) return new Map();
  const fields = ["System.Id", "System.Title", "System.WorkItemType", "System.State"];
  const related = await fetchWorkItems(tab, context, [...relatedIds].sort((a, b) => a - b), apiVersion, { fields });
  return new Map(related.map((item) => [item.id, item]));
}

async function renderWorkItem({
  tab,
  context,
  apiVersion,
  outputDir,
  item,
  relatedLookup,
  includeAttachments,
  includeInlineImages,
}) {
  const fields = item.fields ?? {};
  const title = String(fields["System.Title"] || `Work item ${item.id}`);
  const filePath = path.join(outputDir, `${item.id}-${slugify(title)}.md`);
  const attachmentDir = path.join(outputDir, "attachments", String(item.id));
  let attachmentCount = 0;

  if (includeAttachments || includeInlineImages) {
    await fs.rm(attachmentDir, { recursive: true, force: true });
  }

  const downloadedAttachments = [];
  const skippedAttachments = [];
  if (includeAttachments) {
    for (const [index, relation] of (item.relations ?? []).entries()) {
      if (relation.rel !== "AttachedFile" || !relation.url) continue;
      const suggested = relation.attributes?.name || filenameFromUrl(relation.url) || `attachment-${index + 1}`;
      try {
        const download = await downloadAttachment(tab, context, apiVersion, item.id, relation, suggested);
        const headerName = filenameFromContentDisposition(download.contentDisposition);
        const name = safeAttachmentName(download.filename || headerName || suggested, download.contentType);
        const target = await uniquePath(path.join(attachmentDir, name));
        await fs.mkdir(path.dirname(target), { recursive: true });
        await fs.writeFile(target, Buffer.from(download.base64, "base64"));
        downloadedAttachments.push([path.basename(target), target, download.previewCapture]);
        attachmentCount += 1;
      } catch (error) {
        skippedAttachments.push([suggested, relation.url, error.message || String(error)]);
      }
    }
  }

  const lines = [
    `# #${item.id} ${title}`,
    "",
    `- Azure DevOps: [open work item](${context.workItemUrl(item.id)})`,
    `- Exported: ${new Date().toISOString()}`,
    "",
  ];

  const metadataRows = metadataForItem(fields);
  if (metadataRows.length) {
    lines.push("## Metadata", "", markdownTable(["Field", "Value"], metadataRows), "");
  }

  for (const [fieldName, rawValue] of htmlSectionsForItem(fields)) {
    let value = String(rawValue);
    if (includeInlineImages) {
      const localized = await localizeInlineImages(tab, context, apiVersion, item.id, value, attachmentDir, outputDir);
      value = localized.htmlText;
      attachmentCount += localized.attachmentCount;
    }
    const markdown = htmlToMarkdown(value);
    if (markdown) lines.push(`## ${fieldLabel(fieldName)}`, "", markdown, "");
  }

  const extraRows = extraFieldsForItem(fields);
  if (extraRows.length) {
    lines.push("## Additional Fields", "", markdownTable(["Field", "Value"], extraRows), "");
  }

  const relationRows = relationRowsForItem(item, context, relatedLookup);
  if (relationRows.length) {
    lines.push("## Relations", "", markdownTable(["Relation", "Target", "Comment"], relationRows), "");
  }

  if (downloadedAttachments.length || skippedAttachments.length) {
    lines.push("## Attachments", "");
    for (const [label, target, previewCapture] of downloadedAttachments) {
      const suffix = previewCapture ? " (preview capture)" : "";
      lines.push(`- [${escapeMarkdownInline(label)}](${relativeMarkdownPath(outputDir, target)})${suffix}`);
    }
    for (const [label, url, reason] of skippedAttachments) {
      lines.push(`- [${escapeMarkdownInline(label)}](${url}) (not downloaded: ${escapeMarkdownInline(reason)})`);
    }
    lines.push("");
  }

  const hyperlinks = hyperlinkRowsForItem(item);
  if (hyperlinks.length) {
    lines.push("## Hyperlinks", "", markdownTable(["URL", "Comment"], hyperlinks), "");
  }

  await fs.writeFile(filePath, `${lines.join("\n").trimEnd()}\n`, "utf8");
  return { filePath, attachmentCount };
}

async function localizeInlineImages(tab, context, apiVersion, itemId, htmlText, attachmentDir, outputDir) {
  const regex = /(<img\b[^>]*?\bsrc\s*=\s*["'])([^"']+)(["'][^>]*>)/gi;
  let result = "";
  let lastIndex = 0;
  let count = 0;
  let attachmentCount = 0;

  for (const match of htmlText.matchAll(regex)) {
    result += htmlText.slice(lastIndex, match.index);
    const [full, prefix, rawSrc, suffix] = match;
    lastIndex = match.index + full.length;
    const src = decodeHtml(rawSrc);
    try {
      count += 1;
      let base64;
      let contentType;
      let filename;
      if (src.startsWith("data:")) {
        const data = decodeDataUri(src);
        base64 = data.base64;
        contentType = data.contentType;
        filename = `inline-image-${count}${extensionForContentType(contentType)}`;
      } else {
        const absoluteUrl = src.startsWith("http://") || src.startsWith("https://")
          ? src
          : new URL(src, `${context.webBase}/`).toString();
        const download = await downloadInlineImage(tab, context, apiVersion, itemId, absoluteUrl, count);
        base64 = download.base64;
        contentType = download.contentType;
        filename = filenameFromContentDisposition(download.contentDisposition)
          || download.filename
          || filenameFromUrl(absoluteUrl)
          || `inline-image-${count}`;
        filename = safeAttachmentName(filename, contentType);
      }
      const target = await uniquePath(path.join(attachmentDir, filename));
      await fs.mkdir(path.dirname(target), { recursive: true });
      await fs.writeFile(target, Buffer.from(base64, "base64"));
      attachmentCount += 1;
      result += `${prefix}${escapeHtml(relativeMarkdownPath(outputDir, target))}${suffix}`;
    } catch (error) {
      result += full;
    }
  }
  result += htmlText.slice(lastIndex);
  return { htmlText: result, attachmentCount };
}

async function downloadInlineImage(tab, context, apiVersion, itemId, absoluteUrl, index) {
  try {
    return await browserBytes(tab, addApiVersion(absoluteUrl, apiVersion));
  } catch (error) {
    if (!error.requestUnavailable) throw error;
    return await captureInlineImagePreview(tab, context, itemId, absoluteUrl, index);
  }
}

async function captureInlineImagePreview(tab, context, itemId, imageUrl, index) {
  try {
    return await captureDirectImagePreview(tab, imageUrl, `inline-image-${index}.jpg`);
  } catch {
    // Fall through to the work item UI if the direct attachment URL cannot be rendered.
  }

  await tab.goto(context.workItemUrl(itemId));
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 }).catch(() => {});
  await tab.playwright.waitForTimeout(1500);

  const imageKey = imageLookupKey(imageUrl);
  const image = await waitForRenderedImage(tab, imageKey);
  if (!image?.rect) {
    throw new Error(`could not render inline image preview for ${imageUrl}`);
  }

  const clip = normalizeClip(image.rect);
  const bytes = await tab.screenshot({ clip });
  return {
    base64: Buffer.from(bytes).toString("base64"),
    contentType: "image/jpeg",
    contentDisposition: undefined,
    filename: `inline-image-${index}.jpg`,
    previewCapture: true,
  };
}

async function captureDirectImagePreview(tab, imageUrl, filename) {
  await tab.goto(imageUrl).catch(() => {});
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 30000 }).catch(() => {});

  const imageKey = imageLookupKey(imageUrl);
  const image = (await waitForRenderedImage(tab, imageKey)) ?? (await waitForAnyRenderedImage(tab));
  if (!image?.rect) {
    throw new Error(`could not render direct image preview for ${imageUrl}`);
  }

  const clip = normalizeClip(image.rect);
  const bytes = await tab.screenshot({ clip });
  return {
    base64: Buffer.from(bytes).toString("base64"),
    contentType: "image/jpeg",
    contentDisposition: undefined,
    filename,
    previewCapture: true,
  };
}

async function writeIndexFile(outputDir, context, backlogId, items, writtenFiles) {
  const rows = items.map((item, index) => {
    const fields = item.fields ?? {};
    const title = String(fields["System.Title"] || `Work item ${item.id}`);
    return [
      String(item.id),
      formatFieldValue(fields["System.WorkItemType"] ?? ""),
      formatFieldValue(fields["System.State"] ?? ""),
      `[${escapeMarkdownInline(title)}](${relativeMarkdownPath(outputDir, writtenFiles[index])})`,
    ];
  });
  const lines = [
    "# Azure Boards Export",
    "",
    `- Source board: [${context.sourceUrl}](${context.sourceUrl})`,
    `- Organization: ${context.organization}`,
    `- Project: ${context.project}`,
    `- Team: ${context.team || "TODO"}`,
    `- Backlog: ${context.boardName || backlogId}`,
    `- Backlog id: ${backlogId}`,
    `- Exported: ${new Date().toISOString()}`,
    `- Work items: ${items.length}`,
    "",
    markdownTable(["ID", "Type", "State", "Title"], rows),
    "",
  ];
  await fs.writeFile(path.join(outputDir, "_index.md"), lines.join("\n"), "utf8");
}

function parseBoardUrl(boardUrl) {
  const parsed = new URL(boardUrl);
  const parts = parsed.pathname.split("/").filter(Boolean).map(decodeURIComponent);
  let organization;
  let project;
  let remaining;
  if (parsed.hostname.toLowerCase() === "dev.azure.com") {
    if (parts.length < 2) throw new Error("dev.azure.com URL must include organization and project");
    [organization, project] = parts;
    remaining = parts.slice(2);
  } else if (parsed.hostname.toLowerCase().endsWith(".visualstudio.com")) {
    organization = parsed.hostname.split(".", 1)[0];
    if (parts.length < 1) throw new Error("visualstudio.com URL must include project");
    [project] = parts;
    remaining = parts.slice(1);
  } else {
    throw new Error("URL host must be dev.azure.com or *.visualstudio.com");
  }

  let team;
  let boardName;
  const boardIndex = remaining.indexOf("_boards");
  const teamMarker = remaining.indexOf("t");
  if (boardIndex !== -1 && teamMarker !== -1) {
    team = remaining[teamMarker + 1];
    boardName = remaining[teamMarker + 2];
  }

  const webBase = `https://dev.azure.com/${encodeURIComponent(organization)}/${encodeURIComponent(project)}`;
  return {
    organization,
    project,
    team,
    boardName,
    sourceUrl: boardUrl,
    webBase,
    workItemUrl: (id) => `${webBase}/_workitems/edit/${id}`,
  };
}

function workApiUrl(context, segments, apiVersion) {
  if (!context.team) throw new Error("could not infer team from URL; board URL must contain /_boards/board/t/<team>/");
  return devopsUrl(
    [context.organization, context.project, context.team, "_apis", "work", ...segments],
    apiVersion,
  );
}

function witApiUrl(context, segments, apiVersion, query = {}) {
  return devopsUrl([context.organization, context.project, "_apis", "wit", ...segments], apiVersion, query);
}

function devopsUrl(segments, apiVersion, query = {}) {
  const pathname = `/${segments.map((segment) => encodeURIComponent(segment)).join("/")}`;
  const url = new URL(`https://dev.azure.com${pathname}`);
  url.searchParams.set("api-version", apiVersion);
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  }
  return url.toString();
}

function resolveBacklogId(backlogs, backlogName) {
  if (!backlogName) throw new Error("could not infer backlog name from URL");
  const normalized = normalizeKey(backlogName);
  for (const backlog of backlogs) {
    for (const key of ["id", "name"]) {
      const value = String(backlog[key] ?? "");
      if (normalizeKey(value) === normalized) return String(backlog.id ?? value);
    }
  }
  const available = backlogs.map((backlog) => `${backlog.name ?? ""} (${backlog.id ?? ""})`).join(", ");
  throw new Error(`could not resolve backlog '${backlogName}'. Available backlogs: ${available || "none"}`);
}

function extractIdsFromPayload(payload) {
  const ids = [];
  if (Array.isArray(payload)) {
    for (const value of payload) ids.push(...extractIdsFromPayload(value));
  } else if (payload && typeof payload === "object") {
    for (const key of ["workItems", "value"]) {
      if (Array.isArray(payload[key])) ids.push(...extractIdsFromPayload(payload[key]));
    }
    if (Number.isInteger(payload.id)) ids.push(payload.id);
    if (Number.isInteger(payload.target?.id)) ids.push(payload.target.id);
    if (typeof payload.url === "string") {
      const id = relationWorkItemId(payload.url);
      if (id !== undefined) ids.push(id);
    }
  }
  return ids;
}

function metadataForItem(fields) {
  return CORE_FIELD_ORDER
    .filter((field) => field in fields && !isEmpty(fields[field]))
    .map((field) => [fieldLabel(field), formatFieldValue(fields[field])]);
}

function htmlSectionsForItem(fields) {
  const sections = [];
  const used = new Set();
  for (const field of HTML_FIELD_ORDER) {
    if (typeof fields[field] === "string" && fields[field].trim()) {
      sections.push([field, fields[field]]);
      used.add(field);
    }
  }
  for (const field of Object.keys(fields).sort()) {
    if (!used.has(field) && typeof fields[field] === "string" && looksLikeHtml(fields[field])) {
      sections.push([field, fields[field]]);
    }
  }
  return sections;
}

function extraFieldsForItem(fields) {
  const excluded = new Set([...CORE_FIELD_ORDER, ...HTML_FIELD_ORDER, "System.Title"]);
  return Object.keys(fields)
    .sort()
    .filter((field) => !excluded.has(field) && !isEmpty(fields[field]))
    .filter((field) => !(typeof fields[field] === "string" && looksLikeHtml(fields[field])))
    .map((field) => [fieldLabel(field), formatFieldValue(fields[field])]);
}

function relationRowsForItem(item, context, relatedLookup) {
  const rows = [];
  for (const relation of item.relations ?? []) {
    if (relation.rel === "AttachedFile" || relation.rel === "Hyperlink") continue;
    const name = relation.attributes?.name || relation.rel || "Relation";
    const comment = relation.attributes?.comment || "";
    const id = relationWorkItemId(relation.url ?? "");
    let target = "";
    if (id !== undefined) {
      const related = relatedLookup.get(id);
      if (related) {
        const fields = related.fields ?? {};
        const label = `#${id} ${fields["System.Title"] || `Work item ${id}`} (${fields["System.WorkItemType"] || "Work Item"}, ${fields["System.State"] || ""})`;
        target = `[${escapeMarkdownInline(label)}](${context.workItemUrl(id)})`;
      } else {
        target = `[#${id}](${context.workItemUrl(id)})`;
      }
    } else if (relation.url) {
      target = `[${escapeMarkdownInline(relation.url)}](${relation.url})`;
    }
    rows.push([name, target, String(comment)]);
  }
  return rows;
}

function hyperlinkRowsForItem(item) {
  return (item.relations ?? [])
    .filter((relation) => relation.rel === "Hyperlink")
    .map((relation) => {
      const url = relation.url ?? "";
      return [`[${escapeMarkdownInline(url)}](${url})`, String(relation.attributes?.comment ?? "")];
    });
}

function htmlToMarkdown(value) {
  return decodeHtml(value)
    .replace(/<\s*br\s*\/?>/gi, "\n")
    .replace(/<\/\s*(p|div|section|article|blockquote|h[1-6])\s*>/gi, "\n\n")
    .replace(/<\s*li[^>]*>/gi, "\n- ")
    .replace(/<\/\s*(ul|ol)\s*>/gi, "\n")
    .replace(/<img\b[^>]*src=["']([^"']+)["'][^>]*>/gis, (_match, src) => `![](${src})`)
    .replace(/<\s*strong[^>]*>/gi, "**")
    .replace(/<\/\s*strong\s*>/gi, "**")
    .replace(/<\s*b\b[^>]*>/gi, "**")
    .replace(/<\/\s*b\s*>/gi, "**")
    .replace(/<\s*em[^>]*>/gi, "*")
    .replace(/<\/\s*em\s*>/gi, "*")
    .replace(/<\s*i\b[^>]*>/gi, "*")
    .replace(/<\/\s*i\s*>/gi, "*")
    .replace(/<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gis, (_match, href, text) => `[${stripHtml(text)}](${href})`)
    .replace(/<[^>]+>/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function markdownTable(headers, rows) {
  const lines = [
    `| ${headers.map(tableCell).join(" | ")} |`,
    `| ${headers.map(() => "---").join(" | ")} |`,
  ];
  for (const row of rows) {
    lines.push(`| ${row.map(tableCell).join(" | ")} |`);
  }
  return lines.join("\n");
}

function tableCell(value) {
  return formatFieldValue(value).replace(/\\/g, "\\\\").replace(/\|/g, "\\|").replace(/\s*\n\s*/g, "<br>");
}

function fieldLabel(field) {
  if (FIELD_LABELS.has(field)) return FIELD_LABELS.get(field);
  return field.split(".").at(-1).replace(/([a-z])([A-Z])/g, "$1 $2").replace(/_/g, " ");
}

function formatFieldValue(value) {
  if (value === undefined || value === null) return "";
  if (Array.isArray(value)) return value.map(formatFieldValue).join(", ");
  if (typeof value === "object") {
    const display = value.displayName || value.name;
    const unique = value.uniqueName || value.mailAddress;
    if (display && unique) return `${display} <${unique}>`;
    if (display) return String(display);
    return JSON.stringify(value);
  }
  return String(value).trim();
}

function looksLikeHtml(value) {
  return /<\/?[A-Za-z][^>]*>/.test(value);
}

function stripHtml(value) {
  return decodeHtml(String(value).replace(/<[^>]+>/g, ""));
}

function decodeHtml(value) {
  return String(value)
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeMarkdownInline(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/\[/g, "\\[").replace(/\]/g, "\\]");
}

function relationWorkItemId(url) {
  const match = String(url).match(/\/workItems\/(\d+)(?:\b|$)/i)
    || String(url).match(/\/_workitems\/edit\/(\d+)(?:\b|$)/i);
  return match ? Number(match[1]) : undefined;
}

function filenameFromUrl(url) {
  const parsed = new URL(url);
  for (const key of ["fileName", "filename", "name"]) {
    const value = parsed.searchParams.get(key);
    if (value) return path.posix.basename(decodeURIComponent(value));
  }
  const basename = path.posix.basename(parsed.pathname);
  return basename ? decodeURIComponent(basename) : undefined;
}

function filenameFromContentDisposition(value) {
  if (!value) return undefined;
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) return decodeURIComponent(encoded[1].replace(/^"|"$/g, ""));
  const plain = value.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : undefined;
}

function isImageFilename(filename) {
  return /\.(png|jpe?g|gif|webp|bmp)$/i.test(String(filename));
}

function attachmentIdFromUrl(url) {
  const match = String(url).match(/\/attachments\/([^/?#]+)/i);
  if (!match) throw new Error(`could not infer attachment id from ${url}`);
  return match[1];
}

function normalizeClip(rect) {
  return {
    x: Math.max(0, Math.floor(rect.x)),
    y: Math.max(0, Math.floor(rect.y)),
    width: Math.max(1, Math.ceil(rect.width)),
    height: Math.max(1, Math.ceil(rect.height)),
  };
}

function withJpgExtension(filename) {
  const parsed = path.parse(filename || "attachment");
  return `${parsed.name || "attachment"}.jpg`;
}

function safeAttachmentName(filename, contentType) {
  let name = path.posix.basename(filename || "attachment").replace(/[^A-Za-z0-9._ -]+/g, "-").replace(/^[ .-]+|[ .-]+$/g, "");
  if (!name) name = "attachment";
  if (!path.extname(name) && contentType) name += extensionForContentType(contentType);
  return name;
}

function extensionForContentType(contentType) {
  if (!contentType) return "";
  return IMAGE_EXTENSIONS.get(String(contentType).split(";", 1)[0].trim().toLowerCase()) || "";
}

async function uniquePath(filePath) {
  if (!(await exists(filePath))) return filePath;
  const parsed = path.parse(filePath);
  for (let index = 2; index < 10000; index += 1) {
    const candidate = path.join(parsed.dir, `${parsed.name}-${index}${parsed.ext}`);
    if (!(await exists(candidate))) return candidate;
  }
  throw new Error(`could not find unique path for ${filePath}`);
}

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function addApiVersion(rawUrl, apiVersion) {
  const url = new URL(rawUrl);
  if (![...url.searchParams.keys()].some((key) => key.toLowerCase() === "api-version")) {
    url.searchParams.append("api-version", apiVersion);
  }
  return url.toString();
}

function decodeDataUri(value) {
  const match = String(value).match(/^data:([^;,]+)?(;base64)?,(.*)$/s);
  if (!match) throw new Error("invalid data URI");
  const contentType = match[1] || undefined;
  if (match[2]) return { base64: match[3], contentType };
  return { base64: Buffer.from(decodeURIComponent(match[3]), "utf8").toString("base64"), contentType };
}

function relativeMarkdownPath(base, target) {
  return path.relative(base, target).split(path.sep).join("/");
}

function resolveOutputDir(outputDir) {
  if (!outputDir) throw new Error("outputDir is required");
  if (path.isAbsolute(outputDir)) return outputDir;
  return path.join(nodeRepl.cwd, outputDir);
}

function chunks(values, size) {
  const result = [];
  for (let index = 0; index < values.length; index += size) {
    result.push(values.slice(index, index + size));
  }
  return result;
}

function unique(values) {
  return [...new Set(values)];
}

function normalizeKey(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function slugify(value) {
  const slug = String(value).normalize("NFKD").replace(/[^\w\s-]/g, "").replace(/[_\s-]+/g, "-").replace(/^-|-$/g, "").toLowerCase();
  return slug.slice(0, 80) || "work-item";
}

function isEmpty(value) {
  return value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
}
