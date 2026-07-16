#!/usr/bin/env bash
# people-registry setup — scaffold a people/ directory for agent entity resolution.
#
# Usage:
#   bash scripts/setup.sh                  # creates ./people next to cwd
#   bash scripts/setup.sh --dir ~/agent/people
#   bash scripts/setup.sh --dir ./people --force
#   bash scripts/setup.sh --yes            # non-interactive (same as default; no prompts)
#
# Idempotent. No network. No deps beyond bash + coreutils.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/people-registry"
RECEIPT="$CONFIG_DIR/.installed"

ASSUME_YES=0
FORCE=0
TARGET_DIR=""

for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --force) FORCE=1 ;;
    --dir) ;; # handled below with shift-style parse
    --help|-h)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

# Parse --dir <path> (value form)
prev=""
for arg in "$@"; do
  if [[ "$prev" == "--dir" ]]; then
    TARGET_DIR="$arg"
  fi
  prev="$arg"
done

if [[ -z "$TARGET_DIR" ]]; then
  TARGET_DIR="$(pwd)/people"
fi

# Normalize to absolute
TARGET_DIR="$(mkdir -p "$TARGET_DIR" && cd "$TARGET_DIR" && pwd)"

log()  { printf '[people-registry] %s\n' "$*"; }
warn() { printf '[people-registry] WARN: %s\n' "$*" >&2; }
die()  { printf '[people-registry] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ -f "$RECEIPT" && $FORCE -eq 0 && -f "$TARGET_DIR/index.json" ]]; then
  log "already installed — receipt at $RECEIPT"
  log "people dir: $TARGET_DIR"
  log "re-run with --force to overwrite templates (keeps any person files you added)"
  exit 0
fi

TEMPLATES="$SKILL_DIR/templates"
[[ -d "$TEMPLATES" ]] || die "templates/ missing from skill at $SKILL_DIR"

mkdir -p "$TARGET_DIR"

copy_template() {
  local src="$1" dest="$2" label="$3"
  if [[ -f "$dest" && $FORCE -eq 0 ]]; then
    log "keep existing $label ($dest)"
    return
  fi
  if [[ -f "$dest" && $FORCE -eq 1 ]]; then
    # Never clobber a registry that already has people entries, even with --force,
    # unless it's still the empty scaffold. Person .md files are always preserved.
    if [[ "$label" == "index.json" ]] && grep -q '"people"' "$dest" 2>/dev/null; then
      local count
      count=$(grep -c '"full_name"' "$dest" 2>/dev/null || echo 0)
      if [[ "$count" -gt 0 ]]; then
        warn "refusing to overwrite $dest — it has $count people entr(y/ies). Edit it by hand."
        return
      fi
    fi
    warn "overwriting $label (--force)"
  fi
  cp "$src" "$dest"
  log "wrote $label → $dest"
}

copy_template "$TEMPLATES/index.json"    "$TARGET_DIR/index.json"    "index.json"
copy_template "$TEMPLATES/README.md"     "$TARGET_DIR/README.md"     "README.md"
copy_template "$TEMPLATES/ops-snippet.md" "$TARGET_DIR/OPS-SNIPPET.md" "OPS-SNIPPET.md"
copy_template "$TEMPLATES/person.md"     "$TARGET_DIR/_TEMPLATE.person.md" "person template"

# Drop a pointer to the worked example (don't copy private real data — example is fictional)
if [[ -f "$SKILL_DIR/examples/index.example.json" ]]; then
  copy_template "$SKILL_DIR/examples/index.example.json" \
    "$TARGET_DIR/index.example.json" "worked example"
fi

mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  printf 'people_dir=%s\n' "$TARGET_DIR"
} > "$RECEIPT"

log "done."
log ""
log "Next steps:"
log "  1. Edit $TARGET_DIR/index.json — add your primary collaborator first"
log "  2. Paste $TARGET_DIR/OPS-SNIPPET.md into your agent's ops / CLAUDE.md / AGENTS.md"
log "  3. Add a manual-load note:  Read(\"$TARGET_DIR/index.json\")"
log "  4. Create people/<slug>.md from _TEMPLATE.person.md only for frequent collaborators"
log ""
log "See SKILL.md for the name-resolution algorithm and identity-verification rules."
