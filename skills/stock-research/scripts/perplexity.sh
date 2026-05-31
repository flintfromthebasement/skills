#!/bin/bash
# perplexity.sh — CLI wrapper for Perplexity AI search API
# Usage:
#   perplexity.sh search "query"
#   perplexity.sh search --recent=week "query"
#   perplexity.sh summarize "https://example.com/article" [max_words]
#
# Optional. Needs PERPLEXITY_API_KEY in the environment (or in ~/.env).
# This is just a convenience for live news/context — the skill works fine
# with your agent's own web search if you don't have a Perplexity key.

set -euo pipefail

# Source ~/.env if it exists (optional — don't fail when it's absent).
ENV_FILE="${PERPLEXITY_ENV_FILE:-$HOME/.env}"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi
PERPLEXITY_API_KEY="${PERPLEXITY_API_KEY:-}"
PERPLEXITY_MODEL="sonar"
PERPLEXITY_ENDPOINT="https://api.perplexity.ai/chat/completions"

# --- Helpers ---

usage() {
  cat <<'EOF'
Usage:
  perplexity.sh search [--recent=hour|day|week|month] "query"
  perplexity.sh summarize "url" [max_words]

Commands:
  search      Ask a question or search the web
  summarize   Summarize the contents of a URL

Options:
  --recent=PERIOD   Filter results by recency (hour, day, week, month)

Examples:
  perplexity.sh search "What is the latest on PHP 8.4 features?"
  perplexity.sh search --recent=week "latest Claude API changes"
  perplexity.sh summarize "https://example.com/long-article"
  perplexity.sh summarize "https://example.com/long-article" 300
EOF
  exit 1
}

check_deps() {
  for cmd in curl jq; do
    if ! command -v "$cmd" &>/dev/null; then
      echo "Error: $cmd is required but not installed." >&2
      exit 1
    fi
  done
}

check_api_key() {
  if [ -z "$PERPLEXITY_API_KEY" ]; then
    echo "Error: PERPLEXITY_API_KEY not set. Add it to ~/.env." >&2
    exit 1
  fi
}

# Call the Perplexity API
# Args: $1 = user message, $2 = recency filter (optional)
call_perplexity() {
  local message="$1"
  local recency="${2:-}"

  local payload
  payload=$(jq -n \
    --arg model "$PERPLEXITY_MODEL" \
    --arg message "$message" \
    '{
      model: $model,
      messages: [
        { role: "system", content: "Be precise and concise. Cite your sources." },
        { role: "user", content: $message }
      ]
    }')

  # Add recency filter if provided
  if [ -n "$recency" ]; then
    payload=$(echo "$payload" | jq --arg r "$recency" '. + { search_recency_filter: $r }')
  fi

  local response
  response=$(curl -sf -X POST "$PERPLEXITY_ENDPOINT" \
    -H "Authorization: Bearer $PERPLEXITY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)

  local curl_exit=$?
  if [ $curl_exit -ne 0 ]; then
    echo "Error: API request failed." >&2
    echo "$response" >&2
    exit 1
  fi

  # Check for API error
  local error
  error=$(echo "$response" | jq -r '.error.message // empty' 2>/dev/null)
  if [ -n "$error" ]; then
    echo "API Error: $error" >&2
    exit 1
  fi

  # Extract answer
  local answer
  answer=$(echo "$response" | jq -r '.choices[0].message.content // empty')
  if [ -z "$answer" ]; then
    echo "Error: No answer in response." >&2
    echo "$response" | jq . >&2
    exit 1
  fi

  echo "$answer"

  # Extract and display citations
  local citations
  citations=$(echo "$response" | jq -r '.citations[]? // empty' 2>/dev/null)
  if [ -n "$citations" ]; then
    echo ""
    echo "---"
    echo "Sources:"
    local i=1
    while IFS= read -r url; do
      echo "  [$i] $url"
      ((i++))
    done <<< "$citations"
  fi
}

# --- Commands ---

cmd_search() {
  local recency=""
  local query=""

  while [ $# -gt 0 ]; do
    case "$1" in
      --recent=*)
        recency="${1#--recent=}"
        case "$recency" in
          hour|day|week|month) ;;
          *) echo "Error: --recent must be hour, day, week, or month." >&2; exit 1 ;;
        esac
        shift
        ;;
      -*)
        echo "Error: Unknown option: $1" >&2
        usage
        ;;
      *)
        query="$1"
        shift
        ;;
    esac
  done

  if [ -z "$query" ]; then
    echo "Error: No query provided." >&2
    usage
  fi

  call_perplexity "$query" "$recency"
}

cmd_summarize() {
  local url="${1:-}"
  local max_words="${2:-500}"

  if [ -z "$url" ]; then
    echo "Error: No URL provided." >&2
    usage
  fi

  local message="Summarize the contents of this URL in ${max_words} words or fewer: ${url}"
  call_perplexity "$message"
}

# --- Main ---

check_deps
check_api_key

if [ $# -lt 1 ]; then
  usage
fi

COMMAND="$1"
shift

case "$COMMAND" in
  search)    cmd_search "$@" ;;
  summarize) cmd_summarize "$@" ;;
  *)         echo "Error: Unknown command: $COMMAND" >&2; usage ;;
esac
