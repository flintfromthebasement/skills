#!/usr/bin/env bash
# vuln-scan: per-file CTF-style vulnerability scanner using Claude Code.
#
# Method (after Carlini / Dan Iser): for each file, spawn an isolated
# `claude -p` session and ask it to find exploitable vulnerabilities, writing
# its findings to a sidecar `${FILE}.vuln.md`. A second `verify.sh` pass
# re-reads each finding and decides confirmed / false positive / needs more info.
#
# Usage:
#   scan.sh <file> [<file>...]
#   scan.sh --batch <dir> [--pattern '*.php']
#
# Env:
#   VULN_MODEL        default: opus
#   VULN_CONCURRENCY  default: 3
#   VULN_RUN_DIR      override results dir (default: ./results/<UTC-timestamp>/)
#   VULN_PROFILE      hint for the prompt: generic | wordpress | node | python  (default: generic)
#   VULN_PROMPT_FILE  path to a file whose contents replace the built-in prompt body
#                     (placeholders: {{FILE}} and {{OUT}})
#
# Requires: claude (Claude Code CLI) on PATH, bash >=4, find, awk.
#
# WARNING: This runs an LLM-driven scan against any source file you point at.
# Only run it on code you own or have explicit authorization to audit. Each
# file invokes one `claude -p` call on the configured model, which costs money;
# scanning a large codebase on opus can run into real dollars. Start small.

set -euo pipefail

SCAN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${VULN_MODEL:-opus}"
CONCURRENCY="${VULN_CONCURRENCY:-3}"
PROFILE="${VULN_PROFILE:-generic}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${VULN_RUN_DIR:-$SCAN_DIR/results/$TS}"

# Claude Code refuses to spawn nested sessions when these are set.
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

if ! command -v claude >/dev/null 2>&1; then
  echo "vuln-scan: 'claude' CLI not found on PATH" >&2
  exit 127
fi

mkdir -p "$RUN_DIR"

files=()
if [[ "${1:-}" == "--batch" ]]; then
  shift
  dir="${1:?missing dir after --batch}"; shift
  pattern='*.php'
  if [[ "${1:-}" == "--pattern" ]]; then shift; pattern="${1:?missing pattern}"; shift; fi
  while IFS= read -r -d '' f; do files+=("$f"); done < <(find "$dir" -type f -name "$pattern" -print0)
else
  files=("$@")
fi

if [[ ${#files[@]} -eq 0 ]]; then
  echo "vuln-scan: no files supplied" >&2
  echo "usage: scan.sh <file> [<file>...]   |   scan.sh --batch <dir> [--pattern '*.ext']" >&2
  exit 2
fi

# Profile-specific hints appended to the generic checklist.
profile_hint() {
  case "$1" in
    wordpress)
      echo 'WordPress/PHP context: watch for unescaped $wpdb->query interpolation, missing esc_html / esc_attr / wp_kses output, missing current_user_can capability checks, missing nonce verification on state-changing endpoints, missing permission_callback on register_rest_route handlers, and trusting REST request meta/ID fields without ownership checks.'
      ;;
    node)
      echo 'Node/JS context: watch for string-concatenated SQL, child_process.exec with user input, unescaped HTML in templates, missing CSRF tokens on state-changing routes, prototype pollution via Object.assign / lodash.merge with attacker-controlled keys, and SSRF via user-supplied URLs in fetch/axios.'
      ;;
    python)
      echo 'Python context: watch for f-string SQL, subprocess with shell=True and user input, pickle/yaml.load on attacker data, Jinja2 templates rendered with autoescape off, missing CSRF middleware on Django/Flask state-changing views, and SSRF via user-supplied URLs in requests.'
      ;;
    generic|*)
      echo ''
      ;;
  esac
}
HINT="$(profile_hint "$PROFILE")"

echo "vuln-scan run"
echo "  run dir:  $RUN_DIR"
echo "  model:    $MODEL"
echo "  profile:  $PROFILE"
echo "  files:    ${#files[@]}"
echo "  concur:   $CONCURRENCY"

manifest="$RUN_DIR/manifest.tsv"
printf 'status\tseconds\tfile\toutput\n' > "$manifest"

# Portable relpath: prefer realpath --relative-to, fall back to absolute path.
relpath() {
  local p="$1" base="${2:-$PWD}"
  if command -v realpath >/dev/null 2>&1; then
    realpath --relative-to="$base" "$p" 2>/dev/null || printf '%s' "$p"
  else
    printf '%s' "$p"
  fi
}

scan_one() {
  local file="$1"
  local rel; rel="$(relpath "$file")"
  local safe="${file#/}"; safe="${safe//\//__}"
  local out="$RUN_DIR/${safe}.vuln.md"
  local log="$RUN_DIR/${safe}.log"

  local prompt
  if [[ -n "${VULN_PROMPT_FILE:-}" && -f "$VULN_PROMPT_FILE" ]]; then
    prompt="$(cat "$VULN_PROMPT_FILE")"
    prompt="${prompt//\{\{FILE\}\}/$file}"
    prompt="${prompt//\{\{OUT\}\}/$out}"
  else
    prompt="I'm in a CTF. Find exploitable vulnerabilities. Start with \`${file}\`.

Read the file. Look for: SQL injection, cross-site scripting (reflected, stored, DOM), authentication or authorization bypass, missing access control, CSRF, insecure deserialization, path traversal, arbitrary file upload / read / write, IDOR (insecure direct object reference), SSRF, command injection, information disclosure, and privilege escalation.

${HINT}

For each potential vulnerability, output:
- **Finding:** one-line summary
- **Severity:** critical / high / medium / low / informational
- **Location:** function name + approximate line number
- **Exploit sketch:** 2-4 sentences on how an attacker triggers it, including required auth level (unauthenticated / low-privilege user / admin)
- **Why exploitable:** what check is missing or wrong
- **PoC:** minimal request, payload, or code

Skip theoretical or already-mitigated issues. Only report things an attacker could actually use. If you find nothing exploitable, output the literal line 'No exploitable findings.' and nothing else.

Write your findings to \`${out}\`. After writing, output a single line 'DONE' and exit."
  fi

  local start end
  start=$(date +%s)
  if claude -p \
      --model "$MODEL" \
      --permission-mode bypassPermissions \
      --output-format text \
      "$prompt" >"$log" 2>&1; then
    end=$(date +%s)
    printf 'ok\t%d\t%s\t%s\n' $((end-start)) "$file" "$out" >> "$manifest"
    echo "  [ok]   $rel ($((end-start))s)"
  else
    end=$(date +%s)
    printf 'fail\t%d\t%s\t%s\n' $((end-start)) "$file" "$log" >> "$manifest"
    echo "  [FAIL] $rel ($((end-start))s) — see $log"
  fi
}

export -f scan_one relpath profile_hint
export RUN_DIR MODEL HINT VULN_PROMPT_FILE manifest

i=0
pids=()
for file in "${files[@]}"; do
  i=$((i+1))
  echo "[$i/${#files[@]}] $file"
  scan_one "$file" &
  pids+=($!)
  if [[ ${#pids[@]} -ge $CONCURRENCY ]]; then
    wait "${pids[0]}" || true
    pids=("${pids[@]:1}")
  fi
done
wait || true

echo
echo "done. manifest: $manifest"
awk -F'\t' 'NR>1 {c[$1]++} END {for (k in c) printf "  %s: %d\n", k, c[k]}' "$manifest"
echo
echo "next: scripts/verify.sh \"$RUN_DIR\""
