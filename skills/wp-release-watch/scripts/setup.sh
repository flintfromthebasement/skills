#!/usr/bin/env bash
#
# setup.sh — idempotent installer for wp-release-watch.
#
# Checks deps, writes a config template (NEVER overwrites an existing config,
# even with --force), optionally installs the cron entry (with a sane PATH for
# the analyzer), and records an install receipt. Re-runs are no-ops unless
# --force.
#
# Usage: bash scripts/setup.sh [--force] [--yes] [--no-cron] [--cron]
#   --force     redo deps/cron/receipt steps (config.env is never touched)
#   --cron      (re)install the crontab entry from SCHEDULE and exit — works
#               even when already installed; use after changing SCHEDULE
#
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/wp-release-watch"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/wp-release-watch"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wp-release-watch"
RECEIPT="$CONFIG_DIR/.installed"

ASSUME_YES=0; FORCE=0; INSTALL_CRON=1; CRON_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y)   ASSUME_YES=1 ;;
    --force)    FORCE=1 ;;
    --no-cron)  INSTALL_CRON=0 ;;
    --cron)     CRON_ONLY=1 ;;
    --help|-h)  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

log()  { printf '[wp-release-watch] %s\n' "$*"; }
warn() { printf '[wp-release-watch] WARN: %s\n' "$*" >&2; }
die()  { printf '[wp-release-watch] ERROR: %s\n' "$*" >&2; exit 1; }

mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"

# ── Cron install helper (shared by normal flow and --cron) ──────────
install_cron() {
  # shellcheck disable=SC1091
  [ -f "$CONFIG_DIR/config.env" ] && source "$CONFIG_DIR/config.env"
  local schedule="${SCHEDULE:-0 * * * *}"
  # Explicit PATH: analyzers like claude/pi/codex often live in ~/.local/bin or
  # ~/.npm-global/bin, which minimal cron environments don't have. Without
  # this, --test works interactively and the first real run fails hourly.
  local cron_path="$HOME/.local/bin:$HOME/bin:$HOME/.npm-global/bin:/usr/local/bin:/usr/bin:/bin"
  local cron_line="$schedule PATH=$cron_path $SKILL_DIR/scripts/wp-release-watch.sh >> $LOG_DIR/watch.log 2>&1 # wp-release-watch"

  local confirm=1
  if [[ $ASSUME_YES -eq 0 && $CRON_ONLY -eq 0 ]]; then
    printf '[wp-release-watch] install cron? %s\n[y/N] ' "$cron_line"
    read -r reply
    [[ "${reply:-n}" =~ ^[Yy] ]] || { log "cron skipped."; return 0; }
  fi
  ( crontab -l 2>/dev/null | grep -v "# wp-release-watch" || true; echo "$cron_line" ) | crontab -
  log "cron installed ($schedule). Verify: crontab -l | grep wp-release-watch"
}

if [[ $CRON_ONLY -eq 1 ]]; then
  install_cron
  exit 0
fi

if [[ -f "$RECEIPT" && $FORCE -eq 0 ]]; then
  log "already installed — receipt at $RECEIPT"
  log "re-run with --force to reinstall, or --cron to update the schedule"
  exit 0
fi

# ── Deps ─────────────────────────────────────────────────────────────
for dep in curl jq flock; do
  command -v "$dep" >/dev/null 2>&1 || die "$dep is required but not installed."
done
log "deps OK (curl, jq, flock)"

# ── Config template (never overwrite — secrets live here) ───────────
if [[ -f "$CONFIG_DIR/config.env" ]]; then
  chmod 600 "$CONFIG_DIR/config.env"
  log "config already exists: $CONFIG_DIR/config.env (left untouched)"
else
  cat > "$CONFIG_DIR/config.env" <<'EOF'
# wp-release-watch configuration
# NOTE: this file is sourced with `set -a`, so EVERY variable here is exported
# to the analyzer/notify commands. Put your analyzer's API keys below and they
# will be available under cron. Keep this file 600.

