---
name: read
description: Fetch any web URL or YouTube video, cache the content, and return it at the requested depth (skim, read, deep). Plus lightweight RSS/Atom feed subscriptions — subscribe to a site, refresh to get new items, read items by URL. Model-agnostic — the skill never calls an LLM, the calling agent does the synthesis. Caches at ~/data/read-cache/, subscriptions at ~/data/feeds/, optionally stores read-history memories to AutoMem.
---

# Read

A general-purpose reader. Two modes:

1. **One-off URL read** — paste any web article or YouTube link, get back clean content scaled to a depth budget.
2. **Lightweight feed reader** — subscribe to RSS/Atom feeds, refresh to pull new items, then read individual items.

The agent calling the skill does the analysis. The skill just delivers content.

Inspired by Flint's `tap_read_url` flow, with the heavy aggregator UI stripped out.

## When to Use

**One-off reads:**
- A user pastes a URL with no other instruction (default: read it)
- "Read this article" / "Watch this video" / "Summarize this page"
- "Pull the key points from..." / "What does this say?"
- Batch reading: "skim these 10 links and tell me which two matter"
- Re-read with `--force` when content has changed since the cache was written

**Feed subscriptions:**
- "Subscribe me to [blog]" / "Add this site to my feeds"
- "What's new in my feeds?" → `refresh`
- "What am I subscribed to?" → `feeds`
- Building a personal reading list / knowledge stream
- Periodic check-in skills that want to surface new items from trusted sources

For Google Docs, use a Google Docs skill (this one only handles open-web URLs). For full-site archiving, use the `site-archive` skill.

## Setup

```bash
bash scripts/setup.sh
```

Idempotent. Re-runs are no-ops. Pass `--force` to reinstall.

The setup checks node + npm, installs node deps (Readability, JSDOM, rss-parser, js-yaml), and verifies python3 + `youtube-transcript-api` (required for YouTube reads). If anything is missing, the script prints the exact install line to fix it.

### Prerequisites

- **Node 18+** with `npm`
- **Python 3** with `youtube-transcript-api` (only required for YouTube reads):
  ```bash
  pip3 install youtube-transcript-api
  ```
- Optional: an **AutoMem** endpoint for read-history storage. Without it, memories fall back to a JSONL file.

## Usage

### One-off reads

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

### Feed subscriptions

```bash
# Subscribe — paste a blog homepage, RSS URL, or YouTube channel URL
node scripts/read.mjs sub https://simonwillison.net/
node scripts/read.mjs sub https://www.youtube.com/channel/UCHnyfMqiRRG1u-2MsSQLbXA
node scripts/read.mjs sub http://example.com/feed.xml

# List subscriptions
node scripts/read.mjs feeds
node scripts/read.mjs feeds --json

# Refresh all feeds (returns new items since last poll)
node scripts/read.mjs refresh

# Refresh just one feed
node scripts/read.mjs refresh --feed simon-willison-s-weblog

# Unsubscribe (by slug or URL)
node scripts/read.mjs unsub simon-willison-s-weblog
node scripts/read.mjs unsub https://simonwillison.net/

# Then read an individual item the normal way
node scripts/read.mjs https://simonwillison.net/2026/...
```

The `refresh` output gives the agent a list of new item URLs. To actually read one, pipe its `url` back into `read <url>` — this keeps feed-management and content-fetching cleanly separated.

## Depth Modes (one-off reads)

The `--depth` flag controls how much content is returned to the calling agent. The cache always stores the **full** body — depth only governs the slice handed back.

| Depth | Returned content | Use for |
|-------|------------------|---------|
| `skim` | Title + first ~800 chars + last ~400 chars | Triage. Many URLs at once. Quick "is this worth reading?" |
| `read` | Title + first ~5000 chars | Standard read. Summary, key points, quick takeaways. |
| `deep` | Full content, no truncation | Default for one-offs. Long-form analysis, pull quotes, fact-checking, anything needing the whole text. |

**Default is `deep`.** Skim and read are for batch sessions, not one-offs.

## Feed Discovery

`read sub <url>` resolves to an actual feed via, in order:

1. **YouTube channel URL** → converts `/channel/UC...` to `https://www.youtube.com/feeds/videos.xml?channel_id=UC...`
2. **URL is already an RSS/Atom feed** — detected by `.rss/.xml/.atom` extension or RSS-ish content-type via HEAD request
3. **HTML autodiscovery** — fetches the page, looks for `<link rel="alternate" type="application/rss+xml">` or atom equivalent

If none of those find a feed, `sub` exits with code 2 and `NO_FEED_FOUND`. No scraping, no guessing.

YouTube `@handle` URLs aren't supported in v1 — pass the `/channel/UC...` URL instead. Most YouTube channels expose this in their About tab → Share → "Copy channel ID."

## Output

### One-off read (markdown default)

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

### Subscribe (text default)

```
Subscribed: Simon Willison's Weblog
  slug: simon-willison-s-weblog
  feed: https://simonwillison.net/atom/everything/
  items: 30
```

### Refresh (text default)

