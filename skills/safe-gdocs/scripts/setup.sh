#!/usr/bin/env bash
# setup.sh — idempotent installer for safe-gdocs.
#
# What it does:
#   1. Checks for node + npm.
#   2. Installs @googleworkspace/cli globally if missing.
#   3. Symlinks the read-only `gws` shim and the `gdocs` wrapper into a bin dir
#      that comes BEFORE the npm global bin on PATH.
#   4. Verifies PATH ordering and prints a fix if the shim won't shadow.
#   5. Confirms gws is authenticated, prompts to run `gws auth login` if not.
#   6. Writes an install receipt so re-runs are fast no-ops.
#
# Safe to re-run. Reads STDIN for prompts; pass --yes to accept defaults.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD_SRC="$SKILL_DIR/scripts/gws-guard.sh"
GDOCS_SRC="$SKILL_DIR/scripts/gdocs.sh"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/safe-gdocs"
RECEIPT="$CONFIG_DIR/.installed"
BIN_DIR_DEFAULT="$HOME/.local/bin"

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

log()  { printf '[safe-gdocs] %s\n' "$*"; }
warn() { printf '[safe-gdocs] WARN: %s\n' "$*" >&2; }
die()  { printf '[safe-gdocs] ERROR: %s\n' "$*" >&2; exit 1; }

prompt() {
  local question="$1" default="${2:-}"
  if (( ASSUME_YES )); then
    printf '%s\n' "$default"
    return
  fi
  local answer
  read -r -p "$question " answer </dev/tty || answer=""
  printf '%s\n' "${answer:-$default}"
}

# 1. Skip if already installed (unless --force)
if [[ -f "$RECEIPT" && $FORCE -eq 0 ]]; then
  log "already installed — receipt at $RECEIPT"
  log "re-run with --force to reinstall"
  exit 0
fi

# 2. Check node + npm
command -v node >/dev/null 2>&1 || die "node is required but not on PATH"
command -v npm  >/dev/null 2>&1 || die "npm is required but not on PATH"

# 3. Install @googleworkspace/cli globally if missing
NPM_PREFIX="$(npm config get prefix)"
NPM_GWS="$NPM_PREFIX/bin/gws"

if [[ ! -x "$NPM_GWS" ]]; then
  log "installing @googleworkspace/cli globally..."
  npm install -g @googleworkspace/cli
fi
[[ -x "$NPM_GWS" ]] || die "expected gws at $NPM_GWS after install — not found"
log "real gws: $NPM_GWS"

# 4. Pick a bin dir for the shim
BIN_DIR=$(prompt "Install shim into which directory? [$BIN_DIR_DEFAULT]" "$BIN_DIR_DEFAULT")
mkdir -p "$BIN_DIR"

# 5. Install symlinks (replace if they already point elsewhere)
install_link() {
  local target="$1" linkpath="$2" name="$3"
  chmod +x "$target"
  if [[ -L "$linkpath" || -e "$linkpath" ]]; then
    local current
    current=$(readlink -f "$linkpath" 2>/dev/null || echo "")
    if [[ "$current" == "$(readlink -f "$target")" ]]; then
      log "$name already linked: $linkpath -> $target"
      return
    fi
    warn "$linkpath exists and points to $current — replacing"
    rm -f "$linkpath"
  fi
  ln -s "$target" "$linkpath"
  log "linked $name: $linkpath -> $target"
}

install_link "$GUARD_SRC" "$BIN_DIR/gws"   "gws shim"
install_link "$GDOCS_SRC" "$BIN_DIR/gdocs" "gdocs wrapper"

# 6. Verify PATH ordering — shim must come before npm global bin
SHIM_REAL=$(readlink -f "$BIN_DIR/gws")
GUARD_REAL=$(readlink -f "$GUARD_SRC")
WHICH_GWS=$(command -v gws || echo "")
WHICH_REAL=$(readlink -f "$WHICH_GWS" 2>/dev/null || echo "")

if [[ "$WHICH_REAL" != "$GUARD_REAL" ]]; then
  warn "gws on PATH does not resolve to the guard."
  warn "  PATH currently picks: ${WHICH_GWS:-<none>}"
  warn "  Guard expected at:    $GUARD_REAL"
  warn "  Add this to your shell rc file BEFORE the npm global bin:"
  warn "    export PATH=\"$BIN_DIR:\$PATH\""
  warn "  Then open a new shell and re-run setup.sh to verify."
else
  log "PATH ok — gws resolves to the guard"
fi

# 7. Auth check (best-effort)
if ! gws auth list >/dev/null 2>&1; then
  log "gws auth not configured."
  ans=$(prompt "Run 'gws auth login' now? [Y/n]" "Y")
  case "$ans" in
    [Yy]*|"") gws auth login ;;
    *) warn "skipping auth — run 'gws auth login' manually before using gdocs" ;;
  esac
else
  log "gws auth ok"
fi

# 8. Write install receipt
mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'real_gws=%s\n' "$NPM_GWS"
  printf 'bin_dir=%s\n' "$BIN_DIR"
  printf 'guard=%s\n' "$GUARD_REAL"
} > "$RECEIPT"

log "done. Try: gdocs list --limit 5"
