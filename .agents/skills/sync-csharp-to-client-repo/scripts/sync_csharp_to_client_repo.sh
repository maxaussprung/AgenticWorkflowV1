#!/usr/bin/env bash
set -euo pipefail

# ===== PROJECT CONFIGURATION =====
# Configure these variables for your project:
# DEFAULT_REMOTE_URL: The client repository Git URL
# DEFAULT_TARGET_BRANCH: The target branch in the client repository
# DEFAULT_SOURCE_BRANCH: The source branch to export from
# CLIENT_REPO_USERNAME env var: Username for client repo authentication
# CLIENT_REPO_PASSWORD env var: Password/PAT for client repo authentication
# ==================================

readonly DEFAULT_REMOTE_URL="{CLIENT-REPO-URL}"
readonly DEFAULT_TARGET_BRANCH="develop"
readonly DEFAULT_SOURCE_BRANCH="master"

DRY_RUN=0
REMOTE_URL="$DEFAULT_REMOTE_URL"
TARGET_BRANCH="$DEFAULT_TARGET_BRANCH"
SOURCE_BRANCH="$DEFAULT_SOURCE_BRANCH"
SOURCE_REF=""
SOURCE_REPO=""
COMMIT_MESSAGE=""
GIT_AUTH_ASKPASS_SCRIPT=""

usage() {
  cat <<'EOF'
Usage:
  sync_csharp_to_client_repo.sh [options]

Options:
  --dry-run                 Show the client repo diff without committing or pushing.
  --source-repo PATH        Source repository. Defaults to current git root.
  --source-branch BRANCH    Source branch to fetch from origin. Defaults to master.
  --source-ref REF          Exact source ref to export. Overrides origin/<source-branch>.
  --remote-url URL          Client Azure Repos Git URL.
  --target-branch BRANCH    Client repo target branch. Defaults to develop.
  --commit-message TEXT     Override the generated sync commit message.
  -h, --help                Show this help.

The script exports tracked files from <source-ref>:csharp and mirrors those files into the
client repository root. The sync is additive: it adds and updates files only and never deletes
data from the client repository. It never force-pushes.

Environment:
  CLIENT_REPO_USERNAME  Client repository Git username.
  CLIENT_REPO_PASSWORD  Client repository Git password or PAT.

When both variables are set, target-repo clone/pull/push operations use them through
GIT_ASKPASS and bypass saved credential helpers. The generated commit message lists completed
REQ-* IDs from source metadata, includes a short source-change summary, and strips Co-authored-by
trailers.
EOF
}

git_auth() {
  if [[ -n "$GIT_AUTH_ASKPASS_SCRIPT" ]]; then
    git -c credential.helper= -c "core.askPass=$GIT_AUTH_ASKPASS_SCRIPT" "$@"
  else
    git "$@"
  fi
}

configure_git_credentials() {
  if [[ -n "${CLIENT_REPO_USERNAME:-}" || -n "${CLIENT_REPO_PASSWORD:-}" ]]; then
    if [[ -z "${CLIENT_REPO_USERNAME:-}" || -z "${CLIENT_REPO_PASSWORD:-}" ]]; then
      echo "Set both CLIENT_REPO_USERNAME and CLIENT_REPO_PASSWORD, or unset both to use existing Git credentials." >&2
      exit 1
    fi

    GIT_AUTH_ASKPASS_SCRIPT="$TMP_DIR/git-askpass.sh"
    cat > "$GIT_AUTH_ASKPASS_SCRIPT" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  *Username*|*username*)
    printf '%s\n' "${CLIENT_REPO_USERNAME:?}"
    ;;
  *)
    printf '%s\n' "${CLIENT_REPO_PASSWORD:?}"
    ;;
esac
EOF
    chmod 700 "$GIT_AUTH_ASKPASS_SCRIPT"
    export GIT_TERMINAL_PROMPT=0
    echo "Git authentication: using CLIENT_REPO_USERNAME/CLIENT_REPO_PASSWORD."
  else
    echo "Git authentication: using existing Git credentials."
  fi
}

strip_coauthored_lines() {
  awk 'tolower($0) !~ /^[[:space:]]*co-authored-by:/ { print }'
}

extract_requirement_ids() {
  grep -Eo 'REQ-[A-Z0-9][A-Z0-9-]*' || true
}

