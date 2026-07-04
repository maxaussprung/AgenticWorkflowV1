#!/usr/bin/env python
"""Reusable Azure DevOps PR comment poster — covers ALL three comment kinds:
  • proof   (upload N screenshots + captioned @mention comment + set work item Done)
  • rebuttal (no images: an evidenced "no change needed" comment, set Done pending reply — see 06 §7)
  • plain   (any markdown comment, with/without @mention, with/without status change)
One tool, config-driven — do NOT create per-PR/per-ticket one-off scripts (see tools/README rules).
Encodes ../../01-proof-reporting-protocol.md + ../../06-azure-devops-templates.md — keep in sync.

RUN (master only):
  DEVOPS_PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json) python .memory/tools/scripts/post_to_pr.py <shots_dir>
(<shots_dir> only needed when CONFIG["shots"] is non-empty.) Never print the PAT.
"""
import base64, json, os, sys, time, urllib.request, pathlib

ORG = "https://dev.azure.com/HPS-AT-GenAI"; PROJ = "Post"
REPO = "4d4baa85-9026-40ec-8f3e-1fa4d8e535ea"
GUID = {"yujiao": "deee0071-c83d-6e32-8bb6-b8b24d362fd5",   # UX
        "tobias": "ed127298-d005-60ef-a1e7-24650e2dff64"}   # tester
SHOTS_DIR = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")

# ================================ CONFIG ================================
CONFIG = {
    "pr": "1601",
    "workitem": "2211",
    "header": "UX #2211 — Offene Inkassofälle heading → h4 — done",
    "fixes_line": True,
    "originator": "yujiao",
    "intro": ("The Offene Inkassofälle data-table section heading now uses the Amarillo **h4** Typography "
              "variant (verified it renders as `<h4>` / role heading level 4)."),
    "shots": [
        ("1 · List 1280×1024 — h4 section heading", "proof_2202_list_1280.png"),
        ("2 · List whole page", "proof_2202_list_full.png"),
    ],
    "set_state": "Done",
}
# =======================================================================

PAT = os.environ.get("DEVOPS_PAT") or json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "PATS" / "AZURE-PAT.json").read_text())["pat"]
AUTH = "Basic " + base64.b64encode((":" + PAT).encode()).decode()

def req(method, url, data=None, ctype="application/json"):
    b = None if data is None else (data if isinstance(data, (bytes, bytearray)) else json.dumps(data).encode())
    r = urllib.request.Request(url, data=b, method=method); r.add_header("Authorization", AUTH)
    if data is not None: r.add_header("Content-Type", ctype)
    with urllib.request.urlopen(r) as resp:
        raw = resp.read(); return json.loads(raw) if raw else {}

def upload(fname):
    data = (SHOTS_DIR / fname).read_bytes()
    name = f"{fname.replace('.png','')}_{int(time.time()*1000)}.png"
    res = req("POST", f"{ORG}/{PROJ}/_apis/git/repositories/{REPO}/pullRequests/{CONFIG['pr']}/attachments/{name}?api-version=7.1-preview.1",
              data, "application/octet-stream")
    print("uploaded", fname); return res["url"]

wi_url = f"{ORG}/{PROJ}/_workitems/edit/{CONFIG['workitem']}" if CONFIG.get("workitem") else None
lines = [f"**{CONFIG['header']}**", ""]
if CONFIG.get("fixes_line") and wi_url:
    lines += [f"Fixes [#{CONFIG['workitem']}]({wi_url}).", ""]
# originator: a single key ("yujiao") for a task response, OR a list (["tobias","yujiao"]) to tag ALL
# required reviewers on an initial/new-slice comment (see 01 "Who to @tag").
_orig = CONFIG.get("originator")
if _orig:
    _keys = _orig if isinstance(_orig, list) else [_orig]
    mention = " ".join(f"@<{GUID[k]}>" for k in _keys) + " "
else:
    mention = ""
lines += [mention + CONFIG["intro"], ""]
for caption, fname in CONFIG["shots"]:
    lines += [f"**{caption}**", "", f"![]({upload(fname)})", ""]
content = "\n".join(lines).rstrip() + "\n"

res = req("POST", f"{ORG}/{PROJ}/_apis/git/repositories/{REPO}/pullRequests/{CONFIG['pr']}/threads?api-version=7.0",
          {"comments": [{"parentCommentId": 0, "commentType": 1, "content": content}], "status": 1})
print("thread", res.get("id"))
if CONFIG.get("set_state") and CONFIG.get("workitem"):
    res = req("PATCH", f"{ORG}/{PROJ}/_apis/wit/workitems/{CONFIG['workitem']}?api-version=7.0",
              [{"op": "add", "path": "/fields/System.State", "value": CONFIG["set_state"]}], "application/json-patch+json")
    print("workitem", CONFIG["workitem"], "->", res["fields"]["System.State"])
print("DONE")
