#!/usr/bin/env bash
#
# setup.sh — idempotent installer for wporg-fork-watch.
#
# Checks deps (svn, git, gh, jq, the agent CLI), copies the example config for a
# watch name into ~/.config/wporg-fork-watch/<name>.env (never overwrites an
# existing config, even with --force), optionally installs a crontab line, and
# records an install receipt per watch. Re-runs are no-ops unless --force.
#
# Usage: bash scripts/setup.sh <name> [--example <file>] [--force] [--yes] [--no-cron] [--cron]
#   <name>      watch name; config lands at ~/.config/wporg-fork-watch/<name>.env
#   --example   config to copy when none exists (default: examples/<name>.env, else examples/pmpro-crontrol.env)
#   --cron      (re)install the crontab line from SCHEDULE in the config and exit
#   --no-cron   everything except the crontab line
#   --force     redo deps/cron/receipt steps (the config file is never touched)
#
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/wporg-fork-watch"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/wporg-fork-watch"

NAME=""; EXAMPLE=""; ASSUME_YES=0; FORCE=0; INSTALL_CRON=1; CRON_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) ASSUME_YES=1; shift ;;
    --force) FORCE=1; shift ;;
    --no-cron) INSTALL_CRON=0; shift ;;
    --cron) CRON_ONLY=1; shift ;;
    --example) EXAMPLE="${2:?--example needs a path}"; shift 2 ;;
    --help|-h) sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown arg: $1" >&2; exit 1 ;;
    *) NAME="$1"; shift ;;
  esac
done
[[ -n "$NAME" ]] || { echo "usage: setup.sh <name> [--force] [--yes] [--no-cron] [--cron]" >&2; exit 1; }

log()  { printf '[wporg-fork-watch] %s\n' "$*"; }
warn() { printf '[wporg-fork-watch] WARN: %s\n' "$*" >&2; }
die()  { printf '[wporg-fork-watch] ERROR: %s\n' "$*" >&2; exit 1; }

CONFIG="$CONFIG_DIR/$NAME.env"
RECEIPT="$CONFIG_DIR/.installed-$NAME"
mkdir -p "$CONFIG_DIR" "$LOG_DIR"

install_cron() {
  # shellcheck disable=SC1090
  [[ -f "$CONFIG" ]] && source "$CONFIG"
  local schedule="${SCHEDULE:-30 6 * * *}"
  local cron_path="$HOME/.local/bin:$HOME/bin:$HOME/.npm-global/bin:/usr/local/bin:/usr/bin:/bin"
  local marker="# wporg-fork-watch:$NAME"
  local line="$schedule PATH=$cron_path $SKILL_DIR/scripts/wporg-fork-watch.sh $NAME >> $LOG_DIR/$NAME.log 2>&1 $marker"
  if [[ $ASSUME_YES -eq 0 && $CRON_ONLY -eq 0 ]]; then
    printf '[wporg-fork-watch] install cron? %s\n[y/N] ' "$line"
    read -r reply
    [[ "${reply:-n}" =~ ^[Yy] ]] || { log "cron skipped."; return 0; }
  fi
  ( crontab -l 2>/dev/null | grep -vF "$marker" || true; echo "$line" ) | crontab -
  log "cron installed ($schedule). Verify: crontab -l | grep wporg-fork-watch"
}

if [[ $CRON_ONLY -eq 1 ]]; then install_cron; exit 0; fi
if [[ -f "$RECEIPT" && $FORCE -eq 0 ]]; then
  log "already installed for '$NAME' ($(head -1 "$RECEIPT")). Use --force to redo, --cron to reinstall the crontab line."
  exit 0
fi

# 1. deps
missing=()
for bin in svn git gh jq; do command -v "$bin" >/dev/null || missing+=("$bin"); done
if (( ${#missing[@]} )); then
  log "missing: ${missing[*]}"
  log "fix: sudo apt-get install -y subversion git jq   # gh: https://cli.github.com"
  die "install the missing dependencies and re-run"
fi
gh auth status >/dev/null 2>&1 || warn "gh is not authenticated (or GH_TOKEN unset); PR creation will fail until it is"
command -v claude >/dev/null || warn "claude CLI not on PATH; set AGENT_CMD/REVIEW_AGENT_CMD in the config to the harness you use"
command -v php >/dev/null || warn "php not on PATH; the builtin php -l lint gate will be skipped"

# 2. config (never overwritten)
if [[ -f "$CONFIG" ]]; then
  log "config exists: $CONFIG (left untouched)"
else
  [[ -n "$EXAMPLE" ]] || EXAMPLE="$SKILL_DIR/examples/$NAME.env"
  [[ -f "$EXAMPLE" ]] || EXAMPLE="$SKILL_DIR/examples/pmpro-crontrol.env"
  cp "$EXAMPLE" "$CONFIG"
  chmod 600 "$CONFIG"
  log "config written from $(basename "$EXAMPLE"): $CONFIG"
  log "edit SLUG, REPO, POLICY_FILE, and NOTIFY_CMD before the first run"
fi

# 3. cron
[[ $INSTALL_CRON -eq 1 ]] && install_cron

# 4. receipt
printf 'installed %s\nconfig %s\nskill %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$CONFIG" "$SKILL_DIR" > "$RECEIPT"
log "done. Next: bash $SKILL_DIR/scripts/wporg-fork-watch.sh $NAME --list"