collect_all_implemented_requirement_ids() {
  {
    git -C "$SOURCE_REPO" show "$SOURCE_SHA:openspec/track.md" 2>/dev/null \
      | awk '/\|[[:space:]]*done[[:space:]]*\|/ { print }' \
      || true

    git -C "$SOURCE_REPO" ls-tree -r --name-only "$SOURCE_SHA" -- docs/requirements/requirements 2>/dev/null \
      | while IFS= read -r requirement_file; do
          [[ "$requirement_file" == *.md ]] || continue
          if git -C "$SOURCE_REPO" show "$SOURCE_SHA:$requirement_file" 2>/dev/null \
            | grep -Eq '^status:[[:space:]]*"?done"?[[:space:]]*$'; then
            basename "$requirement_file" .md
          fi
        done \
      || true
  } | extract_requirement_ids | sort -u
}

find_previous_source_commit() {
  git -C "$CLIENT_DIR" log -50 --format=%B \
    | awk '/^Source commit: [0-9a-f]{7,40}$/ { print $3; exit }'
}

source_change_range_from_previous() {
  local previous_source_sha="$1"

  if [[ -n "$previous_source_sha" ]] \
    && git -C "$SOURCE_REPO" rev-parse --verify "$previous_source_sha^{commit}" >/dev/null 2>&1 \
    && git -C "$SOURCE_REPO" merge-base --is-ancestor "$previous_source_sha" "$SOURCE_SHA" 2>/dev/null; then
    printf '%s..%s\n' "$previous_source_sha" "$SOURCE_SHA"
  fi
}

collect_source_summary_subjects() {
  local source_change_range="$1"

  if [[ -n "$source_change_range" ]]; then
    git -C "$SOURCE_REPO" log --reverse --format=%s "$source_change_range" -- \
      csharp docs/requirements/requirements openspec/track.md 2>/dev/null \
      || true
  else
    git -C "$SOURCE_REPO" log -1 --format=%s "$SOURCE_SHA" -- 2>/dev/null \
      || true
  fi \
    | sed -E 's/^Merged PR [0-9]+: //; s/^Merge pull request #[0-9]+ from [^ ]+ //;' \
    | awk '
        NF == 0 { next }
        /^Merge / { next }
        /^chore\(slice\): claim / { next }
        /^chore\(slice\): link Azure claim / { next }
        !seen[$0]++ { print }
      '
}

collect_source_requirement_ids_from_history() {
  local source_change_range="$1"

  if [[ -n "$source_change_range" ]]; then
    git -C "$SOURCE_REPO" log --format=%B "$source_change_range" -- \
      csharp docs/requirements/requirements openspec/track.md 2>/dev/null \
      || true
  else
    git -C "$SOURCE_REPO" log -1 --format=%B "$SOURCE_SHA" -- 2>/dev/null \
      || true
  fi \
    | extract_requirement_ids \
    | sort -u
}

generate_commit_message() {
  local previous_source_sha="$1"
  local source_change_range="$2"
  local requirements
  local summary_subjects

  requirements="$(collect_all_implemented_requirement_ids)"
  if [[ -z "$requirements" ]]; then
    requirements="$(collect_source_requirement_ids_from_history "$source_change_range")"
  fi
  summary_subjects="$(collect_source_summary_subjects "$source_change_range" | awk 'NR <= 5 { print }')"

  {
    echo "Sync implemented {PROJECT-NAME} requirements"
    echo
    echo "Requirements:"
    if [[ -n "$requirements" ]]; then
      while IFS= read -r requirement_id; do
        [[ -n "$requirement_id" ]] && echo "- $requirement_id"
      done <<< "$requirements"
    else
      echo "- No completed REQ-* IDs detected in source metadata"
    fi
    echo
    echo "Summary:"
    if [[ -n "$summary_subjects" ]]; then
      while IFS= read -r subject; do
        [[ -n "$subject" ]] && echo "- $subject"
      done <<< "$summary_subjects"
    else
      echo "- Mirror tracked csharp/ contents from $SOURCE_REF into the client repository root."
    fi
    echo "- Source tree exported from {CLIENT-NAME} $SOURCE_REF at $SOURCE_SHORT_SHA."
    echo
    echo "Source repo: {CLIENT-NAME}"
    echo "Source ref: $SOURCE_REF"
    echo "Source commit: $SOURCE_SHA"
    if [[ -n "$previous_source_sha" ]]; then
      echo "Previous source commit: $previous_source_sha"
    fi
  } | strip_coauthored_lines
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --source-repo)
      SOURCE_REPO="${2:?Missing value for --source-repo}"
      shift 2
      ;;
    --source-branch)
      SOURCE_BRANCH="${2:?Missing value for --source-branch}"
      shift 2
      ;;
    --source-ref)
      SOURCE_REF="${2:?Missing value for --source-ref}"
      shift 2
      ;;
    --remote-url)
      REMOTE_URL="${2:?Missing value for --remote-url}"
      shift 2
      ;;
    --target-branch)
      TARGET_BRANCH="${2:?Missing value for --target-branch}"
      shift 2
      ;;
    --commit-message)
      COMMIT_MESSAGE="${2:?Missing value for --commit-message}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$SOURCE_REPO" ]]; then
  SOURCE_REPO="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi

