#!/usr/bin/env bash
# gdocs — friendly Google Docs CLI wrapped around `gws` (Google Workspace CLI).
#
# Designed to pair with gws-guard.sh, which shadows `gws` on PATH and blocks
# any write methods. Read-only by construction.
#
# Usage:
#   gdocs read <doc-id-or-url> [--md|--html|--csv]   Read doc content
#   gdocs search <query> [--limit N]                 Search docs by name
#   gdocs list [--limit N]                           List recent docs
#   gdocs info <doc-id-or-url>                       Show doc metadata
#
# Requires: gws (npm i -g @googleworkspace/cli) authenticated via `gws auth login`.

set -euo pipefail

extract_doc_id() {
  local input="$1"
  if [[ "$input" =~ docs\.google\.com/document/d/([a-zA-Z0-9_-]+) ]]; then
    echo "${BASH_REMATCH[1]}"
  elif [[ "$input" =~ drive\.google\.com/.*id=([a-zA-Z0-9_-]+) ]]; then
    echo "${BASH_REMATCH[1]}"
  elif [[ "$input" =~ drive\.google\.com/open\?id=([a-zA-Z0-9_-]+) ]]; then
    echo "${BASH_REMATCH[1]}"
  else
    echo "$input"
  fi
}

cmd_read() {
  local input="${1:?Usage: gdocs read <doc-id-or-url> [--md|--html|--csv]}"
  shift
  local mime="text/plain"
  local ext="txt"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --md|--markdown) mime="text/markdown"; ext="md"; shift ;;
      --html) mime="text/html"; ext="html"; shift ;;
      --csv) mime="text/csv"; ext="csv"; shift ;;
      *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
  done

  local doc_id
  doc_id=$(extract_doc_id "$input")

  local tmpfile
  tmpfile=$(mktemp "/tmp/gdocs-XXXXXX.$ext")

  local result
  result=$(gws drive files export \
    --params "{\"fileId\": \"$doc_id\", \"mimeType\": \"$mime\"}" \
    -o "$tmpfile" 2>&1)

  if echo "$result" | grep -q '"error"'; then
    echo "$result" >&2
    rm -f "$tmpfile"
    exit 1
  fi

  sed '1s/^\xEF\xBB\xBF//' "$tmpfile"
  rm -f "$tmpfile"
}

cmd_search() {
  local query="${1:?Usage: gdocs search <query> [--limit N]}"
  shift
  local limit=10

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --limit) limit="${2:?--limit requires a number}"; shift 2 ;;
      *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
  done

  query="${query//\"/\\\"}"

  gws drive files list \
    --params "{\"q\": \"mimeType=\\\"application/vnd.google-apps.document\\\" and name contains \\\"$query\\\"\", \"pageSize\": $limit, \"fields\": \"files(id,name,modifiedTime,owners(displayName))\"}" \
    --format table 2>/dev/null
}

cmd_list() {
  local limit=10

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --limit) limit="${2:?--limit requires a number}"; shift 2 ;;
      *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
  done

  gws drive files list \
    --params "{\"q\": \"mimeType=\\\"application/vnd.google-apps.document\\\"\", \"pageSize\": $limit, \"orderBy\": \"modifiedTime desc\", \"fields\": \"files(id,name,modifiedTime,owners(displayName))\"}" \
    --format table 2>/dev/null
}

cmd_info() {
  local input="${1:?Usage: gdocs info <doc-id-or-url>}"
  local doc_id
  doc_id=$(extract_doc_id "$input")

  gws drive files get \
    --params "{\"fileId\": \"$doc_id\", \"fields\": \"id,name,mimeType,modifiedTime,createdTime,size,owners(displayName,emailAddress),lastModifyingUser(displayName,emailAddress),shared,webViewLink\"}" \
    2>/dev/null
}

cmd_help() {
  cat <<'EOF'
gdocs — Google Docs CLI wrapper (read-only via gws-guard)

Commands:
  read <doc-id-or-url> [--md|--html|--csv]   Read doc content (default: plain text)
  search <query> [--limit N]                 Search docs by name
  list [--limit N]                           List recent docs
  info <doc-id-or-url>                       Show doc metadata

Examples:
  gdocs read 1FYFMlGGiTPPgcmwyXCVWXM8Gn_rSe-QQFryUAfLnyyY
  gdocs read "https://docs.google.com/document/d/1FYF.../edit"
  gdocs search "site audit"
  gdocs list --limit 5
  gdocs info 1FYFMlGGiTPPgcmwyXCVWXM8Gn_rSe-QQFryUAfLnyyY
EOF
}

case "${1:-help}" in
  read)    shift; cmd_read "$@" ;;
  search)  shift; cmd_search "$@" ;;
  list)    shift; cmd_list "$@" ;;
  info)    shift; cmd_info "$@" ;;
  help|-h|--help) cmd_help ;;
  *) echo "Unknown command: $1" >&2; cmd_help >&2; exit 1 ;;
esac
