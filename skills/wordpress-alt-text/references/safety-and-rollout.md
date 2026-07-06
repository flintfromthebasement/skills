# Safety, backups & staged rollout

This skill writes to a live WordPress DB. Treat it like production unless proven otherwise.

## Before any write
1. **Confirm target.** Is this production or staging? State it explicitly. (On some hosts the
   SSH alias says "dev" but the site dir is the live domain — check `wp option get home`.)
2. **Baseline.** Site homepage returns 200.
3. **Back up the tables you'll touch.** Phase 1 touches `<prefix>postmeta`; Phase 2 touches
   `<prefix>posts`:
   ```bash
   wp db export backup-postmeta-$(date +%Y%m%d-%H%M).sql --tables=$(wp db prefix)postmeta
   wp db export backup-posts-$(date +%Y%m%d-%H%M).sql    --tables=$(wp db prefix)posts   # Phase 2
   ```
   If `--single-transaction` errors with a privilege error (common on managed/Aurora DBs lacking
   RELOAD/FLUSH_TABLES), use `--skip-lock-tables` instead — non-locking, fine for a backup.
   Gzip large dumps. Keep them OFF version control (they can contain PII).
4. Phase 2 also auto-saves each modified post's original HTML to `alt-post-originals/` for
   surgical single-post rollback.

## Idempotency (built into the writers)
- Both writers only act where alt is currently **empty**, re-checked at write time — they never
  overwrite curated alt and are safe to re-run. The 12 images from staged tests just show as
  `skip_has` on the full run.

## Staged rollout — always 1 → 5 → full
- **1:** write a single id/post. Verify completely (below). This is the first production touch —
  get an explicit go.
- **5:** a mix (tiers / post types / single vs multi-image / classic vs Gutenberg). Verify each.
- **Full:** run the rest. Jitter with `DELAY_MIN_MS`/`DELAY_MAX_MS` (e.g. 200–700ms) to be gentle.
  Note: `wp eval-file` writes go straight to the DB (no HTTP), so jitter is courtesy, not load
  protection — the real external load is the verification curls, so sample those.

## Verification (every stage)
- **Phase 1:** read the alt back from the DB (matches?), image URL still 200.
- **Phase 2:** prove **only alt changed** — pull the post's original and current content, blank
  all `alt="..."`/`alt='...'` values in both, assert the two are byte-identical. Then the page
  returns 200 (cache-bust `?cb=<ts>`; full-page caches may show stale rendered HTML briefly even
  though the DB is right). Watch for the `wp post get` trailing-newline artifact when diffing —
  strip exactly one trailing `\n` from its output, not all.

## If something looks wrong
Diagnose to the exact byte/line and form a fix — but do **NOT** restore a backup or apply the fix
without confirming with the operator first. A flagged anomaly you understand beats a hasty revert.
Most "scares" in practice are verification-harness artifacts (trailing newline, stale stats,
cache lag), not real corruption — confirm which before acting.

## Scope choices to surface up front
- **Missing-only** (default) vs **all images** (re-alt curated ones too — more review, risk of
  regressing good alt). Recommend missing-only first.
- **Orphans (P3):** images on no live page. Include for library completeness, but process
  **after** P1 (used-in-content) and P2 (featured) so the highest-value images land + get
  reviewed first.
- **Genuinely unfillable** (404 image, ambiguous filename, theme-hardcoded alt): leave flagged,
  don't force.

## Rollback
- Phase 1: the writer logs every `OK <id>` it changed — those ids were empty before, so rollback
  = delete `_wp_attachment_image_alt` for exactly those ids (or restore the postmeta dump).
- Phase 2: restore an individual post from `alt-post-originals/post-<id>.orig.html`, or the
  `posts` dump for a full revert.
