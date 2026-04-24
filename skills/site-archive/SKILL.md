---
name: site-archive
description: Archive a site or URL into markdown under /home/flint/data/site-archives/<domain>/ using a polite, sitemap-first crawler with robots.txt handling, randomized delays, incremental modes, curl fallback, and blocker detection for challenge pages like “Are you human?”.
---

# Site Archive

Use this skill when the user wants a site, section, docs set, or blog archived into markdown for later search, analysis, or migration work.

Default storage:

- `/home/flint/data/site-archives/<domain>/content/pages/`
- `/home/flint/data/site-archives/<domain>/manifest.json`
- `/home/flint/data/site-archives/<domain>/summary.md`
- `/home/flint/data/site-archives/<domain>/state/blocklist.json`

Prefer the bundled crawler instead of writing one-off scraping code.

## Default workflow

1. Point the crawler at a URL or domain.
2. Let it check `robots.txt`, prefer sitemap discovery, and fall back to bounded same-origin link discovery if needed.
3. Use incremental flags to avoid unnecessary re-fetching.
4. Review `summary.md` and `manifest.json` for archived, blocked, skipped, and failed pages.

## Core commands

Archive a site:

```bash
node /home/flint/skills/site-archive/scripts/crawl.mjs --site https://example.com
```

Only crawl blog posts:

```bash
node /home/flint/skills/site-archive/scripts/crawl.mjs --site https://example.com --only-posts
```

Skip already archived pages:

```bash
node /home/flint/skills/site-archive/scripts/crawl.mjs --site https://example.com --skip-existing
```

Only revisit pages whose sitemap `lastmod` changed:

```bash
node /home/flint/skills/site-archive/scripts/crawl.mjs --site https://example.com --since-lastmod
```

## Important flags

- `--fetch-engine auto|node|curl`
- `--include-pagination`
- `--include-search`
- `--include-pattern <regex>`
- `--exclude-pattern <regex>`
- `--link-depth <n>`
- `--max-pages-from-links <n>`
- `--min-delay-ms <n>`
- `--max-delay-ms <n>`
- `--retry-blocked`
- `--dry-run`

## Guardrails

- Respect `robots.txt`. The crawler checks disallow rules and uses `crawl-delay` when present.
- Default to `fetch-engine auto`. It uses explicit browser-like headers and can fall back to `curl` when the lightweight fetch path gets challenge-style responses.
- Pagination index pages like `/page/2/` and search result pages are excluded by default. Archive/category/tag/topic pages stay allowed unless explicitly excluded.
- Do not treat blocker pages as valid content. The crawler records them separately and writes diagnostics instead of archiving their HTML as markdown.
- If the same blocker fingerprint repeats across several pages in one run, the crawl aborts early to avoid hammering the site.
- Keep requests single-threaded and randomized unless there is a strong reason to change that behavior.