if [[ -z "$SOURCE_REPO" || ! -d "$SOURCE_REPO/.git" ]]; then
  echo "Could not determine source git repository. Run from the source repo or pass --source-repo." >&2
  exit 1
fi

if [[ -z "$SOURCE_REF" ]]; then
  if git -C "$SOURCE_REPO" remote get-url origin >/dev/null 2>&1; then
    git -C "$SOURCE_REPO" fetch origin "$SOURCE_BRANCH"
    SOURCE_REF="origin/$SOURCE_BRANCH"
  else
    SOURCE_REF="$SOURCE_BRANCH"
  fi
fi

if ! git -C "$SOURCE_REPO" rev-parse --verify "$SOURCE_REF^{commit}" >/dev/null; then
  echo "Source ref does not resolve to a commit: $SOURCE_REF" >&2
  exit 1
fi

if ! git -C "$SOURCE_REPO" cat-file -e "$SOURCE_REF:csharp" 2>/dev/null; then
  echo "Source ref does not contain csharp/: $SOURCE_REF" >&2
  exit 1
fi

SOURCE_SHA="$(git -C "$SOURCE_REPO" rev-parse "$SOURCE_REF")"
SOURCE_SHORT_SHA="$(git -C "$SOURCE_REPO" rev-parse --short=12 "$SOURCE_REF")"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

EXPORT_DIR="$TMP_DIR/export"
CLIENT_DIR="$TMP_DIR/client"
mkdir -p "$EXPORT_DIR"
configure_git_credentials

echo "Source repo: $SOURCE_REPO"
echo "Source ref:  $SOURCE_REF ($SOURCE_SHORT_SHA)"
echo "Target repo: $REMOTE_URL"
echo "Target ref:  $TARGET_BRANCH"

git -C "$SOURCE_REPO" archive "$SOURCE_REF:csharp" | tar -x -C "$EXPORT_DIR"

git_auth clone --single-branch --branch "$TARGET_BRANCH" "$REMOTE_URL" "$CLIENT_DIR"
git_auth -C "$CLIENT_DIR" pull --ff-only origin "$TARGET_BRANCH"
PREVIOUS_SOURCE_SHA="$(find_previous_source_commit || true)"
SOURCE_CHANGE_RANGE="$(source_change_range_from_previous "$PREVIOUS_SOURCE_SHA")"

# Never delete data from the target (client) repository. The sync only adds new
# files and updates existing ones; any file that exists in the client repo but
# not under csharp/ is left untouched (no --delete).
rsync -a \
  --exclude ".git/" \
  "$EXPORT_DIR"/ \
  "$CLIENT_DIR"/

if [[ -z "$(git -C "$CLIENT_DIR" status --porcelain)" ]]; then
  echo "No changes to sync."
  exit 0
fi

echo
echo "Changed files:"
git -C "$CLIENT_DIR" status --short
git -C "$CLIENT_DIR" add -A
echo
echo "Diff summary:"
git -C "$CLIENT_DIR" diff --cached --stat

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "Dry run only. No commit or push was made."
  exit 0
fi

if [[ -z "$COMMIT_MESSAGE" ]]; then
  COMMIT_MESSAGE="$(generate_commit_message "$PREVIOUS_SOURCE_SHA" "$SOURCE_CHANGE_RANGE")"
fi

COMMIT_MESSAGE_FILE="$TMP_DIR/commit-message.txt"
printf '%s\n' "$COMMIT_MESSAGE" | strip_coauthored_lines > "$COMMIT_MESSAGE_FILE"
if [[ ! -s "$COMMIT_MESSAGE_FILE" ]]; then
  echo "Commit message is empty after removing Co-authored-by trailers." >&2
  exit 1
fi

git -C "$CLIENT_DIR" commit --file "$COMMIT_MESSAGE_FILE"
TARGET_COMMIT="$(git -C "$CLIENT_DIR" rev-parse --short=12 HEAD)"
git_auth -C "$CLIENT_DIR" push origin "HEAD:$TARGET_BRANCH"

echo
echo "Pushed $TARGET_COMMIT to $TARGET_BRANCH from source $SOURCE_SHORT_SHA."
