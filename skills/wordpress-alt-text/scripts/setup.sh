#!/usr/bin/env bash
# wordpress-alt-text setup — creates a .venv with the Python deps. Idempotent.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECEIPT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/wordpress-alt-text"
RECEIPT="$RECEIPT_DIR/.installed"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

if [[ -f "$RECEIPT" && $FORCE -eq 0 && -x "$SKILL_DIR/.venv/bin/python" ]]; then
  echo "already installed ($(cat "$RECEIPT" | head -1)). Use --force to reinstall."
  exit 0
fi

command -v python3 >/dev/null || { echo "FIX: install python3 (3.9+)"; exit 1; }

if [[ ! -x "$SKILL_DIR/.venv/bin/python" || $FORCE -eq 1 ]]; then
  python3 -m venv "$SKILL_DIR/.venv"
fi
"$SKILL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$SKILL_DIR/.venv/bin/pip" install --quiet requests Pillow pymysql

mkdir -p "$RECEIPT_DIR"
{
  echo "installed $(date -Iseconds)"
  echo "venv: $SKILL_DIR/.venv"
  echo "deps: requests Pillow pymysql"
} > "$RECEIPT"
echo "installed. Run scripts with: $SKILL_DIR/.venv/bin/python"
echo "Optional: pip install cairosvg (only if the site serves SVG images)."
