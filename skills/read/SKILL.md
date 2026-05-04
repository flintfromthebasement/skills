---
name: read
description: Fetch any web URL or YouTube video, cache the content, and return it at the requested depth (skim, read, deep). Model-agnostic — the skill never calls an LLM, the calling agent does the synthesis. Caches at ~/data/read-cache/, optionally stores read-history memories to AutoMem.
---

# Read

A general-purpose reader for one-off URLs. Pass it any web article or YouTube link, get back clean content scaled to a depth budget. The agent calling the skill does the analysis.

Inspired by Flint's `tap_read_url` flow, with the feed-subscription layer stripped out.

## When to Use

- A user pastes a URL with no other instruction (default: read it)
- "Read this article" / "Watch this video" / "Summarize this page"
- "Pull the key points from..." / "What does this say?"
- Batch reading: "skim these 10 links and tell me which two matter"
- Re-read with `--force` when content has changed since the cache was written

For Google Docs, use a Google Docs skill (this one only handles open-web URLs). For full-site archiving, use the `site-archive` skill.

## Setup

```bash
bash scripts/setup.sh
```

Idempotent. Re-runs are no-ops. Pass `--force` to reinstall.

The setup checks node + npm, installs node deps, and verifies python3 + `youtube-transcript-api` (required for YouTube reads). If anything is missing, the script prints the exact install line to fix it.

### Prerequisites

- **Node 18+** with `npm`
- **Python 3** with `youtube-transcript-api` (only required for YouTube reads):
  ```bash
  pip3 install youtube-transcript-api
  ```
- Optional: an **AutoMem** endpoint for read-history storage. Without it, memories fall back to a JSONL file.

## Depth Modes

The `--depth` flag controls how much content is returned to the calling agent. The cache always stores the **full** body — depth only governs the slice handed back.

| Depth | Returned content | Use for |
|-------|------------------|---------|
| `skim` | Title + first ~800 chars + last ~400 chars | Triage. Many URLs at once. Quick "is this worth reading?" |
| `read` | Title + first ~5000 chars | Standard read. Summary, key points, quick takeaways. |
| `deep` | Full content, no truncation | Default for one-offs. Long-form analysis, pull quotes, fact-checking, anything needing the whole text. |

**Default is `deep`.** Skim and read are for batch sessions, not one-offs.

## Usage

```bash
# Default — deep read with cache, store memory, markdown output
node scripts/read.mjs https://example.com/article

# Skim mode for triage
node scripts/read.mjs https://example.com/article --depth=skim

# Force re-fetch (bypass cache)
node scripts/read.mjs https://example.com/article --force

# Skip the read-history memory write
node scripts/read.mjs https://example.com/article --no-store

# JSON output (easier to parse from a calling agent)
node scripts/read.mjs https://example.com/article --json

# YouTube
node scripts/read.mjs "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Output

Default markdown output:

```
---
title: The Title
source: example.com
byline: Some Author
url: https://example.com/article
kind: article
fetched: 2026-05-03T20:24:00.000Z
refreshed: 2026-05-03T20:24:00.000Z
read_count: 1
depth: deep
cache: fresh
body_chars_total: 14523
body_chars_returned: 14523
truncated: false
memory: automem
---

# The Title

[full article body]
```

Frontmatter fields the caller should pay attention to:

- `cache: fresh | hit | refreshed` — fresh = first fetch; hit = served from cache; refreshed = `--force` re-fetch
- `truncated: true` — body was sliced to depth budget; pass `--depth=deep` if more is needed
- `memory: automem | fallback | skipped` — where the read-history memory landed

JSON output (`--json`) wraps the same data in `{ ok, frontmatter, body }`.

## What the Skill Stores in Memory

One short "I read this" memory per invocation, tagged `["reading", <kind>, "depth:<depth>", "read-source:<slug>"]`.

The skill does **not** synthesize takeaways — that's the calling agent's job after reading. Use `mcp__memory__store_memory` (or your stack's equivalent) to store proper insights, decisions, and quotes once you've analyzed the content.

If `AUTOMEM_ENDPOINT` is unset or unreachable, the read-history record is appended to `<cache-dir>/_memory-fallback.jsonl` and can be drained later.

## Cache

URL cache: `~/data/read-cache/<sha1-prefix>.md` — one file per URL with YAML frontmatter and the full body.

| Variable | Default | Purpose |
|----------|---------|---------|
| `READ_CACHE_DIR` | `~/data/read-cache` | Where cached entries live |
| `AUTOMEM_ENDPOINT` | (unset) | AutoMem HTTP base URL, e.g. `http://127.0.0.1:8001` |
| `AUTOMEM_API_KEY` | (unset) | Bearer token if your AutoMem requires auth |

Cached entries with body shorter than 500 chars are flagged as broken. The skill exits with code 3 and a `CACHE_BROKEN` message — retry with `--force` to re-fetch.

## Error Handling

| Exit code | Meaning |
|-----------|---------|
| 0 | Success |
| 1 | Bad arguments |
| 2 | Fetch failed (network, paywall, 404, transcript unavailable) |
| 3 | Cache broken — retry with `--force` |

YouTube transcript errors surface with their original error code: `TRANSCRIPTS_DISABLED`, `NO_TRANSCRIPT`, `VIDEO_UNAVAILABLE`. **If a transcript fails, stop.** Don't try yt-dlp, web scraping, or description chasing — auto-captions are the only path this skill supports. Tell the user what happened and move on.

PDFs are not supported in v1.

## Recommended Workflow for the Calling Agent

1. Run the skill at the right depth for the situation (default `deep` for one-offs, `skim` for batches).
2. Read the body the skill returns. Check `truncated` and `cache` in the frontmatter.
3. Analyze — answer the actual question, summarize, pull quotes, whatever was asked.
4. Store useful takeaways via your memory tool with proper tags. The skill only stores read-history.
5. If the body was truncated and you need more, re-run with `--depth=deep`.
6. If the cache was broken, re-run with `--force`.

## Limitations

- Text only. No image, chart, or video-frame analysis.
- No paywall bypass. Paywalled content surfaces as truncated/garbled article body.
- No PDF support (v1).
- YouTube auto-captions have errors, especially with technical terms and proper nouns.
- Brand-new YouTube videos (< 24 hours old) often don't have auto-captions yet.
- Single-threaded, no batching layer. Loop in shell if you need to process many URLs.

## Uninstall

```bash
rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/read-skill"
rm -rf "${READ_CACHE_DIR:-$HOME/data/read-cache}"
# then delete the skill folder itself
```

## Key Principles

- **Cache aggressively.** Re-reads should not re-fetch.
- **Depth is a content budget, not an analysis depth.** The skill gives raw content scaled to the budget; the calling agent does the thinking.
- **Fail fast.** If transcript is unavailable or fetch fails, stop. No workarounds.
- **Model-agnostic.** Whatever model is running the calling agent does the analysis. The skill never picks a model.
- **Memory is for read history, not synthesis.** The calling agent stores actual takeaways after analyzing.
