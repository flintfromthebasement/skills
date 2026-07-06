---
name: wordpress-alt-text
description: Generate and apply accessible, screen-reader-first alt text to images on any WordPress site that is missing it. SQLite-backed pipeline — inventory (WP-CLI manifest or direct read-only MySQL), AI-vision generation (any OpenAI-compatible endpoint, or an API-free agent-vision fallback), a self-contained human-review HTML artifact, safe idempotent write-back to the media library, and optional in-post alt backfill. Use when a WP site has images without alt text, or when the user mentions alt text, alt tags, image accessibility, WCAG image descriptions, or media-library/image SEO.
---

# WordPress Alt Text

Add accurate, screen-reader-first `alt` text to a WordPress site's images. Two independent
write phases, run in order:

- **Phase 1 — Media Library** (safe, do this first): set each attachment's
  `_wp_attachment_image_alt`. Fixes featured images, dynamically-rendered images, and every
  *future* insert. One reversible meta row per image.
- **Phase 2 — In-post backfill** (optional, riskier): fill empty/missing `alt` already baked
  into existing post HTML. Surgical, per-`<img>`-tag, only after Phase 1.

Everything upstream of the writes flows through one local **SQLite DB** (`alt.db`) — the
inventory, generated alts, error flags, costs, and applied-status all live there, so every
stage is resumable, queryable, and auditable. The site itself is only touched read-only
until Phase 1's staged write-back.

## Core principles (non-negotiable)

1. **Accuracy first.** Describe only what is visibly in the image. Never invent brand names,
   people, or screen text. On a fetch/render failure: emit empty + flag for human review,
   never guess.
2. **Idempotent.** Only ever write where alt is currently empty. Never overwrite curated alt.
3. **Back up before any write.** `wp db export` the tables you touch (`*_postmeta` for
   Phase 1; `*_posts` for Phase 2). Keep per-post originals in Phase 2.
4. **Staged rollout.** 1 image/post → verify → 5 → verify → full run, throttled with jitter
   (`DELAY_MIN_MS`/`DELAY_MAX_MS`) so a live site never notices.
5. **Human review before live writes.** Ship the review artifact (Step 4) and get an explicit
   go-ahead before Phase 1 runs against production.

## Prerequisites

- WP-CLI on the target site (local or over SSH), or a read-only MySQL user for direct
  inventory. Confirm **production vs staging** before any write, out loud.
- Python 3.9+ — run `bash scripts/setup.sh` once (creates `.venv` with `requests`, `Pillow`,
  `pymysql`; add `cairosvg` only for SVG-heavy sites).
- A vision API key (`OPENROUTER_API_KEY` or `AI_API_KEY`) — or use the API-free fallback.

## Workflow

### Step 0 — Scope & safety

- Identify the target (prod/staging) and baseline it: homepage returns 200.
- **Hunt for access-protected upload directories** before generating anything. Some sites
  keep private files in the media library (support-ticket attachments, member-only
  downloads) that 403 anonymous fetches *by design*. Spot-check a few upload URLs; anything
  protected goes into `--exclude-pattern` at inventory time so it never enters the pipeline.
  A burst of 403s from one directory during generation is this, not rate limiting.

### Step 1 — Inventory (read-only) → `alt.db`

Pick the mode that matches your access:

**A) WP-CLI manifest mode** (no DB creds needed):
```bash
wp eval-file inventory.php > manifest.json          # on the site (POST_TYPES env to widen)
python3 inventory.py --db alt.db --from-manifest manifest.json
```

**B) Direct MySQL mode** (read-only user; also populates the per-`<img>`-tag `post_images`
table used to scope Phase 2):
```bash
WP_DB_HOST=... WP_DB_USER=... WP_DB_PASS=... WP_DB_NAME=... WP_DB_PREFIX=wp_ \
python3 inventory.py --db alt.db \
  --base-url https://example.com/wp-content/uploads \
  --post-types post,page,docs \
  --exclude-pattern 'uploads/private-dir/'
```

Include the site's content CPTs in `--post-types`/`POST_TYPES` — the default `post,page`
misses docs/kb/lesson content on most real sites. Each missing-alt image is tiered:
`P1_content` (used in published content), `P2_featured` (featured-only), `P3_orphan` (unused).

### Step 2 — Generate (no site writes)

```bash
python3 generate.py --db alt.db --tiers P1_content --limit 10    # sample; eyeball output
python3 generate.py --db alt.db --tiers P1_content,P2_featured,P3_orphan
```

Resumable (only processes rows without a `proposed_alt`), threaded, skips
`excluded_private`. Default model: OpenRouter `google/gemini-3.1-flash-lite`
(~$0.0004/image — a 3,000-image site costs about a dollar). Any OpenAI-compatible vision
endpoint works via `--api-url`/`--model`. Failures store an empty alt + `needs_visual_review=1`.

**No API key → agent-vision fallback.** Don't run generate.py. Instead:
```bash
python3 fetch_images.py --db alt.db --tiers P1_content --limit 50   # downloads + downscales
```
Then the host agent (e.g. Claude Code) reads each `alt-images/<id>.jpg` with its own vision,
applies the prompt contract in `references/prompt-and-seo.md`, and writes each alt back:
```bash
sqlite3 alt.db "UPDATE images SET proposed_alt='...', status='generated' WHERE id=<id>"
```
Fan out with subagents for batches. Best for small sites / zero budget. Details:
`references/models-and-fallbacks.md`.

