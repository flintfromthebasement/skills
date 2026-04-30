#!/usr/bin/env bash
# setup.sh — idempotent installer for lyric-video.
#
# What it does:
#   1. Verifies ffmpeg, ffprobe, and python3 are on PATH.
#   2. Symlinks `make-lyric-video` into a bin dir on PATH.
#   3. Verifies PATH ordering and prints a fix line if the shim won't shadow.
#   4. Writes an install receipt so re-runs are fast no-ops.
#
# Safe to re-run. Pass --yes to accept defaults non-interactively, --force to reinstall.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENTRY_SRC="$SKILL_DIR/scripts/make-lyric-video.py"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/lyric-video"
RECEIPT="$CONFIG_DIR/.installed"
BIN_DIR_DEFAULT="$HOME/.local/bin"
LINK_NAME="make-lyric-video"

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

log()  { printf '[lyric-video] %s\n' "$*"; }
warn() { printf '[lyric-video] WARN: %s\n' "$*" >&2; }
die()  { printf '[lyric-video] ERROR: %s\n' "$*" >&2; exit 1; }

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

# 2. Verify required binaries
command -v ffmpeg  >/dev/null 2>&1 || die "ffmpeg is required but not on PATH (try: sudo apt install ffmpeg)"
command -v ffprobe >/dev/null 2>&1 || die "ffprobe is required but not on PATH (ships with ffmpeg)"
command -v python3 >/dev/null 2>&1 || die "python3 is required but not on PATH"

FFMPEG_VER="$(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}')"
log "ffmpeg ok ($FFMPEG_VER)"

# 3. Pick a bin dir for the entry point
BIN_DIR=$(prompt "Install entry point into which directory? [$BIN_DIR_DEFAULT]" "$BIN_DIR_DEFAULT")
mkdir -p "$BIN_DIR"

# 4. Install symlink (replace if it points elsewhere)
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

install_link "$ENTRY_SRC" "$BIN_DIR/$LINK_NAME" "$LINK_NAME"

# 5. Verify PATH ordering — symlink must resolve to our entry point
ENTRY_REAL=$(readlink -f "$ENTRY_SRC")
WHICH_ENTRY=$(command -v "$LINK_NAME" 2>/dev/null || echo "")
WHICH_REAL=$(readlink -f "$WHICH_ENTRY" 2>/dev/null || echo "")

if [[ "$WHICH_REAL" != "$ENTRY_REAL" ]]; then
  warn "$LINK_NAME on PATH does not resolve to this skill."
  warn "  PATH currently picks: ${WHICH_ENTRY:-<none>}"
  warn "  Expected:             $ENTRY_REAL"
  warn "  Add this to your shell rc file:"
  warn "    export PATH=\"$BIN_DIR:\$PATH\""
  warn "  Then open a new shell and re-run this setup to verify."
else
  log "PATH ok — $LINK_NAME resolves to this skill"
fi

# 6. Write install receipt
mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n'  "$(date -Iseconds)"
  printf 'skill_dir=%s\n'     "$SKILL_DIR"
  printf 'bin_dir=%s\n'       "$BIN_DIR"
  printf 'entry=%s\n'         "$ENTRY_REAL"
  printf 'ffmpeg_version=%s\n' "$FFMPEG_VER"
} > "$RECEIPT"

log "done. Try: $LINK_NAME --help"
