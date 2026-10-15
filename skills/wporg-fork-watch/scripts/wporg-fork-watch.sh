#!/usr/bin/env bash
#
# wporg-fork-watch.sh — watch a WordPress.org plugin's SVN tags and port each new
# release into your fork through an agent-authored pull request.
#
# Flow (one watch = one config file):
#   svn ls <slug>/tags → new tags above the newest imported vendor tag?
#     → export each tag onto VENDOR_BRANCH (one commit + git tag per release)
#     → push the vendor branch and tags
#     → fresh worktree PR_BRANCH_PREFIX<version> from BASE_REMOTE/BASE_BRANCH
#     → git merge --no-commit <tag>, then AGENT_CMD finishes the merge under POLICY_FILE
#       (keeps the useful upstream changes, drops what the policy says to drop,
#       writes SYNC_SUMMARY.md, commits; never pushes)
#     → LINT_CMD gate → push → gh pr create (body = SYNC_SUMMARY.md)
#     → REVIEW_CMD <pr-url> (default: a second agent pass posted as a GitHub review)
#     → NOTIFY_CMD (message on stdin) and/or SLACK_WEBHOOK_URL
#
# State lives in git and GitHub, not in a state file: the newest TAG_PREFIX* tag
# says what was imported, and a PR whose head is PR_BRANCH_PREFIX<version> says
# what was handed off. A crash between the two is picked up on the next run.
#
# Usage:
#   wporg-fork-watch.sh <name> [--dry-run] [--keep] [--version X.Y.Z] [--config <file>]
#     <name>        config file ~/.config/wporg-fork-watch/<name>.env (or --config path)
#     --dry-run     import tags locally and run the agent, but never push, open a PR,
#                   review, or notify; implies --keep
#     --keep        leave the worktrees in place for inspection
#     --version     treat this SVN tag as the target even if already imported (re-port)
#     --list        print the SVN tags and the imported state, then exit
#
# Exit 0 when up to date. Non-zero on any failure so a cron wrapper can alert.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/wporg-fork-watch"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wporg-fork-watch"

NAME=""; CONFIG=""; DRY_RUN=0; KEEP=0; FORCE_VERSION=""; LIST_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; KEEP=1; shift ;;
    --keep) KEEP=1; shift ;;
    --version) FORCE_VERSION="${2:?--version needs a tag}"; shift 2 ;;
    --config) CONFIG="${2:?--config needs a path}"; shift 2 ;;
    --list) LIST_ONLY=1; shift ;;
    -h|--help) sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) [[ -z "$NAME" ]] || { echo "one name only" >&2; exit 2; }; NAME="$1"; shift ;;
  esac
done
[[ -n "$NAME" || -n "$CONFIG" ]] || { echo "usage: wporg-fork-watch.sh <name> [--dry-run]" >&2; exit 2; }
[[ -n "$CONFIG" ]] || CONFIG="$CONFIG_DIR/$NAME.env"
[[ -n "$NAME" ]] || NAME="$(basename "$CONFIG" .env)"
[[ -f "$CONFIG" ]] || { echo "no config at $CONFIG (see examples/pmpro-crontrol.env)" >&2; exit 2; }

