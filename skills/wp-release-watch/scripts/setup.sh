#!/usr/bin/env bash
#
# setup.sh — idempotent installer for wp-release-watch.
#
# Checks deps, writes a config template (never overwrites), optionally installs
# the cron entry, and records an install receipt. Re-runs are no-ops unless
# --force.
#
# Usage: bash scripts/setup.sh [--force] [--yes] [--no-cron]
#
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/wp-release-watch"
RECEIPT="$CONFIG_DIR/.installed"

ASSUME_YES=0; FORCE=0; INSTALL_CRON=1
for arg in "$@"; do
  case "$arg" in
    --yes|-y)   ASSUME_YES=1 ;;
    --force)    FORCE=1 ;;
    --no-cron)  INSTALL_CRON=0 ;;
    --help|-h)  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 1 ;;
  esac
done

log()  { printf '[wp-release-watch] %s\n' "$*"; }
warn() { printf '[wp-release-watch] WARN: %s\n' "$*" >&2; }
die()  { printf '[wp-release-watch] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ -f "$RECEIPT" && $FORCE -eq 0 ]]; then
  log "already installed — receipt at $RECEIPT"
  log "re-run with --force to reinstall"
  exit 0
fi

# ── Deps ─────────────────────────────────────────────────────────────
for dep in curl jq; do
  command -v "$dep" >/dev/null 2>&1 || die "$dep is required but not installed."
done
log "deps OK (curl, jq)"

# ── Config template (never overwrite an existing config) ─────────────
mkdir -p "$CONFIG_DIR"
if [[ -f "$CONFIG_DIR/config.env" && $FORCE -eq 0 ]]; then
  log "config already exists: $CONFIG_DIR/config.env (left untouched)"
else
  cat > "$CONFIG_DIR/config.env" <<'EOF'
# wp-release-watch configuration
# ── What to watch ────────────────────────────────────────────────
REPO="WordPress/wordpress-develop"
GH_TOKEN=""                      # GitHub PAT — avoids the 60 req/hr anonymous limit

# ── Analyzer (prompt on stdin → plain text on stdout) ───────────
# Examples:
#   ANALYZE_CMD='claude -p --disallowedTools Skill'
#   ANALYZE_CMD='pi rk -p --no-tools'
#   ANALYZE_CMD='codex exec --skip-git-repo-check "$(cat)"'
ANALYZE_CMD="claude -p --disallowedTools Skill"

# ── Threat intel (optional; question on stdin → text on stdout) ─
# CONTEXT_CMD="my-web-search-cli"

# ── Notification ────────────────────────────────────────────────
# SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
# NOTIFY_CMD='mail -s "WP $VERSION: $SEVERITY" you@example.com'
NOTIFY_MIN_SEVERITY="none"       # none|low|medium|high|critical

# ── Cron ────────────────────────────────────────────────────────
SCHEDULE="0 * * * *"
MAX_PATCH_CHARS="400000"
EOF
  log "config template written: $CONFIG_DIR/config.env"
  warn "edit config.env before going live (GH_TOKEN, analyzer, notification path)"
fi

# shellcheck disable=SC1090
source "$CONFIG_DIR/config.env"

# ── Analyzer smoke check ─────────────────────────────────────────────
if ! command -v "${ANALYZE_CMD%% *}" >/dev/null 2>&1; then
  warn "analyzer binary '${ANALYZE_CMD%% *}' not on PATH — fix ANALYZE_CMD in $CONFIG_DIR/config.env"
fi

chmod +x "$SKILL_DIR/scripts/wp-release-watch.sh"

# ── Cron ─────────────────────────────────────────────────────────────
CRON_TAG="# wp-release-watch"
CRON_LINE="$SCHEDULE $SKILL_DIR/scripts/wp-release-watch.sh >> $HOME/.local/state/wp-release-watch/watch.log 2>&1 $CRON_TAG"

if [[ $INSTALL_CRON -eq 1 ]]; then
  CONFIRM=1
  if [[ $ASSUME_YES -eq 0 ]]; then
    printf '[wp-release-watch] install cron? %s [Y/n] ' "$CRON_LINE"
    read -r reply
    [[ "${reply:-y}" =~ ^[Yy] ]] || CONFIRM=0
  fi
  if [[ $CONFIRM -eq 1 ]]; then
    mkdir -p "$HOME/.local/state/wp-release-watch"
    ( crontab -l 2>/dev/null | grep -v "$CRON_TAG" || true; echo "$CRON_LINE" ) | crontab -
    log "cron installed ($SCHEDULE). Verify: crontab -l | grep wp-release-watch"
  else
    log "cron skipped. Install manually:"
    log "  $CRON_LINE"
  fi
else
  log "cron not installed (--no-cron). Manual entry:"
  log "  $CRON_LINE"
fi

# ── Receipt (last) ───────────────────────────────────────────────────
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  printf 'config=%s\n' "$CONFIG_DIR/config.env"
  printf 'cron_line=%s\n' "$CRON_LINE"
} > "$RECEIPT"

log "done."
log "next: edit $CONFIG_DIR/config.env, then run:"
log "  $SKILL_DIR/scripts/wp-release-watch.sh --init          # baseline current tag"
log "  $SKILL_DIR/scripts/wp-release-watch.sh --test 7.0.3 7.0.4   # verify end-to-end"
