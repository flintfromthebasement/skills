---
name: wporg-fork-watch
description: Keep a fork of a WordPress.org plugin current without re-doing the fork by hand. A daily cron watches the plugin's SVN tags; each new release is exported onto a pristine vendor branch, merged into a PR branch, and handed to an agent that applies your keep/drop policy (strip promos, telemetry, upsells, rebranding; keep fixes and features), lints, writes the PR body, and commits. The script opens the pull request, runs a review (a second agent pass or your own reviewer), and notifies someone (any command, or a Slack webhook). Merging stays human. Harness-agnostic: claude -p by default, any stdin-prompt CLI via config.
---

# wporg-fork-watch

You forked a WordPress.org plugin because a release added something you refuse to ship (cross-promotion panels, one-click installers for a vendor's other plugins, usage tracking, a rebrand). The problem with that fork is next month: upstream keeps shipping real fixes, and someone has to port them while keeping the junk out. This skill makes that a daily cron with an agent doing the merge and a human doing the merge button.

Built for `strangerstudios/pmpro-cron-management`, a fork of WP Crontrol made after the 2.0.0 Awesome Motive release. The example config and policy are the real ones.

## How it works

```
daily cron → svn ls plugins.svn.wordpress.org/<slug>/tags
  → tags newer than the newest <TAG_PREFIX>* git tag?
      → svn export each tag onto VENDOR_BRANCH, one commit + tag per release, push
      → worktree PR_BRANCH_PREFIX<version> from BASE_REMOTE/BASE_BRANCH
      → git merge --no-ff --no-commit <tag>          (script)
      → agent reads POLICY_FILE + upstream diff, resolves conflicts,
        drops what the policy drops, bumps version/changelog,
        php -l + marker grep, writes SYNC_SUMMARY.md, commits   (AGENT_CMD)
      → conflict-marker + lint gate, push, gh pr create (body = SYNC_SUMMARY.md)
      → REVIEW_CMD <pr-url>  (builtin: agent reviews the diff against the policy, posts a GitHub review)
      → NOTIFY_CMD / SLACK_WEBHOOK_URL with version, PR link, summary line, review verdict
  → nothing new: exit 0 quietly
```

Design points worth knowing before you trust it:

- **State is git plus GitHub, not a state file.** The newest `TAG_PREFIX*` tag is what was imported; a PR whose head is `PR_BRANCH_PREFIX<version>` is what was handed off. A crash between the two resumes on the next run. A merged tag (`merge-base --is-ancestor`) is done.
- **The vendor branch is pristine.** Every release is an exact `svn export` of the SVN tag, so `git diff wp-crontrol-2.0.0 wp-crontrol-2.0.1` is the true upstream diff and the merge is a real three-way merge with your fork's history. Never edit it by hand.
- **The agent never pushes.** The script starts the merge, the agent finishes it inside a throwaway worktree with edits auto-accepted and a shell limited to git/php/grep and friends, and the script verifies: merge concluded, tree clean, no conflict markers, `php -l` on changed files, `SYNC_SUMMARY.md` present. Any failure exits non-zero with no PR.
- **One open sync PR at a time.** If the last PR is still open, the run logs and exits; releases that stack up are exported to the vendor branch and the next PR covers all of them.
- **Dry-run is a real rehearsal.** `--dry-run` imports tags locally, runs the agent, and stops before push/PR/review/notify, keeping the worktree so you can read the result. Use it to tune the policy before the cron goes live.

## Setup

```bash
bash scripts/setup.sh pmpro-cron-management            # deps check, config from examples/, cron prompt, receipt
bash scripts/setup.sh my-fork --example examples/pmpro-cron-management.env --no-cron
```

Then edit `~/.config/wporg-fork-watch/<name>.env`:

| Key | Meaning |
|---|---|
| `SLUG` | WordPress.org plugin slug (`plugins.svn.wordpress.org/<slug>`) |
| `REPO` | local checkout of your fork |
| `BASE_BRANCH`, `BASE_REMOTE`, `PUSH_REMOTE`, `PR_REPO` | fork-model aware: `BASE_REMOTE` defaults to `upstream` when that remote exists; the PR head gets an `owner:` prefix when push and PR repos differ |
| `VENDOR_BRANCH`, `TAG_PREFIX` | pristine SVN export branch and its per-release tags |
| `PR_BRANCH_PREFIX`, `PR_LABEL` | PR head branch name and label (label is created if missing) |
| `POLICY_FILE` | markdown the agent and reviewer follow; see `examples/pmpro-cron-management.policy.md` |
| `AGENT_CMD`, `AGENT_TOOLS`, `AGENT_TIMEOUT` | the merge agent; default `claude -p --model opus --effort high --permission-mode acceptEdits --allowedTools "<git/php/grep/...>"` |
| `REVIEW_CMD`, `REVIEW_AGENT_CMD` | `builtin` (agent review posted with `gh pr review`), a command taking the PR URL, or `none` |
| `LINT_CMD` | `builtin` (`php -l` on changed PHP), a command run in the worktree, or `none` |
| `NOTIFY_CMD`, `SLACK_WEBHOOK_URL` | message on stdin with `$PR_URL`, `$VERSION`, `$SLUG`, `$PR_REPO` exported; and/or a Slack incoming webhook |
| `SCHEDULE` | cron expression for `setup.sh --cron` |

Bootstrap an existing fork once so the vendor branch has the release your fork is based on:

```bash
git checkout --orphan wp-crontrol && git rm -rfq --cached . && rm -rf ./*   # new empty vendor branch
svn export --force https://plugins.svn.wordpress.org/wp-crontrol/tags/2.0.0 .
git add -A && git commit -m "WP Crontrol 2.0.0 (pristine export of tags/2.0.0)"
git tag wp-crontrol-2.0.0
```

If your `main` was not branched from that commit, the first merge will conflict more than later ones; run `--dry-run` and read the result.

## Run

```bash
scripts/wporg-fork-watch.sh pmpro-cron-management --list        # SVN tags vs imported state
scripts/wporg-fork-watch.sh pmpro-cron-management --dry-run     # full rehearsal, no push/PR/review/notify
scripts/wporg-fork-watch.sh pmpro-cron-management               # the cron entry point
scripts/wporg-fork-watch.sh pmpro-cron-management --version 2.0.1   # re-port a specific tag
```

Logs: `~/.local/state/wporg-fork-watch/<name>.log`, plus `<name>-<version>-agent.log` and `-review.md` per release.

## Writing a policy

The policy is the whole product. Say what the fork is and why, then four sections the prompt leans on: **Keep**, **Drop**, **Fork identity** (renamed main file, header, added files, things that must survive every merge), **Version and changelog**, and **Verification** (the greps and lints the agent must run). Be concrete about markers: CSS class prefixes, option names, filter names, image folders. The agent is told that dropped code must not survive in any file and that cleanly merged hunks still need judging, so the policy should name the things a diff would not make obvious. `examples/pmpro-cron-management.policy.md` is a complete one.

## Plugging in your own tools

- Another harness: `AGENT_CMD="codex exec --full-auto -"` or any CLI that reads a prompt on stdin and edits the cwd.
- Your own reviewer: `REVIEW_CMD="/path/to/review-pr.sh"` gets the PR URL; the notify line then reports the latest review state on the PR.
- Your own notifier: `NOTIFY_CMD='bash -c "source ~/lib/slack.sh; post_dev \"$(cat)\""'`, `NOTIFY_CMD="mail -s \"$SLUG $VERSION ported\" you@example.com"`, or a webhook.
- A cron wrapper of your own: call `scripts/wporg-fork-watch.sh <name>` from it and skip `setup.sh --cron`.

## Requirements

`svn`, `git`, `gh` (authenticated, with push access to `PUSH_REMOTE` and PR rights on `PR_REPO`), `jq`, and the agent CLI. `php` is optional but recommended for the lint gate.
