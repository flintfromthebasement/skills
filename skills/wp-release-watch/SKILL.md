---
name: wp-release-watch
description: Hourly watchdog that polls a WordPress (or any git-tagged) repo for new releases, diffs each release against its predecessor, runs an LLM security analysis over the diff plus optional web threat intel, writes a markdown report, and notifies you however you want — Slack webhook, arbitrary command, or just the report file. Model- and harness-agnostic: bring your own `claude -p`, `codex exec`, pi, or raw API command.
---

# WP Release Watch

A set-and-forget security tripwire for WordPress core releases. WordPress does
not publish GitHub Release objects, so most tooling misses point releases
entirely. This skill polls the repo's **tags**, picks the highest stable semver,
diffs it against its immediate predecessor, and has a model read the actual code
changes for patched vulnerabilities — then tells you about it before your users
do.

Born from a real incident: this pipeline analyzed WordPress 7.0.4 and posted a
severity-tagged summary roughly an hour before WordPress's own announcement went
live. The full story is on the blog; this is the reusable version.

## When to use

- You operate one or many WordPress sites and want hours of head start on core security releases
- You want a model reading release diffs for you, with structured severity output you can alert on
- You want the same pattern pointed at **any project that ships git tags** (`REPO` is configurable)

## When not to use

- Plugin/theme monitoring — the diff volumes and tagging patterns differ; adapt with care
- As your *only* defense — this is early warning, not patching. Someone still has to update the sites.

## How it works

```
hourly cron → poll /tags (GitHub API)
  → new stable tag? → fetch compare OLD...NEW
  → [optional] gather threat intel (CONTEXT_CMD)
  → build prompt (commit messages + unified patches)
  → ANALYZE_CMD reads prompt on stdin, emits structured verdict
  → parse SEVERITY / SECURITY_RELEASE / NEEDS_HUMAN_REVIEW
  → write markdown report + notify (webhook / NOTIFY_CMD)
  → update state file
```

Two design decisions worth understanding before you trust it:

**1. Diff-only analysis lies low.** WordPress core deliberately obscures
security fixes — burying them inside refactors with vague commit messages so
responsible sites can patch before attackers reverse-engineer the fix. A small,
oddly-defensive change to input handling may be a critical fix that looks like
nothing. So the pipeline takes the **max of code-derived and intel-derived**
severity, and flags anything it can't fully confirm as `NEEDS_HUMAN_REVIEW`
rather than quietly rating it low.

**2. The model call is a shell command, not an SDK.** The analyzer is whatever
`ANALYZE_CMD` says — any harness or model that can read a prompt on stdin and
write text to stdout. Swap models without touching code.

## Setup

```bash
bash scripts/setup.sh              # deps check, config template, cron install, receipt
bash scripts/setup.sh --no-cron    # everything except the crontab entry
bash scripts/setup.sh --force      # reinstall
```

Edit the generated config at `~/.config/wp-release-watch/config.env` — at minimum
set `GH_TOKEN` (avoids GitHub's 60 req/hr anonymous limit) and pick your
analyzer + notification path. Then baseline:

```bash
scripts/wp-release-watch.sh --init   # record current latest tag, no alert
scripts/wp-release-watch.sh --test 7.0.3 7.0.4   # force-analyze a known pair end-to-end
scripts/wp-release-watch.sh --dry-run            # analyze next real release without notifying
```

Always run `--test` against a past security release before going live. It's the
cheapest way to find out your `ANALYZE_CMD` isn't on PATH or your parser
expectations are wrong — while nothing is burning.

## Configuration (`~/.config/wp-release-watch/config.env`)

| Variable | Default | Notes |
| --- | --- | --- |
| `REPO` | `WordPress/wordpress-develop` | Any `owner/repo` that tags releases. |
| `GH_TOKEN` | _(unset)_ | GitHub PAT. Strongly recommended. |
| `ANALYZE_CMD` | `claude -p` | Shell snippet; prompt arrives **on stdin**, verdict on stdout. Run via `bash -c`. |
| `CONTEXT_CMD` | _(unset)_ | Optional. Receives a question on stdin, emits threat-intel text. E.g. a Perplexity/web-search CLI. Unset = diff-only analysis. |
| `NOTIFY_CMD` | _(unset)_ | Optional. Message on stdin; env gets `VERSION`, `SEVERITY`, `SECURITY_RELEASE`, `REPORT_FILE`. |
| `SLACK_WEBHOOK_URL` | _(unset)_ | Optional built-in Slack notify via incoming webhook. |
| `NOTIFY_MIN_SEVERITY` | `none` | `none/low/medium/high/critical` — suppress pings below this (report is still written). |
| `SCHEDULE` | `0 * * * *` | Cron schedule installed by setup.sh. |
| `MAX_PATCH_CHARS` | `400000` | Patch budget fed to the model; oversized files are named and skipped. |

### Analyzer adapters

The protocol: **prompt in on stdin, plain text out on stdout.** The model must
reply in the exact structured format the prompt requests (severity header lines,
then `---`, then a human-readable summary). Proven adapters:

```bash
# Claude Code (headless). --disallowedTools Skill matters: bundled skills can
# silently auto-inject ~600KB into the prompt and blow your context budget.
ANALYZE_CMD='claude -p --disallowedTools Skill'

# pi (any provider/model your pi install has)
ANALYZE_CMD='pi rk -p --no-tools'          # e.g. Kimi 3

# OpenAI Codex CLI
ANALYZE_CMD='codex exec --skip-git-repo-check "$(cat)"'

# Plain `llm` CLI
ANALYZE_CMD='llm -m claude-sonnet'

# Raw OpenAI-compatible API (jq + curl one-liner)
ANALYZE_CMD='jq -Rs "{model: \"gpt-5.6\", messages: [{role: \"user\", content: .}]}" \
  | curl -s https://api.openai.com/v1/chat/completions -H "Auth..." -d @- \
  | jq -r ".choices[0].message.content"'
```

### Notification adapters

Reports always land in `~/.local/share/wp-release-watch/reports/<version>.md`.
On top of that, any combination of:

```bash
# Built-in Slack webhook
SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'

# Arbitrary command — email, Discord, another agent's inbox, SMS gateway...
NOTIFY_CMD='mail -s "WP $VERSION: $SEVERITY" you@example.com'
NOTIFY_CMD='tee /home/partner/data/slack-inbox/wp-security.md'   # file drop for someone else's cron
```

## State & logs

Everything mutable lives outside the repo:

```
~/.config/wp-release-watch/config.env     # config (you edit this)
~/.config/wp-release-watch/.installed     # setup receipt
~/.local/share/wp-release-watch/state     # last-seen tag (baselined on first run)
~/.local/share/wp-release-watch/reports/  # per-release markdown reports
~/.local/state/wp-release-watch/watch.log # run log
```

Uninstall: remove the crontab line tagged `# wp-release-watch`, then
`rm -rf ~/.config/wp-release-watch ~/.local/share/wp-release-watch`.

## Honest limits

- **It reads diffs, not running sites.** Pair with fleet-level checks (wp-cli core version sweep) if you manage many installs.
- **Severity is a model opinion shaped by a good prompt.** The structured format and the max-floor parsing keep it consistent; the human-review flag keeps it honest.
- **One-shot analysis per release.** If threat intel lands days later (it does), re-run `--test OLD NEW` manually.
