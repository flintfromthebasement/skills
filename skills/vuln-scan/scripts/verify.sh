#!/usr/bin/env bash
# vuln-scan verify pass: re-prompts each .vuln.md to confirm exploitability.
#
# Usage:
#   verify.sh <run-dir>
#
# Env:
#   VULN_MODEL        default: opus
#   VULN_CONCURRENCY  default: 3
#
# The verifier is intentionally skeptical. Common false positives the prompt
# explicitly calls out:
#   - capability / permission checks the first scanner missed
#   - values that pass through sanitize / cast helpers upstream
#   - endpoints gated by middleware / permission_callback that scanner ignored
#   - data from trusted sources (settings, constants) flagged as user input

set -euo pipefail

run_dir="${1:?usage: verify.sh <run-dir>}"
if [[ ! -d "$run_dir" ]]; then echo "vuln-scan: not a dir: $run_dir" >&2; exit 2; fi

MODEL="${VULN_MODEL:-opus}"
CONCURRENCY="${VULN_CONCURRENCY:-3}"

unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true

if ! command -v claude >/dev/null 2>&1; then
  echo "vuln-scan: 'claude' CLI not found on PATH" >&2
  exit 127
fi

manifest="$run_dir/verify-manifest.tsv"
printf 'status\tseconds\tfindings\tverified\n' > "$manifest"

verify_one() {
  local findings="$1"
  local verified="${findings%.vuln.md}.verified.md"
  local log="${findings%.vuln.md}.verify.log"

  if grep -q '^No exploitable findings\.$' "$findings" 2>/dev/null; then
    printf 'skip\t0\t%s\t-\n' "$findings" >> "$manifest"
    echo "  [skip] $(basename "$findings") (no findings)"
    return 0
  fi

  local prompt
  prompt="You are a security reviewer doing a verification pass. A previous scan produced the findings at \`${findings}\`. For each finding, independently verify whether it is actually exploitable by reading the referenced source file and tracing the code path.

Be skeptical. Common false positives:
- Capability or permission checks that exist but the scanner missed
- Values that look unsanitized but pass through cast / sanitize / escape helpers upstream
- Endpoints gated by middleware or permission_callback that the scanner ignored
- Data from trusted sources (settings, constants, internal calls) flagged as user input
- Findings whose 'PoC' relies on conditions an attacker cannot satisfy

For each finding in the input file, output:
- **Finding:** (copy the original one-liner)
- **Verdict:** confirmed / false positive / needs more info
- **Reasoning:** 2-5 sentences citing specific code (file:line) that confirms or refutes the finding
- **Refined severity:** critical / high / medium / low / informational / none

Write the verification to \`${verified}\`. After writing, output 'DONE' and exit."

  local start end
  start=$(date +%s)
  if claude -p \
      --model "$MODEL" \
      --permission-mode bypassPermissions \
      --output-format text \
      "$prompt" >"$log" 2>&1; then
    end=$(date +%s)
    printf 'ok\t%d\t%s\t%s\n' $((end-start)) "$findings" "$verified" >> "$manifest"
    echo "  [ok]   $(basename "$findings") ($((end-start))s)"
  else
    end=$(date +%s)
    printf 'fail\t%d\t%s\t%s\n' $((end-start)) "$findings" "$log" >> "$manifest"
    echo "  [FAIL] $(basename "$findings") ($((end-start))s) — see $log"
  fi
}

export -f verify_one
export MODEL manifest

mapfile -t files < <(find "$run_dir" -maxdepth 1 -type f -name '*.vuln.md' | sort)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "vuln-scan: no *.vuln.md files in $run_dir" >&2
  exit 2
fi

echo "verifying ${#files[@]} finding files with $MODEL (concurrency $CONCURRENCY)"

pids=()
for f in "${files[@]}"; do
  verify_one "$f" &
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
