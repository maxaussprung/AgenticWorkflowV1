#!/usr/bin/env python
"""Check a PR's or branch's latest CI build/pipeline result (the "watch CI to green" step, see 07).

Needs the DevOps PAT with **Build (Read)** scope (added 2026-07-02, see 04). Given a PR id it resolves the
PR's source branch; given a branch name it uses it directly. Prints the latest build(s) status/result and,
for a failed build, the failing test names (best-effort via the test-results API).

RUN (master):
  DEVOPS_PAT=$(jq -r .pat .memory/PATS/AZURE-PAT.json) python .memory/tools/scripts/az_build.py <pr-id|branch> [--tests] [--logs]
Examples:  az_build.py 1601        az_build.py feature/foo --tests        az_build.py 1601 --logs
  --tests  best-effort failing-test names (test API may 401).
  --logs   tail the failed timeline steps' logs (the reliable way to see WHY a build failed).
"""
import base64, json, os, sys, urllib.request, urllib.parse, pathlib

ORG = "https://dev.azure.com/HPS-AT-GenAI"; PROJ = "Post"
REPO = "4d4baa85-9026-40ec-8f3e-1fa4d8e535ea"
ARG = sys.argv[1] if len(sys.argv) > 1 else ""
WANT_TESTS = "--tests" in sys.argv
WANT_LOGS = "--logs" in sys.argv
if not ARG:
    sys.exit("usage: az_build.py <pr-id|branch> [--tests]")

PAT = os.environ.get("DEVOPS_PAT") or json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / "PATS" / "AZURE-PAT.json").read_text())["pat"]
AUTH = "Basic " + base64.b64encode((":" + PAT).encode()).decode()

def get(url):
    r = urllib.request.Request(url); r.add_header("Authorization", AUTH)
    with urllib.request.urlopen(r) as resp:
        return json.load(resp)

def get_text(url):
    r = urllib.request.Request(url); r.add_header("Authorization", AUTH)
    with urllib.request.urlopen(r) as resp:
        return resp.read().decode("utf-8", "replace")

# Resolve the ref(s): a bare number => PR id (Azure PR-validation builds run against the MERGE ref
# refs/pull/<id>/merge, not the source branch — check both), else treat as a branch name.
if ARG.isdigit():
    pr = get(f"{ORG}/{PROJ}/_apis/git/repositories/{REPO}/pullRequests/{ARG}?api-version=7.0")
    print(f"PR #{ARG} [{pr['status']}] {pr['title']}\n  source: {pr['sourceRefName']}")
    refs = [f"refs/pull/{ARG}/merge", pr["sourceRefName"]]
else:
    refs = [ARG if ARG.startswith("refs/") else f"refs/heads/{ARG}"]
    print(f"branch: {refs[0]}")

builds = []
for ref in refs:
    builds = get(f"{ORG}/{PROJ}/_apis/build/builds?branchName={urllib.parse.quote(ref, safe='')}"
                 f"&$top=5&api-version=7.0").get("value", [])
    if builds:
        print(f"  (builds on {ref})"); break
if not builds:
    print("  no builds for this PR/branch yet (queued/none)"); sys.exit(0)

for b in builds[:5]:
    print(f"  build {b['id']}  {b['status']:>10}  {str(b.get('result','-')):>12}  "
          f"{b.get('definition',{}).get('name','')}  {b.get('finishTime', b.get('queueTime',''))[:19]}  "
          f"{b['sourceVersion'][:8]}")

latest = builds[0]
if latest.get("result") == "failed" and WANT_LOGS:
    # The reliable "why did it fail" path: read the failed timeline records' logs and print the tail.
    try:
        tl = get(f"{ORG}/{PROJ}/_apis/build/builds/{latest['id']}/timeline?api-version=7.0").get("records", [])
        failed = [r for r in tl if r.get("result") == "failed" and r.get("log", {}).get("url")]
        if not failed:
            print("  (no failed timeline records with logs — build may have failed before running steps)")
        for rec in failed:
            print(f"\n  ===== FAILED STEP: {rec.get('name')} ({rec.get('type')}) — log tail =====")
            lines = get_text(rec["log"]["url"]).splitlines()
            for ln in lines[-40:]:
                print("   " + ln)
    except Exception as e:
        print("    (could not fetch step logs:", e, ")")

if latest.get("result") == "failed" and WANT_TESTS:
    # best-effort: failing tests for the latest build
    try:
        runs = get(f"{ORG}/{PROJ}/_apis/test/runs?buildUri={urllib.parse.quote(latest['uri'], safe='')}"
                   f"&api-version=7.0").get("value", [])
        for run in runs:
            res = get(f"{ORG}/{PROJ}/_apis/test/runs/{run['id']}/results?outcomes=Failed&api-version=7.0").get("value", [])
            for r in res:
                print(f"    FAILED: {r.get('automatedTestName') or r.get('testCaseTitle')}")
    except Exception as e:
        print("    (could not fetch failing tests:", e, ")")