```
✓ Simon Willison's Weblog [simon-willison-s-weblog]: 3 new
    - Title of new post
      https://simonwillison.net/2026/...
    - Another new post
      https://simonwillison.net/2026/...
✓ Paul Graham: Essays [paul-graham-essays]: 0 new

3 new items across 2 feeds.
```

All commands accept `--json` for structured output. The JSON shape mirrors the text output's data fields.

## What the Skill Stores in Memory

| Action | Memory tags | Importance |
|--------|-------------|------------|
| `read <url>` | `["reading", <kind>, "depth:<depth>", "read-source:<slug>"]` | 0.5 |
| `sub <url>` | `["reading", "subscribe", <kind>, "feed-source:<slug>"]` | 0.5 |
| `refresh`, `feeds`, `unsub` | (no memory written) | — |

The skill does **not** synthesize takeaways — that's the calling agent's job after reading. Use `mcp__memory__store_memory` (or your stack's equivalent) to store proper insights, decisions, and quotes once you've analyzed the content.

If `AUTOMEM_ENDPOINT` is unset or unreachable, the read-history record is appended to `<cache-dir>/_memory-fallback.jsonl` and can be drained later. Pass `--no-store` to skip the memory write entirely.

## Storage

| Path | Purpose |
|------|---------|
| `~/data/read-cache/<sha1-prefix>.md` | One file per cached URL — YAML frontmatter + full body |
| `~/data/feeds/subscriptions.json` | Array of subscription records |
| `~/data/feeds/state/<slug>.json` | Per-feed last-poll timestamp |
| `~/data/feeds/items/<slug>/<hash>.json` | Per-item metadata (title, url, published, summary) — used to dedupe `refresh` |

| Variable | Default | Purpose |
|----------|---------|---------|
| `READ_CACHE_DIR` | `~/data/read-cache` | Where cached URL bodies live |
| `READ_FEEDS_DIR` | `~/data/feeds` | Where feed subscriptions and items live |
| `AUTOMEM_ENDPOINT` | (unset) | AutoMem HTTP base URL, e.g. `http://127.0.0.1:8001` |
| `AUTOMEM_API_KEY` | (unset) | Bearer token if your AutoMem requires auth |

Cached entries with body shorter than 500 chars are flagged as broken. The skill exits with code 3 and a `CACHE_BROKEN` message — retry with `--force` to re-fetch.

## Error Handling

| Exit code | Meaning |
|-----------|---------|
| 0 | Success |
| 1 | Bad arguments |
| 2 | Fetch / subscribe / unsub failed |
| 3 | Cache broken — retry with `--force` |

Common subscribe errors:

- `NO_FEED_FOUND` — input URL didn't resolve to an RSS/Atom feed
- `ALREADY_SUBSCRIBED` — slug or feed_url already in subscriptions

YouTube transcript errors surface with their original error code: `TRANSCRIPTS_DISABLED`, `NO_TRANSCRIPT`, `VIDEO_UNAVAILABLE`. **If a transcript fails, stop.** Don't try yt-dlp, web scraping, or description chasing — auto-captions are the only path this skill supports.

PDFs are not supported in v1.

## Recommended Workflow for the Calling Agent

**One-off reads:**

1. Run the skill at the right depth (default `deep` for one-offs, `skim` for batches).
2. Read the body the skill returns. Check `truncated` and `cache` in the frontmatter.
3. Analyze — answer the actual question, summarize, pull quotes.
4. Store useful takeaways via your memory tool with proper tags.
5. If the body was truncated and you need more, re-run with `--depth=deep`.

**Feed reading:**

1. `read sub <url>` once per source the user wants to follow.
2. Periodically (or on demand) `read refresh` to pull new items.
3. For each new item the user cares about, call `read <item-url>` to fetch full content.
4. Synthesize — same as one-off reads.

## Limitations

- Text only. No image, chart, or video-frame analysis.
- No paywall bypass.
- No PDF support (v1).
- YouTube auto-captions have errors, especially with technical terms and proper nouns.
- Brand-new YouTube videos (< 24 hours old) often don't have auto-captions yet.
- YouTube `@handle` URLs not yet supported for subscriptions — use `/channel/UC...` URLs.
- Single-threaded. `refresh` polls feeds sequentially.
- No background polling / cron — the calling agent decides when to refresh.

## Uninstall

```bash
rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/read-skill"
rm -rf "${READ_CACHE_DIR:-$HOME/data/read-cache}"
rm -rf "${READ_FEEDS_DIR:-$HOME/data/feeds}"
# then delete the skill folder itself
```

## Key Principles

- **One skill, two modes.** One-off reads and feed subscriptions share fetch, cache, and memory plumbing.
- **Cache aggressively.** Re-reads and re-polls should not re-fetch unnecessarily.
- **Depth is a content budget, not an analysis depth.** The skill gives raw content scaled to the budget; the calling agent does the thinking.
- **Fail fast.** If discovery, transcript, or fetch fails, stop. No workarounds.
- **Model-agnostic.** Whatever model is running the calling agent does the analysis.
- **Memory is for read history, not synthesis.** The calling agent stores actual takeaways after analyzing.
- **Feed reading composes with one-off reading.** `refresh` returns item URLs; the agent feeds them back into `read <url>` to get full content.
