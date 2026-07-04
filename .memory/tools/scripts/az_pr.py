#!/usr/bin/env python
"""Inspect an Azure DevOps PR fast: status, reviewer votes (flags waiting-for-author / rejected),
and every comment thread (status + author + first line). Use before a fix/continue to see findings
and whether the PR is Waiting for Author. `--active` shows only unresolved threads.

RUN:  python .memory/tools/scripts/az_pr.py <pr-id> [--active]
PAT: env DEVOPS_PAT else ../../PATS/AZURE-PAT.json (never printed).
"""
import base64, json, os, sys, pathlib, urllib.request

ORG = "https://dev.azure.com/HPS-AT-GenAI"; PROJ = "Post"
REPO = "4d4baa85-9026-40ec-8f3e-1fa4d8e535ea"
if len(sys.argv) < 2:
    sys.exit("usage: az_pr.py <pr-id> [--active]")
PR = sys.argv[1]; ACTIVE_ONLY = "--active" in sys.argv
PAT = os.environ.get("DEVOPS_PAT") or json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "PATS" / "AZURE-PAT.json").read_text())["pat"]
AUTH = "Basic " + base64.b64encode((":" + PAT).encode()).decode()

def get(url):
    r = urllib.request.Request(url); r.add_header("Authorization", AUTH)
    with urllib.request.urlopen(r) as resp: return json.loads(resp.read())

VOTE = {10: "approved", 5: "approved-with-suggestions", 0: "no vote",
        -5: "WAITING FOR AUTHOR", -10: "REJECTED"}
pr = get(f"{ORG}/{PROJ}/_apis/git/repositories/{REPO}/pullRequests/{PR}?api-version=7.0")
print(f"PR #{PR} [{pr.get('status')}] {pr.get('title')}")
print(f"  {pr.get('sourceRefName')} -> {pr.get('targetRefName')}  | draft={pr.get('isDraft')}")
print("--- reviewers ---")
for rv in pr.get("reviewers", []):
    v = rv.get("vote", 0)
    print(f"  {rv.get('displayName')}: {VOTE.get(v, v)}{'  [required]' if rv.get('isRequired') else ''}")

th = get(f"{ORG}/{PROJ}/_apis/git/repositories/{REPO}/pullRequests/{PR}/threads?api-version=7.0")
print("--- comment threads ---")
for t in th.get("value", []):
    cs = [c for c in t.get("comments", []) if c.get("commentType") != "system"]
    if not cs: continue
    st = t.get("status")
    if ACTIVE_ONLY and st not in ("active", "pending"): continue
    a = cs[0].get("author", {}).get("displayName", "?")
    first = " ".join((cs[0].get("content") or "").split())[:140]
    print(f"  T{t['id']} [{st}] by {a} ({len(cs)} comment{'s' if len(cs)!=1 else ''}): {first}")
