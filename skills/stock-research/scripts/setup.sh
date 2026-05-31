#!/usr/bin/env bash
# setup.sh — idempotent installer for the stock-research skill.
#
# What it does:
#   1. Verifies python3 + node are available.
#   2. Ensures yfinance is importable; if missing, installs it (pip), or prints
#      the exact pip line when running unattended without permission to install.
#   3. Smoke-tests stock-data.py and chart-urls.mjs.
#   4. Writes an install receipt so re-runs are fast no-ops.
#
# Optional: set PERPLEXITY_API_KEY (env or ~/.env) to enable scripts/perplexity.sh.
# The skill works without it — your agent's own web search covers news/context.
#
# Safe to re-run. Pass --force to reinstall, --yes for unattended.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/stock-research"
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

log()  { printf '[stock-research] %s\n' "$*"; }
warn() { printf '[stock-research] WARN: %s\n' "$*" >&2; }
die()  { printf '[stock-research] ERROR: %s\n' "$*" >&2; exit 1; }

# 1. Skip if already installed
if [[ -f "$RECEIPT" && $FORCE -eq 0 ]]; then
  if python3 -c 'import yfinance' >/dev/null 2>&1; then
    log "already installed — receipt at $RECEIPT"
    log "re-run with --force to reinstall"
    exit 0
  fi
  warn "receipt present but yfinance not importable — continuing setup"
fi

# 2. Verify runtimes
command -v python3 >/dev/null 2>&1 || die "python3 is required but not on PATH"
command -v node    >/dev/null 2>&1 || die "node is required but not on PATH (chart-urls.mjs needs it)"

# 3. Ensure yfinance
PIP_LINE="python3 -m pip install --user yfinance"
if python3 -c 'import yfinance' >/dev/null 2>&1; then
  log "yfinance already importable"
else
  log "yfinance not found — installing..."
  if python3 -m pip --version >/dev/null 2>&1; then
    if [[ $ASSUME_YES -eq 1 ]]; then
      python3 -m pip install --user yfinance >/dev/null 2>&1 || python3 -m pip install yfinance
    else
      python3 -m pip install --user yfinance || python3 -m pip install yfinance
    fi
  else
    die "pip not available. Install yfinance yourself: $PIP_LINE"
  fi
  python3 -c 'import yfinance' >/dev/null 2>&1 || die "yfinance still not importable after install. Try: $PIP_LINE"
fi

# 4. Smoke tests
chmod +x "$SKILL_DIR/scripts/stock-data.py" "$SKILL_DIR/scripts/perplexity.sh" 2>/dev/null || true

if node "$SKILL_DIR/scripts/chart-urls.mjs" AAPL --json >/dev/null 2>&1; then
  log "chart-urls.mjs OK"
else
  warn "chart-urls.mjs smoke test failed — check your Node version (needs ES modules)"
fi

if python3 "$SKILL_DIR/scripts/stock-data.py" --help >/dev/null 2>&1; then
  log "stock-data.py OK"
else
  warn "stock-data.py smoke test failed"
fi

# Optional Perplexity heads-up
if [[ -z "${PERPLEXITY_API_KEY:-}" ]] && ! { [[ -f "$HOME/.env" ]] && grep -q PERPLEXITY_API_KEY "$HOME/.env" 2>/dev/null; }; then
  log "note: PERPLEXITY_API_KEY not set — scripts/perplexity.sh is optional; the skill uses your agent's web search for news."
fi

# 5. Write receipt last
mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  printf 'yfinance=%s\n' "$(python3 -c 'import yfinance; print(getattr(yfinance,"__version__","unknown"))' 2>/dev/null || echo unknown)"
  printf 'node=%s\n' "$(node --version 2>/dev/null || echo unknown)"
} > "$RECEIPT"

log "done. receipt at $RECEIPT"