# ── What to watch ────────────────────────────────────────────────
REPO="WordPress/wordpress-develop"
# GH_TOKEN="ghp_..."             # GitHub PAT — avoids the 60 req/hr anonymous limit
# Leave this line commented if GH_TOKEN is already in the environment.
# config.env is sourced with `set -a`; an empty GH_TOKEN="" assignment
# would clobber the inherited token.
# TAG_PATTERN="^v?[0-9]+\.[0-9]+(\.[0-9]+)?$"   # adjust if tags look different

# ── Analyzer (prompt on stdin → plain text on stdout) ───────────
# The command runs under cron with the PATH set at install time; API keys can
# be defined right here, e.g.:  ANTHROPIC_API_KEY="sk-..."
# Examples:
#   ANALYZE_CMD='claude -p --disallowedTools Skill'
#   ANALYZE_CMD='pi rk -p --no-tools'
#   ANALYZE_CMD='codex exec --skip-git-repo-check -'   # '-' = read stdin
ANALYZE_CMD="claude -p --disallowedTools Skill"

# ── Threat intel (optional; question on stdin → text on stdout) ─
# CONTEXT_CMD="my-web-search-cli"

# ── Notification ────────────────────────────────────────────────
# SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
# NOTIFY_CMD='mail -s "WP $VERSION: $SEVERITY" you@example.com'
NOTIFY_MIN_SEVERITY="none"       # none|low|medium|high|critical
PING="channel"                   # attention ping on delivered alerts: channel|here|none

# ── Cron ────────────────────────────────────────────────────────
SCHEDULE="0 * * * *"
MAX_PATCH_CHARS="400000"
MAX_INTEL_CHARS="50000"
EOF
  chmod 600 "$CONFIG_DIR/config.env"
  log "config template written: $CONFIG_DIR/config.env (chmod 600)"

  # Make the ping choice explicit at setup — it decides who gets woken up.
  if [[ $ASSUME_YES -eq 0 ]]; then
    printf '[wp-release-watch] attention ping on alerts — 1) @channel (default) 2) @here 3) none [1/2/3] '
    read -r reply
    case "${reply:-1}" in
      2) sed -i 's/^PING=.*/PING="here"/' "$CONFIG_DIR/config.env" ; log "PING=here" ;;
      3) sed -i 's/^PING=.*/PING="none"/'  "$CONFIG_DIR/config.env" ; log "PING=none" ;;
      *) log "PING=channel (default)" ;;
    esac
  fi
  warn "edit config.env before going live (GH_TOKEN, analyzer credentials, notification path)"
fi

# shellcheck disable=SC1091
source "$CONFIG_DIR/config.env"

# ── Analyzer smoke check ─────────────────────────────────────────────
if ! command -v "${ANALYZE_CMD%% *}" >/dev/null 2>&1; then
  warn "analyzer binary '${ANALYZE_CMD%% *}' not on YOUR path — under cron it uses the PATH baked into the crontab line; verify with a real --test run"
fi

chmod +x "$SKILL_DIR/scripts/wp-release-watch.sh"

# ── Cron ─────────────────────────────────────────────────────────────
if [[ $INSTALL_CRON -eq 1 ]]; then
  install_cron
else
  log "cron not installed (--no-cron). Install later with: bash scripts/setup.sh --cron"
fi

# ── Receipt (last) ───────────────────────────────────────────────────
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  printf 'config=%s\n' "$CONFIG_DIR/config.env"
} > "$RECEIPT"

log "done."
log "next: edit $CONFIG_DIR/config.env, then run:"
log "  $SKILL_DIR/scripts/wp-release-watch.sh --init                  # baseline current tag"
log "  $SKILL_DIR/scripts/wp-release-watch.sh --test 7.0.3 7.0.4      # dry-run a known pair"
