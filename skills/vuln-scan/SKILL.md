---
name: vuln-scan
description: Per-file CTF-style vulnerability scanner using Claude Code. Loops source files, asks an isolated `claude -p` session to find exploitable bugs and write a `${FILE}.vuln.md` sidecar, then runs a second-pass verifier that re-reads each finding to weed out false positives. Language-agnostic with optional profiles for WordPress/PHP, Node/JS, and Python.
---

# Vuln Scan

Use this skill when you want to point Claude at a codebase and surface real, exploitable bugs — not generic linter complaints. It's designed for **code you own or have explicit authorization to audit** (your own projects, CTFs, paid pentests, plugins you maintain).

The method is from Nicholas Carlini's [*Vulnerability research is cooked*](https://sockpuppet.org/blog/2026/03/30/vulnerability-research-is-cooked/) and Dan Iser's WordPress-plugin variation: hit each file with a CTF prompt, then run a skeptical second pass to throw out false positives. In our experience the verifier rejects roughly half of first-pass findings — without it you'll waste time on phantom bugs.

## When to use

- Auditing a WordPress plugin, Node service, Python app, or any single-language codebase before release
- Reviewing a small set of high-exposure files (REST handlers, payment webhooks, file upload endpoints)
- CTF challenges where the source is open
- Spot-checking AI-generated code for security issues

## When not to use

- Code you don't own and don't have permission to audit
- Production systems where the scanner would touch live data — this only reads source files, but be deliberate
- Tiny one-file changes — just ask Claude directly
- Massive codebases all at once — start with the highest-exposure surface (anything touching user input, auth, payments)

## Default workflow

1. Pick the files. Prioritize anything that touches network input, auth, the database, or the filesystem.
2. Run `scan.sh` against them. Each file becomes one isolated `claude -p` call writing a `*.vuln.md` sidecar.
3. Run `verify.sh` against the run directory. Each `*.vuln.md` becomes a `*.verified.md` with verdicts.
4. Read the verified files. Open issues / PRs only on `confirmed` findings; investigate `needs more info`; ignore `false positive`.

## Core commands

Scan a handful of files:

```bash
scripts/scan.sh path/to/file1.php path/to/file2.php
```

Scan a whole directory by glob:

```bash
scripts/scan.sh --batch ./src --pattern '*.php'
```

Run the verifier on the resulting run dir:

```bash
scripts/verify.sh ./results/<UTC-timestamp>/
```

That's the whole loop.

## Configuration

| Env var | Default | Notes |
| --- | --- | --- |
| `VULN_MODEL` | `opus` | Pass any model alias your `claude` CLI accepts. Opus catches subtler issues; Sonnet is faster and cheaper. |
| `VULN_CONCURRENCY` | `3` | Parallel `claude -p` workers. Higher = faster, more $$, more rate-limit risk. |
| `VULN_RUN_DIR` | `./results/<UTC-timestamp>/` | Override where findings are written. |
| `VULN_PROFILE` | `generic` | `generic` / `wordpress` / `node` / `python`. Adds a language-specific hint to the scan prompt (sanitization helpers, capability checks, etc.). |
| `VULN_PROMPT_FILE` | _(unset)_ | Path to a file whose contents replace the built-in scan prompt body. Placeholders: `{{FILE}}`, `{{OUT}}`. |

Example: scan a Node project with the JS-aware profile:

```bash
VULN_PROFILE=node scripts/scan.sh --batch ./api --pattern '*.js'
```

## Output layout

```text
results/20260428T180000Z/
├── manifest.tsv                    # status, seconds, file, output for each scan
├── verify-manifest.tsv             # status, seconds, findings, verified for each verify
├── <safe-path>.vuln.md             # first-pass findings (one file per source file)
├── <safe-path>.verified.md         # second-pass verdicts
├── <safe-path>.log                 # raw claude stdout/stderr from scan
└── <safe-path>.verify.log          # raw claude stdout/stderr from verify
```

`<safe-path>` is the source file path with `/` replaced by `__`, so the output dir stays flat.

A scan output looks like:

```markdown
- **Finding:** /api/v1/order returns other users' order data when ?id is changed
- **Severity:** high
- **Location:** order_endpoint(), src/api/order.php:142
- **Exploit sketch:** A logged-in subscriber sends GET /api/v1/order?id=123 ...
- **Why exploitable:** The handler looks up the order by ID but never checks order.user_id == current_user.id.
- **PoC:** curl -H "Cookie: ..." https://example.com/api/v1/order?id=123
```

A verify output adds:

```markdown
- **Verdict:** confirmed
- **Reasoning:** order.php:142 calls fetch_order($id) with no ownership check; the surrounding permission_callback only checks is_user_logged_in().
- **Refined severity:** high
```

## Cost & rate limits

Each file invokes one `claude -p` call. On Opus, scanning 30 small-to-medium PHP files plus the verify pass typically lands in the **$5–$15 USD** range — but this depends entirely on file size and your account's pricing. Sonnet is cheaper and meaningfully faster, at the cost of catching fewer subtle issues.

Start with 5–10 files to calibrate before pointing it at a whole repo.

## Limitations

- The scanner reads one file at a time. Cross-file vulnerabilities (taint that flows through three modules) are often missed unless the relevant code is reachable from imports the model follows.
- Findings are LLM output. The verifier helps a lot, but you still need to read the code yourself before filing CVEs or shipping patches.
- "No exploitable findings." is not a clean bill of health. Absence of evidence ≠ evidence of absence.
- The bypassed permission mode (`--permission-mode bypassPermissions`) is required so each scan can read its target file without prompting. Don't run this from a directory that contains secrets the spawned Claude shouldn't be reading. Point it at the target source tree only.

## Prior art and credit

- Nicholas Carlini, [*Vulnerability research is cooked*](https://sockpuppet.org/blog/2026/03/30/vulnerability-research-is-cooked/)
- Dan Iser's Popup Maker thread (4/4 hit rate on a single plugin, which is what got us off our asses to build this)

## Requirements

- `claude` (Claude Code CLI) on `PATH`, authenticated
- bash >= 4, `find`, `awk`
- A model your account can call (default `opus`)