### Step 3 — Review (no site writes)

```bash
python3 build_review.py --db alt.db --out review.html --site example.com
```

Self-contained HTML (thumbnails embedded): sampled cards per tier, every flagged row, and
the Phase-2 in-post table. Send it to the site owner; **wait for the go-ahead**.

### Step 4 — Phase 1 write-back (media library)

```bash
# on the site, from WP root — BACK UP FIRST, outside the docroot:
wp db export /root/alt-backups/postmeta-$(date +%Y%m%d-%H%M%S).sql --tables=$(wp db prefix)postmeta

# locally: export approved alts
python3 export_updates.py --db alt.db --out alt_updates.json

# on the site: dry run, then staged live
ALT_JSON=alt_updates.json DRY_RUN=1 wp eval-file apply_alt.php
ALT_JSON=alt_updates.json IDS=<one-id> wp eval-file apply_alt.php
# verify: wp post meta get <id> _wp_attachment_image_alt
ALT_JSON=alt_updates.json IDS=<five-ids> DELAY_MIN_MS=500 DELAY_MAX_MS=1500 wp eval-file apply_alt.php
# verify all five, then the full run (detach it — nohup/tmux — a throttled run takes ~1s/image):
nohup env ALT_JSON=alt_updates.json DELAY_MIN_MS=500 DELAY_MAX_MS=1500 \
  wp eval-file apply_alt.php > apply.out 2>&1 &

# locally, after the run:
python3 export_updates.py --db alt.db --mark-applied alt_updates.json
```

`apply_alt.php` writes `_wp_attachment_image_alt` **only where currently empty**, verifies
each write by reading it back, logs everything, and prints a `RESULT` summary line
(`updated= skip_has= missing= fail=`). Spot-check the site (front-end 200s, normal load)
mid-run.

### Step 5 — Phase 2 in-post backfill (optional)

Only after Phase 1. Back up `*_posts` first. `inpost_alt.php` rewrites **only** the alt
attribute of `<img>` tags (per-tag callback, never a blind regex), matching by `wp-image-N`
then filename (ambiguous filename collisions are skipped, never guessed), pulling the value
from the attachment's media alt. Writes verbatim via `$wpdb->update` (no kses) and saves
each post's original HTML.

```bash
DRY_RUN=1 wp eval-file inpost_alt.php               # scope + exact before/after diffs
IDS=<one-post> wp eval-file inpost_alt.php          # then 5, then full — throttled
```

Verify per stage: only-alt-changed (blank out alt values in both versions → byte-identical)
and page returns 200 with a cache-buster (`?cb=<ts>` — full-page caches serve stale HTML).

## Verification (every stage)

- Read the alt back from the DB; confirm it matches.
- Image URL still returns 200.
- Site health during long runs: homepage + a content page return 200 in normal time.

## Field notes (from a 7,700-image production run)

- **Private upload dirs are the #1 pipeline trap.** 681 access-protected attachments looked
  like rate-limiting until traced; exclude them at inventory time (Step 0).
- 10 fetch workers against a CDN-fronted production site caused zero throttling; the write
  phase at ~1 write/sec with jitter was invisible in monitoring.
- Expect a handful of hard failures per few thousand images (corrupt files, 404s). The
  empty+flagged contract handles them; don't chase 100%.
- A few attachments will vanish between inventory and apply (deleted media). `apply_alt.php`
  reports them as `missing` — normal, not an error.
- If SSH to the site is wrapper-restricted (no scp), transfer `alt_updates.json` by
  base64-chunking it through the command channel and verify with `md5sum` both ends.

## Stop / ask-the-human rules

- Hard fail (404 image, unrasterizable SVG): emit empty, flag, never guess.
- If anything looks broken (a post, an image, the site), diagnose and propose — do **not**
  restore a backup or apply a fix without confirming with the operator.
- Ambiguous filename matches, theme-hardcoded alt, foreign-key-locked tables: surface them,
  don't force.

## Files

- `scripts/inventory.php` — WP-side read-only inventory → manifest JSON (`wp eval-file`)
- `scripts/inventory.py` — manifest **or** direct-MySQL → `alt.db`
- `scripts/generate.py` — vision-API generation into `alt.db` (resumable, threaded)
- `scripts/fetch_images.py` — API-free fallback: download+downscale for agent vision
- `scripts/build_review.py` + `review_template.html` — human-review HTML artifact
- `scripts/export_updates.py` — `alt.db` → `alt_updates.json`; `--mark-applied` after
- `scripts/apply_alt.php` — Phase 1 media-library write-back (`wp eval-file`)
- `scripts/inpost_alt.php` — Phase 2 in-post backfill (`wp eval-file`)
- `references/wordpress-alt-internals.md` — where alt lives, why Phase 1 ≠ Phase 2, edge cases
- `references/models-and-fallbacks.md` — model setup, cost, the API-free fallback in detail
- `references/prompt-and-seo.md` — the exact prompt contract + keyword rules
- `references/safety-and-rollout.md` — backups, idempotency, staged rollout, rollback
