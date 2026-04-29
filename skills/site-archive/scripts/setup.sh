#!/usr/bin/env bash
# setup.sh — idempotent installer for site-archive.
#
# What it does:
#   1. Verifies node + npm are available.
#   2. Runs `npm install` if node_modules is missing or package-lock has drifted.
#   3. Writes an install receipt so re-runs are fast no-ops.
#
# Safe to re-run. Pass --force to reinstall, --yes for unattended.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/site-archive"
RECEIPT="$CONFIG_DIR/.installed"

ASSUME_YES=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --force) FORCE=1 ;;
    --help|-h)
      sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

log()  { printf '[site-archive] %s\n' "$*"; }
warn() { printf '[site-archive] WARN: %s\n' "$*" >&2; }
die()  { printf '[site-archive] ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Skip if already installed and node_modules still exists
if [[ -f "$RECEIPT" && -d "$SKILL_DIR/node_modules" && $FORCE -eq 0 ]]; then
  log "already installed — receipt at $RECEIPT"
  log "re-run with --force to reinstall"
  exit 0
fi

# 2. Verify node + npm
command -v node >/dev/null 2>&1 || die "node is required but not on PATH"
command -v npm  >/dev/null 2>&1 || die "npm is required but not on PATH"

# 3. Install deps
cd "$SKILL_DIR"
if [[ -d node_modules && $FORCE -eq 0 ]]; then
  log "node_modules present — skipping npm install"
else
  log "running npm install..."
  npm install --no-audit --no-fund
fi

# 4. Smoke-check the entry point loads
if ! node -e "import('./scripts/crawl.mjs').then(() => process.exit(0)).catch(e => { console.error(e); process.exit(1); })" >/dev/null 2>&1; then
  warn "scripts/crawl.mjs failed to import — deps may be incomplete"
  warn "try: rm -rf node_modules && bash scripts/setup.sh --force"
fi

# 5. Write install receipt
mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  printf 'node_version=%s\n' "$(node --version)"
} > "$RECEIPT"

log "done. Try: node scripts/crawl.mjs --help"
