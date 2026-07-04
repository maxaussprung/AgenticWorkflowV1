#!/usr/bin/env python
"""Set an Azure DevOps work item's State (optionally its children too).
RUN:
  python .memory/tools/scripts/set_workitem_state.py <id> <state> [--with-children]
  e.g. ... 2197 Done            |  ... 2176 Done --with-children
States: Task = To Do|In Progress|Done ; PBI = New|Approved|Committed|Done.
PAT: env DEVOPS_PAT else ../../PATS/AZURE-PAT.json (never printed).
"""
import base64, json, os, sys, pathlib, urllib.request

ORG = "https://dev.azure.com/HPS-AT-GenAI"; PROJ = "Post"
if len(sys.argv) < 3:
    sys.exit("usage: set_workitem_state.py <id> <state> [--with-children]")
WID, STATE = sys.argv[1], sys.argv[2]
WITH_CHILDREN = "--with-children" in sys.argv
PAT = os.environ.get("DEVOPS_PAT") or json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "PATS" / "AZURE-PAT.json").read_text())["pat"]
AUTH = "Basic " + base64.b64encode((":" + PAT).encode()).decode()

def req(method, url, data=None, ctype="application/json"):
    b = None if data is None else json.dumps(data).encode()
    r = urllib.request.Request(url, data=b, method=method); r.add_header("Authorization", AUTH)
    if data is not None: r.add_header("Content-Type", ctype)
    with urllib.request.urlopen(r) as resp:
        raw = resp.read(); return json.loads(raw) if raw else {}

def set_state(idv):
    res = req("PATCH", f"{ORG}/{PROJ}/_apis/wit/workitems/{idv}?api-version=7.0",
              [{"op": "add", "path": "/fields/System.State", "value": STATE}], "application/json-patch+json")
    print(f"#{idv} -> {res['fields']['System.State']}")

targets = [WID]
if WITH_CHILDREN:
    d = req("GET", f"{ORG}/{PROJ}/_apis/wit/workitems/{WID}?$expand=relations&api-version=7.0")
    targets += [r["url"].split("/")[-1] for r in d.get("relations", [])
                if r.get("rel") == "System.LinkTypes.Hierarchy-Forward"]
for t in targets:
    set_state(t)
print("DONE")
