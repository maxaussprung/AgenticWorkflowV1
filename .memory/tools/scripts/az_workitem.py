#!/usr/bin/env python
"""Inspect an Azure DevOps work item fast: state/type/creator, child work items (with their state),
linked PR(s), Description + AcceptanceCriteria (HTML stripped), and every inline/attached image URL.
`--comments` prints discussion comments; `--download <dir>` pulls all images. Replaces the
hand-rolled curl+python we ran every fix.

RUN:
  python .memory/tools/scripts/az_workitem.py <id> [--comments] [--download <dir>]
PAT: env DEVOPS_PAT if set, else read from ../../PATS/AZURE-PAT.json (never printed).
"""
import base64, json, re, sys, html, pathlib, urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ORG = "https://dev.azure.com/HPS-AT-GenAI"; PROJ = "Post"
if len(sys.argv) < 2:
    sys.exit("usage: az_workitem.py <id> [--download <dir>]")
WID = sys.argv[1]
DL = pathlib.Path(sys.argv[sys.argv.index("--download") + 1]) if "--download" in sys.argv else None
SHOW_COMMENTS = "--comments" in sys.argv

import os
PAT = os.environ.get("DEVOPS_PAT") or json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "PATS" / "AZURE-PAT.json").read_text())["pat"]
AUTH = "Basic " + base64.b64encode((":" + PAT).encode()).decode()

def get(url):
    r = urllib.request.Request(url); r.add_header("Authorization", AUTH)
    with urllib.request.urlopen(r) as resp: return resp.read()

def wi(idv):
    return json.loads(get(f"{ORG}/{PROJ}/_apis/wit/workitems/{idv}?$expand=relations&api-version=7.0"))

def strip(t):
    if not t: return "(empty)", []
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', t)
    txt = re.sub(r"<[^>]+>", " ", t); txt = html.unescape(txt)
    txt = re.sub(r"[ \t]+", " ", txt); txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip(), imgs

d = wi(WID); f = d["fields"]
print(f"#{WID} [{f.get('System.State')}] {f.get('System.WorkItemType')} — {f.get('System.Title')}")
print("CreatedBy:", f.get("System.CreatedBy", {}).get("displayName"))
imgs_all = []
for key in ["System.Description", "Microsoft.VSTS.TCM.ReproSteps", "Microsoft.VSTS.Common.AcceptanceCriteria"]:
    if key in f:
        txt, imgs = strip(f[key]); imgs_all += imgs
        print(f"--- {key.split('.')[-1]} ---\n{txt}")
        for i in imgs: print("  IMG:", i)
children, prs, atts = [], [], []
for r in d.get("relations", []):
    rel, url = r.get("rel"), r.get("url", "")
    if rel == "System.LinkTypes.Hierarchy-Forward": children.append(url.split("/")[-1])
    elif "PullRequest" in url: prs.append(url.split("%2F")[-1])
    elif rel == "AttachedFile": atts.append((r.get("attributes", {}).get("name"), url)); imgs_all.append(url)
if children:
    print("--- children ---")
    for cid in children:
        cf = wi(cid)["fields"]
        print(f"  #{cid} [{cf.get('System.State')}] {cf.get('System.Title')}")
if prs: print("--- PRs ---", ", ".join(prs))
if atts:
    print("--- attached files ---")
    for name, url in atts: print("  ", name, url)
if SHOW_COMMENTS:
    print("--- discussion comments ---")
    try:
        cj = json.loads(get(f"{ORG}/{PROJ}/_apis/wit/workItems/{WID}/comments?api-version=7.0-preview.3"))
        for c in cj.get("comments", []):
            who = c.get("createdBy", {}).get("displayName", "?"); when = (c.get("createdDate") or "")[:16]
            txt = re.sub(r"<[^>]+>", " ", c.get("text") or ""); txt = html.unescape(re.sub(r"\s+", " ", txt)).strip()
            print(f"  [{when}] {who}: {txt[:200]}")
    except Exception as e:
        print("  (comments fetch failed:", e, ")")
if DL:
    DL.mkdir(parents=True, exist_ok=True)
    for n, url in enumerate(imgs_all):
        u = url if "api-version" in url else url + ("&" if "?" in url else "?") + "api-version=7.0"
        out = DL / f"wi{WID}_{n}.png"; out.write_bytes(get(u)); print("downloaded", out)
