#!/usr/bin/env bash
# setup.sh — idempotent installer for the read skill.
#
# What it does:
#   1. Verifies node + npm are available.
#   2. Runs `npm install` if node_modules is missing.
#   3. Checks python3 + youtube-transcript-api (the fast YouTube caption path).
#      If the lib is missing, prints the exact pip line to install it.
#   4. Reports which optional keys are set (Firecrawl fallback, Gemini watching).
#   5. Writes an install receipt so re-runs are fast no-ops.
#
# Safe to re-run. Pass --force to reinstall, --yes for unattended.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/read-skill"
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

log()  { printf '[read-skill] %s\n' "$*"; }
warn() { printf '[read-skill] WARN: %s\n' "$*" >&2; }
die()  { printf '[read-skill] ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Skip if already installed and node_modules still exists
if [[ -f "$RECEIPT" && -d "$SKILL_DIR/node_modules" && $FORCE -eq 0 ]]; then
  log "already installed — receipt at $RECEIPT"
  log "re-run with --force to reinstall"
  exit 0
fi

# 2. Verify node + npm
command -v node >/dev/null 2>&1 || die "node is required but not on PATH"
command -v npm  >/dev/null 2>&1 || die "npm is required but not on PATH"

# 3. Install node deps
cd "$SKILL_DIR"
if [[ -d node_modules && $FORCE -eq 0 ]]; then
  log "node_modules present — skipping npm install"
else
  log "running npm install..."
  npm install --no-audit --no-fund
fi

# 4. Smoke-check the entry point loads
if ! node -e "import('./scripts/read.mjs').then(() => process.exit(0)).catch(e => { console.error(e); process.exit(1); })" >/dev/null 2>&1; then
  warn "scripts/read.mjs failed to import — deps may be incomplete"
  warn "try: rm -rf node_modules && bash scripts/setup.sh --force"
fi

# 5. Verify python + youtube-transcript-api (direct YouTube captions; Firecrawl is the fallback)
PYTHON_CMD=""
for cmd in ${READ_PYTHON:-} python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PYTHON_CMD="$cmd"
    break
  fi
done

if [[ -z "$PYTHON_CMD" ]]; then
  warn "no python3/python on PATH — YouTube captions will rely on the Firecrawl fallback"
  warn "install with: sudo apt-get install python3 python3-pip && pip3 install youtube-transcript-api"
else
  if ! "$PYTHON_CMD" -c "import youtube_transcript_api" >/dev/null 2>&1; then
    warn "youtube-transcript-api is not installed — YouTube captions will rely on the Firecrawl fallback"
    warn "install with: $PYTHON_CMD -m pip install youtube-transcript-api (or set READ_PYTHON to a venv python that has it)"
  else
    log "python ($PYTHON_CMD) and youtube-transcript-api: OK"
  fi
fi

# 6. Optional keys
if [[ -n "${FIRECRAWL_API_KEY:-}" ]]; then
  log "FIRECRAWL_API_KEY set — Firecrawl fallback enabled for blocked articles and YouTube captions"
else
  log "FIRECRAWL_API_KEY not set — no fallback for bot-blocked pages or failed YouTube captions"
fi
if [[ -n "${GEMINI_API_KEY:-}${GOOGLE_AI_API_KEY:-}" ]]; then
  log "Gemini key set — YouTube watch classifier + video watching enabled"
else
  log "GEMINI_API_KEY / GOOGLE_AI_API_KEY not set — YouTube reads are transcript-only (no watching)"
fi

# 7. Cache dir hint (created lazily by the skill itself, but log it for diagnostics)
CACHE_DIR="${READ_CACHE_DIR:-$HOME/data/read-cache}"
log "cache dir: $CACHE_DIR (override with READ_CACHE_DIR)"

# 8. AutoMem hint
if [[ -z "${AUTOMEM_ENDPOINT:-}" ]]; then
  log "AUTOMEM_ENDPOINT not set — read-history memories will be appended to ${CACHE_DIR}/_memory-fallback.jsonl"
  log "to enable AutoMem, set AUTOMEM_ENDPOINT (and AUTOMEM_API_KEY if your endpoint requires auth)"
else
  log "AutoMem endpoint configured: $AUTOMEM_ENDPOINT"
fi

# 9. Write install receipt
mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  printf 'node_version=%s\n' "$(node --version 2>/dev/null || echo unknown)"
  printf 'python_cmd=%s\n' "${PYTHON_CMD:-none}"
} > "$RECEIPT"

log "done."
log "try: node $SKILL_DIR/scripts/read.mjs https://example.com/article"
