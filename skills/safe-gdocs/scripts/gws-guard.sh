#!/usr/bin/env bash
# gws-guard.sh — Read-only guard for gws (Google Workspace CLI)
# Shadows the real gws binary so write methods are blocked at the CLI layer.
# Pass-through for read-only operations.
#
# How to wire it up:
#   1. Install @googleworkspace/cli globally (npm i -g @googleworkspace/cli).
#   2. Symlink this file as `gws` somewhere that comes BEFORE the npm global bin
#      on PATH (e.g. ~/.local/bin/gws -> .../scripts/gws-guard.sh).
#   3. Run `gws auth login` once to authenticate.
#
# Resolving the real binary:
#   - $SAFE_GDOCS_REAL_GWS overrides everything
#   - else: walk PATH, skip our own shim, return the first other `gws`
#   - else: try `$(npm config get prefix)/bin/gws`

set -euo pipefail

resolve_real_gws() {
  if [[ -n "${SAFE_GDOCS_REAL_GWS:-}" && -x "$SAFE_GDOCS_REAL_GWS" ]]; then
    echo "$SAFE_GDOCS_REAL_GWS"
    return 0
  fi

  local self
  self=$(readlink -f "$0" 2>/dev/null || echo "$0")

  # Walk PATH for the first `gws` that isn't us
  local IFS=:
  for dir in $PATH; do
    [[ -z "$dir" ]] && continue
    local candidate="$dir/gws"
    if [[ -x "$candidate" ]]; then
      local resolved
      resolved=$(readlink -f "$candidate" 2>/dev/null || echo "$candidate")
      if [[ "$resolved" != "$self" ]]; then
        echo "$candidate"
        return 0
      fi
    fi
  done

  # Fallback: npm global bin
  if command -v npm >/dev/null 2>&1; then
    local npm_bin
    npm_bin="$(npm config get prefix 2>/dev/null)/bin/gws"
    if [[ -x "$npm_bin" ]]; then
      echo "$npm_bin"
      return 0
    fi
  fi

  return 1
}

REAL_GWS=$(resolve_real_gws) || {
  echo "safe-gdocs: could not find the real gws binary." >&2
  echo "  Install with: npm install -g @googleworkspace/cli" >&2
  echo "  Or set SAFE_GDOCS_REAL_GWS to its absolute path." >&2
  exit 127
}

# Methods that modify data — block these
BLOCKED="create|copy|delete|update|batchUpdate|send|modify|modifyLabels|emptyTrash|trash|untrash|patch|insert|remove"

# Always-safe prefixes — pass straight through
first_arg="${1:-}"
case "$first_arg" in
  auth|schema|help|-h|--help|"")
    exec "$REAL_GWS" "$@"
    ;;
esac

# Allow --help anywhere in args
for arg in "$@"; do
  if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
    exec "$REAL_GWS" "$@"
  fi
done

# Block any arg that names a write method
for arg in "$@"; do
  if [[ "$arg" =~ ^(\+?)(${BLOCKED})$ ]]; then
    echo "safe-gdocs: write methods are blocked by the read-only guard." >&2
    echo "  Blocked method: $arg" >&2
    echo "  To allow writes, edit scripts/gws-guard.sh or invoke the real binary directly." >&2
    exit 1
  fi
done

exec "$REAL_GWS" "$@"
