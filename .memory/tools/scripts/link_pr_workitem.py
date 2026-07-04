#!/usr/bin/env python
"""Link an existing Azure DevOps PR to a work item (adds the PR as an ArtifactLink on the work item).

WHY: `complete-implementation-slice` normally creates the PR WITH the work-item ref, but in fix/continue
flows (or when a PR was opened without the link) you need to attach one after the fact. Reusable +
parametrised (pr id + work-item id) — NOT a per-PR one-off (see tools/README rules).

RUN (master only; PAT referenced by path, never printed):
  DEVOPS_PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json) \
    python .memory/tools/scripts/link_pr_workitem.py <pr-id> <workitem-id>
Idempotent-ish: if the link already exists Azure returns 400 "relation already exists" — treated as OK.
"""
import base64, json, os, sys, urllib.request, urllib.error, pathlib

ORG = "https://dev.azure.com/HPS-AT-GenAI"; PROJ = "Post"
REPO = "4d4baa85-9026-40ec-8f3e-1fa4d8e535ea"
if len(sys.argv) < 3:
    sys.exit("usage: link_pr_workitem.py <pr-id> <workitem-id>")
PR, WI = sys.argv[1], sys.argv[2]

PAT = os.environ.get("DEVOPS_PAT") or json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "PATS" / "AZURE-PAT.json").read_text())["pat"]
AUTH = "Basic " + base64.b64encode((":" + PAT).encode()).decode()

def req(method, url, data=None, ctype="application/json"):
    b = None if data is None else json.dumps(data).encode()
    r = urllib.request.Request(url, data=b, method=method); r.add_header("Authorization", AUTH)
    if data is not None: r.add_header("Content-Type", ctype)
    with urllib.request.urlopen(r) as resp:
        raw = resp.read(); return json.loads(raw) if raw else {}

# Artifact link needs the project GUID (not the name) in the vstfs URI.
proj_id = req("GET", f"{ORG}/_apis/projects/{PROJ}?api-version=7.0")["id"]
artifact = f"vstfs:///Git/PullRequestId/{proj_id}%2F{REPO}%2F{PR}"
patch = [{"op": "add", "path": "/relations/-", "value": {
    "rel": "ArtifactLink", "url": artifact, "attributes": {"name": "Pull Request"}}}]
try:
    res = req("PATCH", f"{ORG}/{PROJ}/_apis/wit/workitems/{WI}?api-version=7.0", patch,
              "application/json-patch+json")
    print(f"linked PR #{PR} -> work item #{WI} (rev {res.get('rev')})")
except urllib.error.HTTPError as e:
    msg = e.read().decode(errors="replace")
    if "already exists" in msg or e.code == 400:
        print(f"PR #{PR} already linked to work item #{WI} (ok)")
    else:
        raise