log() { printf '%s [wporg-fork-watch:%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$NAME" "$*"; }
die() { log "ERROR: $*"; exit 1; }

# ---- config ----
# shellcheck disable=SC1090
source "$CONFIG"
: "${SLUG:?SLUG (wordpress.org plugin slug) is required}"
: "${REPO:?REPO (local checkout of the fork) is required}"
BASE_BRANCH="${BASE_BRANCH:-main}"
VENDOR_BRANCH="${VENDOR_BRANCH:-$SLUG}"
TAG_PREFIX="${TAG_PREFIX:-$SLUG-}"
PR_BRANCH_PREFIX="${PR_BRANCH_PREFIX:-upstream/}"
PUSH_REMOTE="${PUSH_REMOTE:-origin}"
PR_LABEL="${PR_LABEL:-upstream-sync}"
POLICY_FILE="${POLICY_FILE:-$SKILL_DIR/examples/default.policy.md}"
# Default agent: edits auto-accepted, shell limited to the tools a merge needs; no network, no package installs.
AGENT_TOOLS="${AGENT_TOOLS:-Read,Edit,Write,Glob,Grep,Bash(git:*),Bash(php:*),Bash(grep:*),Bash(ls:*),Bash(find:*),Bash(cat:*),Bash(diff:*),Bash(head:*),Bash(tail:*),Bash(wc:*),Bash(sed:*)}"
AGENT_CMD="${AGENT_CMD:-claude -p --model opus --effort high --permission-mode acceptEdits --allowedTools \"$AGENT_TOOLS\"}"
AGENT_TIMEOUT="${AGENT_TIMEOUT:-3600}"
REVIEW_CMD="${REVIEW_CMD:-builtin}"
REVIEW_AGENT_CMD="${REVIEW_AGENT_CMD:-claude -p --model opus --effort medium}"
REVIEW_TIMEOUT="${REVIEW_TIMEOUT:-1500}"
LINT_CMD="${LINT_CMD:-builtin}"
NOTIFY_CMD="${NOTIFY_CMD:-}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
WT_ROOT="${WT_ROOT:-${REPO%/}-wt}"
SVN_BASE="${SVN_BASE:-https://plugins.svn.wordpress.org}"
PR_FOOTER="${PR_FOOTER:-🤖 Generated with [Claude Code](https://claude.com/claude-code)}"
UPSTREAM_NAME="${UPSTREAM_NAME:-$SLUG}"

[[ -d "$REPO/.git" || -f "$REPO/.git" ]] || die "not a git checkout: $REPO"
[[ -f "$POLICY_FILE" ]] || die "policy file not found: $POLICY_FILE"
for bin in svn git gh jq; do command -v "$bin" >/dev/null || die "missing dependency: $bin"; done
unset CLAUDECODE 2>/dev/null || true
mkdir -p "$LOG_DIR"

# Remote that holds the branch PRs merge into; a fork-model checkout has upstream + origin.
if [[ -z "${BASE_REMOTE:-}" ]]; then
  if git -C "$REPO" remote get-url upstream >/dev/null 2>&1; then BASE_REMOTE=upstream; else BASE_REMOTE="$PUSH_REMOTE"; fi
fi
remote_slug() { git -C "$REPO" remote get-url "$1" | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##'; }
PR_REPO="${PR_REPO:-$(remote_slug "$BASE_REMOTE")}"
PUSH_SLUG="$(remote_slug "$PUSH_REMOTE")"
PR_HEAD_PREFIX=""
[[ "$PUSH_SLUG" == "$PR_REPO" ]] || PR_HEAD_PREFIX="${PUSH_SLUG%%/*}:"

log "=== start slug=$SLUG repo=$REPO base=$BASE_REMOTE/$BASE_BRANCH vendor=$VENDOR_BRANCH push=$PUSH_REMOTE pr_repo=$PR_REPO dry_run=$DRY_RUN ==="

# ---- what SVN has vs what we imported ----
semver_sort() { sort -t. -k1,1n -k2,2n -k3,3n -k4,4n; }
SVN_TAGS=$(svn ls "$SVN_BASE/$SLUG/tags/" 2>/dev/null | sed 's#/$##' | grep -E '^[0-9]+(\.[0-9]+)+$' | semver_sort) \
  || die "svn ls failed for $SVN_BASE/$SLUG/tags/"
[[ -n "$SVN_TAGS" ]] || die "no release tags found for $SLUG"
SVN_LATEST=$(tail -1 <<<"$SVN_TAGS")

git -C "$REPO" fetch --quiet --tags "$PUSH_REMOTE" 2>/dev/null || log "warn: fetch $PUSH_REMOTE failed (offline or no access); using local refs"
[[ "$BASE_REMOTE" == "$PUSH_REMOTE" ]] || git -C "$REPO" fetch --quiet "$BASE_REMOTE" "$BASE_BRANCH" 2>/dev/null || log "warn: fetch $BASE_REMOTE/$BASE_BRANCH failed"
IMPORTED=$(git -C "$REPO" tag -l "${TAG_PREFIX}*" | sed "s#^${TAG_PREFIX}##" | grep -E '^[0-9]+(\.[0-9]+)+$' | semver_sort | tail -1 || true)
log "svn latest $SVN_LATEST; newest imported vendor tag ${IMPORTED:-none}"

if [[ $LIST_ONLY -eq 1 ]]; then
  printf 'svn tags:\n%s\nimported: %s\n' "$SVN_TAGS" "${IMPORTED:-none}"; exit 0
fi

ver_gt() { [[ "$1" != "$2" && "$(printf '%s\n%s\n' "$1" "$2" | semver_sort | tail -1)" == "$1" ]]; }

NEW_TAGS=""
if [[ -n "$FORCE_VERSION" ]]; then
  grep -qx "$FORCE_VERSION" <<<"$SVN_TAGS" || die "$FORCE_VERSION is not an SVN tag of $SLUG"
  TARGET="$FORCE_VERSION"
  git -C "$REPO" rev-parse -q --verify "refs/tags/${TAG_PREFIX}${TARGET}" >/dev/null || NEW_TAGS="$TARGET"
else
  while read -r t; do
    [[ -z "$IMPORTED" ]] && NEW_TAGS+="$t"$'\n' && continue
    ver_gt "$t" "$IMPORTED" && NEW_TAGS+="$t"$'\n'
  done <<<"$SVN_TAGS"
  NEW_TAGS=$(sed '/^$/d' <<<"$NEW_TAGS")
  TARGET="${NEW_TAGS:+$(tail -1 <<<"$NEW_TAGS")}"
  TARGET="${TARGET:-$IMPORTED}"
fi

# ---- is the target already handled? ----
pr_for_version() { # prints "<state> <url>" of the PR whose head is the version branch, or nothing
  gh pr list --repo "$PR_REPO" --state all --head "${PR_BRANCH_PREFIX}$1" --limit 1 --json state,url \
    --jq '.[] | "\(.state) \(.url)"' 2>/dev/null || true
}
tag_in_base() { git -C "$REPO" merge-base --is-ancestor "refs/tags/${TAG_PREFIX}$1" "$BASE_REMOTE/$BASE_BRANCH" 2>/dev/null; }

if [[ -z "$NEW_TAGS" && -z "$FORCE_VERSION" ]]; then
  if [[ -z "$IMPORTED" ]]; then die "nothing imported and nothing new: check SLUG/TAG_PREFIX"; fi
  if tag_in_base "$IMPORTED"; then log "up to date: $IMPORTED is in $BASE_REMOTE/$BASE_BRANCH"; exit 0; fi
  existing=$(pr_for_version "$IMPORTED")
  if [[ -n "$existing" ]]; then log "up to date: $IMPORTED already has a PR ($existing)"; exit 0; fi
  log "vendor tag $IMPORTED was imported but never handed off; resuming the port"
fi

# No stacking: one open sync PR at a time.
OPEN_SYNC=$(gh pr list --repo "$PR_REPO" --state open --label "$PR_LABEL" --limit 5 --json url,headRefName \
  --jq ".[] | select(.headRefName | startswith(\"$PR_BRANCH_PREFIX\")) | .url" 2>/dev/null | head -1 || true)
if [[ -n "$OPEN_SYNC" && $DRY_RUN -eq 0 ]]; then
  log "an open $PR_LABEL PR already exists, not stacking another: $OPEN_SYNC"; exit 0
fi

# ---- worktrees ----
VENDOR_WT="$WT_ROOT/$NAME-vendor"
SYNC_BRANCH="${PR_BRANCH_PREFIX}${TARGET}"
SYNC_WT="$WT_ROOT/$NAME-$TARGET"
PUSHED=0
cleanup() {
  local rc=$?
  if [[ $KEEP -eq 0 ]]; then
    for wt in "$VENDOR_WT" "$SYNC_WT"; do
      [[ -e "$wt" ]] && { git -C "$REPO" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"; }
    done
    git -C "$REPO" worktree prune 2>/dev/null || true
    if [[ $PUSHED -eq 1 || $rc -ne 0 ]] && git -C "$REPO" show-ref --verify --quiet "refs/heads/$SYNC_BRANCH"; then
      git -C "$REPO" branch -D "$SYNC_BRANCH" >/dev/null 2>&1 || true
    fi
  else
    log "worktrees kept: $VENDOR_WT $SYNC_WT"
  fi
  [[ $rc -eq 0 ]] || log "=== failed (exit $rc) ==="
}
trap cleanup EXIT
mkdir -p "$WT_ROOT"
for wt in "$VENDOR_WT" "$SYNC_WT"; do
  [[ -e "$wt" ]] && { git -C "$REPO" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"; }
done
git -C "$REPO" worktree prune

# ---- import new tags onto the vendor branch ----
if [[ -n "$NEW_TAGS" ]]; then
  if git -C "$REPO" show-ref --verify --quiet "refs/heads/$VENDOR_BRANCH"; then
    git -C "$REPO" worktree add --quiet "$VENDOR_WT" "$VENDOR_BRANCH"
  elif git -C "$REPO" show-ref --verify --quiet "refs/remotes/$PUSH_REMOTE/$VENDOR_BRANCH"; then
    git -C "$REPO" worktree add --quiet -b "$VENDOR_BRANCH" "$VENDOR_WT" "$PUSH_REMOTE/$VENDOR_BRANCH"
  else
    git -C "$REPO" worktree add --quiet --detach "$VENDOR_WT"
    git -C "$VENDOR_WT" checkout --quiet --orphan "$VENDOR_BRANCH"
    git -C "$VENDOR_WT" rm -rfq --cached . 2>/dev/null || true
    log "created orphan vendor branch $VENDOR_BRANCH"
  fi
  while read -r v; do
    [[ -n "$v" ]] || continue
    log "svn export $SLUG/tags/$v → $VENDOR_BRANCH"
    find "$VENDOR_WT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
    svn export --quiet --force "$SVN_BASE/$SLUG/tags/$v" "$VENDOR_WT" || die "svn export of $v failed"
    git -C "$VENDOR_WT" add -A
    git -C "$VENDOR_WT" -c user.name="${GIT_AUTHOR_NAME:-wporg-fork-watch}" -c user.email="${GIT_AUTHOR_EMAIL:-wporg-fork-watch@localhost}" \
      commit --quiet --allow-empty -m "$UPSTREAM_NAME $v (pristine export of $SVN_BASE/$SLUG/tags/$v)"
    git -C "$REPO" tag "${TAG_PREFIX}${v}" "$VENDOR_BRANCH"
  done <<<"$NEW_TAGS"
  if [[ $DRY_RUN -eq 0 ]]; then
    git -C "$REPO" push --quiet "$PUSH_REMOTE" "$VENDOR_BRANCH" --tags || die "push of $VENDOR_BRANCH/tags to $PUSH_REMOTE failed"
    log "pushed $VENDOR_BRANCH and tags to $PUSH_REMOTE"
  fi
fi
TARGET_TAG="${TAG_PREFIX}${TARGET}"
PREV=$(git -C "$REPO" tag -l "${TAG_PREFIX}*" | sed "s#^${TAG_PREFIX}##" | grep -E '^[0-9]+(\.[0-9]+)+$' | semver_sort | awk -v t="$TARGET" '$0 == t { exit } { p = $0 } END { print p }')
PREV_TAG="${PREV:+${TAG_PREFIX}${PREV}}"
if tag_in_base "$TARGET" && [[ -z "$FORCE_VERSION" ]]; then log "$TARGET_TAG already merged into $BASE_BRANCH"; exit 0; fi

# ---- sync worktree: start the merge, hand the rest to the agent ----
git -C "$REPO" show-ref --verify --quiet "refs/heads/$SYNC_BRANCH" && git -C "$REPO" branch -D "$SYNC_BRANCH" >/dev/null
git -C "$REPO" worktree add --quiet --no-track -b "$SYNC_BRANCH" "$SYNC_WT" "$BASE_REMOTE/$BASE_BRANCH"
BASE_SHA=$(git -C "$SYNC_WT" rev-parse HEAD)
MERGE_STATE="clean"
if ! git -C "$SYNC_WT" merge --no-ff --no-commit "$TARGET_TAG" >/dev/null 2>&1; then
  MERGE_STATE="conflicts"
fi
CONFLICTS=$(git -C "$SYNC_WT" diff --name-only --diff-filter=U 2>/dev/null || true)
log "merge of $TARGET_TAG started: $MERGE_STATE${CONFLICTS:+ ($(wc -l <<<"$CONFLICTS") files)}"

UPSTREAM_STAT=$( [[ -n "$PREV_TAG" ]] && git -C "$REPO" diff --stat "$PREV_TAG" "$TARGET_TAG" | tail -60 || echo "(first import, no previous tag)")
README_DIFF=$( [[ -n "$PREV_TAG" ]] && git -C "$REPO" diff "$PREV_TAG" "$TARGET_TAG" -- readme.txt README.md 2>/dev/null | head -200 || true)

PROMPT_FILE="$SYNC_WT/.wporg-fork-watch-prompt.md"
cat > "$PROMPT_FILE" <<EOF
You are porting a new upstream release of the WordPress.org plugin \`$SLUG\` into this fork.

Working directory: \`$SYNC_WT\` (git worktree, branch \`$SYNC_BRANCH\`, based on \`$BASE_REMOTE/$BASE_BRANCH\` at $BASE_SHA).
Upstream release: $UPSTREAM_NAME $TARGET, imported verbatim as git tag \`$TARGET_TAG\` on branch \`$VENDOR_BRANCH\`${PREV_TAG:+ (previous release: \`$PREV_TAG\`)}.
A \`git merge --no-ff --no-commit $TARGET_TAG\` has already been started in this worktree. State: $MERGE_STATE.
${CONFLICTS:+Conflicted files:
$CONFLICTS
}
## Fork policy (what to keep, what to drop)

$(cat "$POLICY_FILE")

## Upstream change summary ($PREV_TAG → $TARGET_TAG)

\`\`\`
$UPSTREAM_STAT
\`\`\`

Readme/changelog diff:

\`\`\`diff
${README_DIFF:-(none)}
\`\`\`

Run \`git diff ${PREV_TAG:-$(git -C "$REPO" rev-list --max-parents=0 "$TARGET_TAG" | head -1)} $TARGET_TAG\` (or per file) to read the full upstream changes.

## Your job

1. Read every upstream change against the policy. Finish the merge: resolve conflicts, keep every upstream change the policy allows (bug fixes, security hardening, features that work locally), and remove anything the policy drops, including new code the merge brought in cleanly without conflicts. Dropped upstream code must not survive in any file, including CSS, JS, images, readme, and uninstall cleanup.
2. Apply the policy's version and changelog rules so the fork reports the new upstream version.
3. Verify: syntax-check every changed PHP file (\`php -l\`), grep for the policy's forbidden markers, and make sure no conflict markers (\`<<<<<<<\`, \`>>>>>>>\`) remain.
4. Write \`SYNC_SUMMARY.md\` in the worktree root. It becomes the pull request body. Sections: a one-paragraph summary first, then **Upstream changes**, **Ported**, **Dropped (and why)**, **Verification**, and **Needs human attention** (empty is fine). Mention the upstream version and tag. Do not commit SYNC_SUMMARY.md.
5. Commit: \`git commit\` to conclude the merge (message: "Merge $UPSTREAM_NAME $TARGET"), then as many further commits as you need for the policy work. Leave the tree clean except SYNC_SUMMARY.md.

Rules: never push, never create a PR, never touch branches other than \`$SYNC_BRANCH\`, never edit files outside this worktree. If the merge cannot be completed safely, abort it with \`git merge --abort\`, write what blocked you in SYNC_SUMMARY.md under **Needs human attention**, and stop with a clean tree.
EOF
log "prompt composed ($(wc -c <"$PROMPT_FILE") bytes); running agent (timeout ${AGENT_TIMEOUT}s)"
AGENT_LOG="$LOG_DIR/$NAME-$TARGET-agent.log"
rc=0
(cd "$SYNC_WT" && timeout "$AGENT_TIMEOUT" bash -c "$AGENT_CMD" <"$PROMPT_FILE") >"$AGENT_LOG" 2>&1 || rc=$?
log "agent exited $rc (log: $AGENT_LOG)"
[[ $rc -ne 124 ]] || die "agent timed out after ${AGENT_TIMEOUT}s"
[[ $rc -eq 0 ]] || die "agent failed; see $AGENT_LOG"
rm -f "$PROMPT_FILE"

# ---- verify the handoff ----
[[ ! -f "$SYNC_WT/.git/MERGE_HEAD" ]] && ! git -C "$SYNC_WT" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1 || die "merge still in progress after the agent run"
[[ -f "$SYNC_WT/SYNC_SUMMARY.md" ]] || die "agent did not write SYNC_SUMMARY.md"
DIRTY=$(git -C "$SYNC_WT" status --porcelain | grep -v 'SYNC_SUMMARY.md' || true)
[[ -z "$DIRTY" ]] || die "worktree not clean after the agent run: $DIRTY"
if [[ "$(git -C "$SYNC_WT" rev-parse HEAD)" == "$BASE_SHA" ]]; then
  log "agent made no commits (merge aborted); summary follows"; sed -n 1,40p "$SYNC_WT/SYNC_SUMMARY.md"
  die "no port produced for $TARGET"
fi
if grep -rIl --exclude-dir=.git --exclude=SYNC_SUMMARY.md -E '^(<<<<<<<|>>>>>>>) ' "$SYNC_WT" >/dev/null 2>&1; then
  die "conflict markers remain in the tree"
fi
if [[ "$LINT_CMD" == "builtin" ]]; then
  if command -v php >/dev/null; then
    while IFS= read -r f; do
      [[ -f "$SYNC_WT/$f" ]] && { php -l "$SYNC_WT/$f" >/dev/null 2>&1 || die "php -l failed: $f"; }
    done < <(git -C "$SYNC_WT" diff --name-only "$BASE_SHA" HEAD -- '*.php')
    log "php -l passed on changed files"
  fi
elif [[ -n "$LINT_CMD" && "$LINT_CMD" != "none" ]]; then
  (cd "$SYNC_WT" && bash -c "$LINT_CMD") || die "LINT_CMD failed"
fi
CHANGED=$(git -C "$SYNC_WT" diff --shortstat "$BASE_SHA" HEAD)
log "port ready: $CHANGED"

if [[ $DRY_RUN -eq 1 ]]; then
  log "(dry-run) stopping before push/PR/review/notify. Summary:"
  cat "$SYNC_WT/SYNC_SUMMARY.md"
  exit 0
fi

# ---- push + PR ----
git -C "$SYNC_WT" push --quiet -u "$PUSH_REMOTE" "$SYNC_BRANCH" || die "push of $SYNC_BRANCH to $PUSH_REMOTE failed"
PUSHED=1
gh label create "$PR_LABEL" --repo "$PR_REPO" --color 0E8A16 --description "Upstream release port" >/dev/null 2>&1 || true
PR_BODY="$SYNC_WT/.pr-body.md"
{ cat "$SYNC_WT/SYNC_SUMMARY.md"; printf '\n\n---\nUpstream: `%s/%s/tags/%s` → tag `%s`. Opened by wporg-fork-watch.\n\n%s\n' "$SVN_BASE" "$SLUG" "$TARGET" "$TARGET_TAG" "$PR_FOOTER"; } > "$PR_BODY"
PR_URL=$(gh pr create --repo "$PR_REPO" --base "$BASE_BRANCH" --head "${PR_HEAD_PREFIX}${SYNC_BRANCH}" \
  --title "Sync $UPSTREAM_NAME $TARGET" --body-file "$PR_BODY" --label "$PR_LABEL" 2>&1) || die "gh pr create failed: $PR_URL"
PR_URL=$(grep -o 'https://github.com/[^ ]*/pull/[0-9]*' <<<"$PR_URL" | head -1)
[[ -n "$PR_URL" ]] || die "could not parse PR URL"
log "PR opened: $PR_URL"
PR_NUMBER="${PR_URL##*/}"

# ---- review ----
REVIEW_LINE="review skipped"
if [[ "$REVIEW_CMD" == "builtin" ]]; then
  REVIEW_PROMPT="$SYNC_WT/.review-prompt.md"
  {
    printf 'Review pull request %s, which ports %s %s into a fork. Judge it against this fork policy:\n\n' "$PR_URL" "$UPSTREAM_NAME" "$TARGET"
    cat "$POLICY_FILE"
    printf '\n\nThe PR description:\n\n'; cat "$SYNC_WT/SYNC_SUMMARY.md"
    printf '\n\nThe diff:\n\n```diff\n'; gh pr diff "$PR_URL" | head -c 400000; printf '\n```\n\n'
    printf 'Check: (1) anything the policy drops that slipped through, (2) upstream fixes or security changes that were dropped without a policy reason, (3) merge mistakes: duplicated blocks, leftover conflict markers, broken PHP, references to removed functions or files, (4) the version and changelog rules. Be specific with file paths. Start your reply with one line `VERDICT: approve` or `VERDICT: request-changes` or `VERDICT: comment`, then the review in markdown.\n'
  } > "$REVIEW_PROMPT"
  REVIEW_OUT="$LOG_DIR/$NAME-$TARGET-review.md"
  if (cd "$SYNC_WT" && timeout "$REVIEW_TIMEOUT" bash -c "$REVIEW_AGENT_CMD" <"$REVIEW_PROMPT") >"$REVIEW_OUT" 2>"$LOG_DIR/$NAME-$TARGET-review.err"; then
    VERDICT=$(grep -m1 -oE '^VERDICT: *(approve|request-changes|comment)' "$REVIEW_OUT" | sed 's/VERDICT: *//' || true)
    case "$VERDICT" in request-changes) EVENT=--request-changes ;; *) EVENT=--comment ;; esac
    gh pr review "$PR_URL" "$EVENT" --body-file "$REVIEW_OUT" >/dev/null 2>&1 && REVIEW_LINE="review posted (${VERDICT:-comment})" || REVIEW_LINE="review generated but posting failed ($REVIEW_OUT)"
  else
    REVIEW_LINE="review agent failed (see $LOG_DIR/$NAME-$TARGET-review.err)"
  fi
  rm -f "$REVIEW_PROMPT"
elif [[ -n "$REVIEW_CMD" && "$REVIEW_CMD" != "none" ]]; then
  if bash -c "$REVIEW_CMD \"\$1\"" _ "$PR_URL"; then
    STATE=$(gh api "repos/$PR_REPO/pulls/$PR_NUMBER/reviews" --jq 'map(select(.state != "PENDING")) | last | .state // empty' 2>/dev/null || true)
    REVIEW_LINE="review posted${STATE:+ ($(tr 'A-Z_' 'a-z ' <<<"$STATE"))}"
  else
    REVIEW_LINE="review command failed"
  fi
fi
log "$REVIEW_LINE"

# ---- notify ----
SUMMARY_LINE=$(awk 'NF && !/^#/ { print; exit }' "$SYNC_WT/SYNC_SUMMARY.md" | head -c 600)
MESSAGE="$UPSTREAM_NAME $TARGET is out and ported to $PR_REPO: $PR_URL
$SUMMARY_LINE
$REVIEW_LINE. Merge is a human call."
export PR_URL VERSION="$TARGET" SLUG PR_REPO
if [[ -n "$NOTIFY_CMD" ]]; then
  printf '%s\n' "$MESSAGE" | bash -c "$NOTIFY_CMD" && log "notified via NOTIFY_CMD" || log "warn: NOTIFY_CMD failed"
fi
if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
  curl -sf -X POST -H 'Content-type: application/json' --data "$(jq -n --arg t "$MESSAGE" '{text: $t}')" "$SLACK_WEBHOOK_URL" >/dev/null \
    && log "notified via Slack webhook" || log "warn: Slack webhook failed"
fi
[[ -n "$NOTIFY_CMD$SLACK_WEBHOOK_URL" ]] || printf '%s\n' "$MESSAGE"
log "=== done: $PR_URL ==="
