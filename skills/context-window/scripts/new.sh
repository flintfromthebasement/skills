#!/usr/bin/env bash
# new.sh — copy template.html to <dest>, defaulting to a timestamped file in cwd.
#
# Usage:
#   bash scripts/new.sh                    # ./context-window-YYYYMMDD-HHMM.html
#   bash scripts/new.sh ./my-report.html
#   bash scripts/new.sh /tmp/foo.html

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$SKILL_DIR/template.html"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "error: template not found at $TEMPLATE" >&2
  exit 1
fi

DEST="${1:-./context-window-$(date +%Y%m%d-%H%M).html}"

if [[ -e "$DEST" ]]; then
  echo "error: $DEST already exists — choose another path or delete it first" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
cp "$TEMPLATE" "$DEST"

echo "wrote $DEST"
echo
echo "next steps:"
echo "  1. edit the file — search for 'TODO' to find the placeholders"
echo "  2. fill in TABS[] and the <script type=\"text/plain\"> blocks"
echo "  3. open in a browser:"
echo "       macOS:   open '$DEST'"
echo "       linux:   xdg-open '$DEST'"
