---
name: sync-csharp-to-client-repo
description: Push only the tracked contents of this repository's csharp/ directory from master to the client repository {CLIENT-REPO-NAME} {CLIENT-REPO-BRANCH} branch. Use for the C# handoff/sync from the source repository to the client repository.
---

# Sync C# To Client Repo

Use this skill when the user asks to push, mirror, sync, or hand off the `csharp/` application
code to the client Azure Repos repository.

## Fixed Mapping

- Source repository: this {CLIENT-NAME} repository.
- Source tree: tracked contents of `csharp/` only.
- Source ref: `origin/master` after fetching `origin master`; fall back to local `master` only
  when the source remote is unavailable.
- Target repository:
  `{CLIENT-REPO-URL}`
- Target branch: `develop`.
- Target path: repository root. Do not create a nested `csharp/` directory in the client repo.

The Azure URL sometimes appears with `?version=GBdevelop`; that query is Azure UI state, not part
of the Git remote URL. The branch is `develop`.

## Safety Rules

- Use the bundled script unless it is impossible to run.
- The sync is **additive**: it only adds new files and updates existing ones. It never deletes
  data from the target (client) repository — files that exist in the client repo but not under
  `csharp/` are left untouched.
- Run `--dry-run` first and review the changed files before pushing.
- Export committed tracked files from the source ref; do not sync uncommitted or untracked files.
- Do not paste credentials, PATs, bearer tokens, or passwords into the prompt, script, or Git URL.
  The bundled script uses `CLIENT_REPO_USERNAME` and
  `CLIENT_REPO_PASSWORD` through `GIT_ASKPASS` when both are set. If neither is set, use
  existing Git Credential Manager, SSH/HTTPS credentials, or CI secrets. If only one variable is
  set, stop and fix the environment.
- Use the script's generated commit message. It must reference the completed `REQ-*` requirements
  found in source metadata, falling back to `REQ-*` IDs in the relevant source commit history only
  when completed metadata is unavailable. It must include a short source-change explanation and
  contain no `Co-authored-by` trailers.
- Never use `git push --force`, `--mirror`, or `--all`.
- If the push is rejected because the target branch moved or is protected, stop and report the
  rejection. Do not work around branch protection unless the user explicitly asks for a PR branch.

## Command

From the repository root:

```bash
bash .agents/skills/sync-csharp-to-client-repo/scripts/sync_csharp_to_client_repo.sh --dry-run
```

If the dry-run diff is expected and the user has already asked for the sync to be pushed:

```bash
bash .agents/skills/sync-csharp-to-client-repo/scripts/sync_csharp_to_client_repo.sh
```

Useful overrides:

```bash
bash .agents/skills/sync-csharp-to-client-repo/scripts/sync_csharp_to_client_repo.sh \
  --source-ref master \
  --target-branch develop \
  --remote-url "{CLIENT-REPO-URL}"
```

## Expected Result

The script clones the client repo into a temporary directory, copies the tracked contents of
`csharp/` from the source ref onto the client repo root (adding and updating files only, never
deleting client-only files), commits the diff, and pushes that commit to `origin/develop`.

For target-repo clone/pull/push authentication, the script prefers the credentials
saved in:

```bash
CLIENT_REPO_USERNAME
CLIENT_REPO_PASSWORD
```

The generated commit message has this shape:

```text
Sync implemented {PROJECT-NAME} requirements

Requirements:
- REQ-...

Summary:
- <short generated source-change explanation>
- Source tree exported from {CLIENT-NAME} <source-ref> at <source-sha>.

Source repo: {CLIENT-NAME}
Source ref: <source-ref>
Source commit: <full-source-sha>
Previous source commit: <full-previous-source-sha, when known>
```

The script removes any `Co-authored-by` trailer before committing, including when a manual
`--commit-message` override is supplied.

Report:

- Source ref and SHA used.
- Target repo and branch.
- Whether there were no changes, a dry-run diff, or a pushed commit.
- Any push/authentication/branch-protection failure.
