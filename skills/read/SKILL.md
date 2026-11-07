---
name: read
description: Fetch any web URL or YouTube video, cache the content, and return it at the requested depth (skim, read, deep). YouTube gets a transcript (direct captions, then Firecrawl) plus an optional watch pass where a cheap classifier decides whether a video model should actually see and hear it (music, demos, tutorials, captionless videos) and Gemini writes a neutral audiovisual description. Bot-blocked or JS-only articles fall back to Firecrawl. Default depth is deep; skim is the only truncated mode. Plus lightweight RSS/Atom feed subscriptions. The calling agent does all synthesis.
---

# Read

A general-purpose reader. Two modes:

1. **One-off URL read** — paste any web article or YouTube link, get back clean content scaled to a depth budget. YouTube videos can also be *watched*: see [Watching videos](#watching-videos).
2. **Lightweight feed reader** — subscribe to RSS/Atom feeds, refresh to pull new items, then read individual items.

The agent calling the skill does the analysis. The skill just delivers content: text, transcripts, and (for videos worth it) a neutral description of what a video model saw and heard. It never writes a take or summary of its own.

Ported from the Stranger Agents `read_url` tool and feeds watch pass, with the aggregator UI stripped out.

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

The setup checks node + npm, installs node deps (Readability, JSDOM, rss-parser, js-yaml), checks python3 + `youtube-transcript-api`, and reports which optional keys are set. If anything is missing, the script prints the exact line to fix it.

### Prerequisites

- **Node 18+** with `npm`
- Recommended for YouTube: **Python 3** with `youtube-transcript-api` (the fast, free caption path):
  ```bash
  pip3 install youtube-transcript-api
  ```
  Point `READ_PYTHON` at a venv interpreter if the package isn't in the system python.
- Optional `FIRECRAWL_API_KEY`: fallback for bot-blocked / JS-only articles and for YouTube captions when the direct path fails or the box is IP-blocked.
- Optional `GEMINI_API_KEY` (or `GOOGLE_AI_API_KEY`): enables the watch classifier and video watching. Without it the skill reads transcripts only and says so.
- Optional: an **AutoMem** endpoint for read-history storage. Without it, memories fall back to a JSONL file.

## Usage

### One-off reads

```bash
# Default — deep read with cache, store memory, markdown output
node scripts/read.mjs https://flint.fountain.network/blog/2026-02-20-the-respond-gap-why-autonomous-agents-have-no-panic-button/

# Skim mode for triage
node scripts/read.mjs https://flint.fountain.network/blog/2026-02-20-the-respond-gap-why-autonomous-agents-have-no-panic-button/ --depth=skim

# Force re-fetch (bypass cache)
node scripts/read.mjs https://flint.fountain.network/blog/2026-02-20-the-respond-gap-why-autonomous-agents-have-no-panic-button/ --force

# Skip the read-history memory write
node scripts/read.mjs https://flint.fountain.network/blog/2026-02-20-the-respond-gap-why-autonomous-agents-have-no-panic-button/ --no-store

# JSON output (easier to parse from a calling agent)
node scripts/read.mjs https://flint.fountain.network/blog/2026-02-20-the-respond-gap-why-autonomous-agents-have-no-panic-button/ --json

# YouTube — transcript, plus a watch when the classifier says the visuals/sound matter
node scripts/read.mjs "https://www.youtube.com/watch?v=VIDEO_ID"

# Tell the classifier why you're reading it (a question about how it looks/sounds leans toward watching)
node scripts/read.mjs "https://youtu.be/VIDEO_ID" --context="user asked what the guitar tone is like"

# Always watch / never watch
node scripts/read.mjs "https://youtu.be/VIDEO_ID" --watch=force
node scripts/read.mjs "https://youtu.be/VIDEO_ID" --watch=never
```

### Feed subscriptions

```bash
# Subscribe — paste a blog homepage, RSS URL, or YouTube channel URL
node scripts/read.mjs sub https://flint.fountain.network
node scripts/read.mjs sub https://www.youtube.com/channel/UCHnyfMqiRRG1u-2MsSQLbXA
node scripts/read.mjs sub https://flint.fountain.network/rss.xml

# List subscriptions
node scripts/read.mjs feeds
node scripts/read.mjs feeds --json

# Refresh all feeds (returns new items since last poll)
node scripts/read.mjs refresh

# Refresh just one feed
node scripts/read.mjs refresh --feed flint-from-the-basement

# Unsubscribe (by slug or URL)
node scripts/read.mjs unsub flint-from-the-basement
node scripts/read.mjs unsub https://flint.fountain.network

# Then read an individual item the normal way
node scripts/read.mjs https://flint.fountain.network/blog/2026-02-20-the-respond-gap-why-autonomous-agents-have-no-panic-button/
```

The `refresh` output gives the agent a list of new item URLs. To actually read one, pipe its `url` back into `read <url>` — this keeps feed-management and content-fetching cleanly separated.

## Depth Modes (one-off reads)

The `--depth` flag controls how much content is returned to the calling agent. The cache always stores the **full** body — depth only governs the slice handed back.

| Depth | Returned content | Use for |
|-------|------------------|---------|
| `skim` | Title + first ~800 chars + last ~400 chars | Triage. Many URLs at once. Quick "is this worth reading?" |
| `read` | Full content (promoted to `deep` if over 5k) | One-off reads. Not a 5k head — a long article or video would lie. |
| `deep` | Full content, no truncation | Default. Anything you will summarise, quote, review, or treat as the whole text. |

**Default is `deep`.** Use it for any summarise / review / "watch this" request. `--depth=read` on a body longer than 5k chars (article or YouTube) is auto-promoted to `deep` (`depth_requested` is recorded). `skim` is the only mode that still slices.

If the body is `truncated: true` or carries a `[TRUNCATED]` marker, you have **not** seen the rest. Say the summary covers only that portion. Do not guess at the remainder or fill it in from web search.

## Fetch Chain

**Articles:** direct fetch + Readability. On 401/403/429/451, 5xx, network errors, extraction failure, or a page under 50 words (JS-rendered shell), the skill retries through Firecrawl `/v2/scrape` when `FIRECRAWL_API_KEY` is set. `via: direct|firecrawl` in the frontmatter says which path served it.

**YouTube transcripts:**

1. `youtube-transcript-api` direct (English first, then any language, manual captions before auto). Also gives the video length from the last caption.
2. Firecrawl scrape of the watch page (stealth proxy, `waitFor`, uncached, up to 3 tries; YouTube intermittently serves it a 401 shell). Reads the `## Transcript` section and the video length from scrape metadata.
3. Neither worked → no transcript. The watch pass can still cover the video.

`youtu.be`, `/shorts/`, `/embed/`, `/live/`, and `watch?v=` URLs all normalise to one canonical URL, so they share a cache entry.

## Watching Videos

Ported from the Stranger Agents feeds watch pass. For every YouTube read, after the transcript:

| Step | What happens |
|------|--------------|
| `--watch=never` | Transcript only. |
| Saved watch exists | Returns it (`watch.status: cached`). No re-watch. |
| No Gemini key | Skipped, reason says so. |
| `--watch=force` | Watches. |
| `--depth=skim` | Auto-watch skipped (triage). `--watch=force` still watches. |
| Earlier auto verdict was skip, or the watch failed | Skipped with that reason; `--force` re-decides. |
| Otherwise (`auto`) | **Classifier** (`gemini-3.1-flash-lite-preview`, temp 0) reads title, channel, transcript excerpt, and `--context`, returns watch yes/no + reason. Yes for music, performance, dance, visual tutorials, demos, art/animation, film breakdowns, gameplay, and captionless videos; no for talking heads, podcasts, lectures, commentary. If the classifier call fails, a title-regex heuristic decides (no transcript → always watch). |

**The watch:** Gemini (`gemini-3.8-flash`, falling back to `gemini-3.6-flash` on overload or empty output) gets the YouTube URL directly, no download. Videos under 10 minutes use `STATIC` frame sampling; 10+ minutes use `AGENTIC` (the model seeks through the video itself). Length comes from caption timing or scrape metadata, else an estimate from transcript words at 150 wpm; unknown length starts `STATIC` and retries `AGENTIC` if it overflows the token limit. 429/5xx retries with backoff. Streams over SSE with a 10-minute ceiling; a typical 3–5 minute video takes 20–60 seconds.

The model writes a **neutral** report (Summary, Timeline with timestamps, Editing and pacing, On-screen text, Sound and music, Verification details): what's there, no opinions. Your take is your job.

Every outcome (watched, skipped by the classifier, failed) is saved to `<cache-dir>/yt-<video_id>.watch.md`, so the same video is never re-judged or re-watched. `--force` clears that for the run.

### Coverage: never claim a watch that didn't happen

YouTube reads carry `watched`, `watch` (`status`, `reason`, `decided_by`, `model`, `processing`, token `usage`), `transcript_available`, and a `coverage` line in the frontmatter. **Follow `coverage` literally.** If it says you did NOT watch, say you read the transcript; never say you watched or listened. If you watched, the body opens with `## Watch report` and the transcript follows under `## Transcript`.

| Env | Default | Purpose |
|-----|---------|---------|
| `GEMINI_API_KEY` / `GOOGLE_AI_API_KEY` | (unset) | Classifier + watching |
| `READ_VIDEO_MODEL` | `gemini-3.8-flash` | Watch model |
| `READ_VIDEO_MODEL_FALLBACK` | `gemini-3.6-flash` | Fallback on overload/empty; `""` disables |
| `READ_VIDEO_AGENTIC_MIN_SECONDS` | `600` | Length at which watching switches to `AGENTIC` |
| `READ_WATCH_CLASSIFIER_MODEL` | `gemini-3.1-flash-lite-preview` | Watch/skip classifier |
| `FIRECRAWL_API_KEY` | (unset) | Article + YouTube transcript fallback |
| `FIRECRAWL_BASE_URL` | `https://api.firecrawl.dev` | Self-hosted Firecrawl |
| `READ_PYTHON` | `python3` | Interpreter with `youtube-transcript-api` |

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
title: 'The Respond Gap: Why Autonomous Agents Have No Panic Button'
source: flint.fountain.network
byline: Flint
url: https://flint.fountain.network/blog/2026-02-20-the-respond-gap-why-autonomous-agents-have-no-panic-button/
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

# The Respond Gap: Why Autonomous Agents Have No Panic Button

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
| `~/data/read-cache/yt-<video_id>.watch.md` | Saved watch outcome per video (status, model, reason) + watch report |
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

A YouTube read exits 2 with `NO_TRANSCRIPT` only when there is no transcript **and** no watch; the payload carries `transcript_errors` (what each provider said) and the watch reason. **Don't improvise past it**: no yt-dlp, no description chasing, no search-result summaries passed off as the video. The skill already tried direct captions, Firecrawl, and a watch. If the watch was skipped for lack of a key, say that; if the user explicitly wants it watched, `--watch=force`.

PDFs are not supported.

## Recommended Workflow for the Calling Agent

**One-off reads:**

1. Run the skill at the right depth (default `deep` for one-offs and anything you will summarise; `skim` for batches). For a video, pass `--context` with what the user wants from it.
2. Read the body the skill returns. Check `truncated`, `body_chars_total`, and `cache` in the frontmatter; for YouTube, read `coverage` and describe your access exactly as it says.
3. Analyze — answer the actual question, summarize, pull quotes.
4. Store useful takeaways via your memory tool with proper tags.
5. If the body was truncated, re-run with `--depth=deep` before summarising. A truncated body is not the video.

**Feed reading:**

1. `read sub <url>` once per source the user wants to follow.
2. Periodically (or on demand) `read refresh` to pull new items.
3. For each new item the user cares about, call `read <item-url>` to fetch full content.
4. Synthesize — same as one-off reads.

## Limitations

- Articles are text only. No image or chart analysis.
- Watching is YouTube-only (Gemini reads public YouTube URLs). Private, unlisted-with-restrictions, and age-gated videos can't be watched.
- A watch report is one model's neutral description, not ground truth. It can miss or misread details; the Verification details section exists so you can sanity-check it.
- No paywall bypass.
- No PDF support.
- YouTube auto-captions have errors, especially with technical terms and proper nouns. Non-English videos come back in their own language (`transcript_language`).
- Brand-new YouTube videos (< 24 hours old) often don't have auto-captions yet; the classifier treats no transcript as a reason to watch.
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
- **Fallbacks live in the skill, not the agent.** Direct → Firecrawl → watch, in that order. When the chain is exhausted, stop. No improvised workarounds.
- **Watch only when it adds something.** A cheap classifier gates the expensive model; outcomes are cached so nothing is judged or watched twice.
- **Never overclaim.** The `coverage` line is the contract between what the skill did and what the agent may say it did.
- **The calling agent does the analysis.** The skill's only model calls are the watch classifier and a neutral audiovisual description.
- **Memory is for read history, not synthesis.** The calling agent stores actual takeaways after analyzing.
- **Feed reading composes with one-off reading.** `refresh` returns item URLs; the agent feeds them back into `read <url>` to get full content.
