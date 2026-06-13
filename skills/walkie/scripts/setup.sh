#!/usr/bin/env bash
# walkie skill installer.
# Installs walkie-sh globally, verifies it's on PATH, and records an install
# receipt. Idempotent: re-runs are no-ops unless --force.
#
# Usage: bash scripts/setup.sh [--force] [--yes|-y] [--help|-h]
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/walkie-skill"
RECEIPT="$CONFIG_DIR/.installed"

ASSUME_YES=0; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --force) FORCE=1 ;;
    --help|-h) sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  esac
done

log()  { printf '[walkie] %s\n' "$*"; }
warn() { printf '[walkie] WARN: %s\n' "$*" >&2; }
die()  { printf '[walkie] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ -f "$RECEIPT" && $FORCE -eq 0 ]]; then
  log "already installed — receipt at $RECEIPT"
  log "re-run with --force to reinstall"
  exit 0
fi

# Preconditions
command -v node >/dev/null 2>&1 || die "Node.js not found. Install Node >= 20 first."
command -v npm  >/dev/null 2>&1 || die "npm not found. Install Node/npm first."
node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [[ "$node_major" -lt 20 ]]; then
  warn "Node $node_major detected; walkie-sh expects Node >= 20. Continuing, but upgrade if you hit issues."
fi

# Install walkie-sh globally if the binary is missing
if command -v walkie >/dev/null 2>&1; then
  log "walkie already installed: $(command -v walkie)"
else
  log "installing walkie-sh globally (npm install -g walkie-sh)..."
  npm install -g walkie-sh || die "npm install -g walkie-sh failed. Check npm permissions (you may need a user-owned global prefix)."
fi

# Verify it's reachable on PATH; diagnose if not
if command -v walkie >/dev/null 2>&1; then
  log "walkie on PATH: $(command -v walkie)"
else
  prefix="$(npm config get prefix 2>/dev/null || echo "$HOME/.npm-global")"
  warn "walkie-sh installed but 'walkie' is not on your PATH."
  warn "Add this to your shell profile (~/.bashrc or ~/.zshrc), then restart your shell:"
  printf '\n    export PATH="%s/bin:$PATH"\n\n' "$prefix"
  die "PATH not configured — fix the line above and re-run."
fi

# Identity nudge (non-mutating — we don't touch the user's shell rc)
if [[ -z "${WALKIE_ID:-}" ]]; then
  log "TIP: set a human-readable identity so peers know who's talking:"
  log "     export WALKIE_ID=your-agent-name   (add to your shell profile / agent .env)"
else
  log "WALKIE_ID is set to '$WALKIE_ID'."
fi

# Write the receipt last
mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  printf 'walkie_bin=%s\n' "$(command -v walkie)"
  printf 'walkie_version=%s\n' "$(walkie --version 2>/dev/null || echo unknown)"
} > "$RECEIPT"

log "done. Next: walkie connect <channel>:<secret>   (see SKILL.md §3)"
