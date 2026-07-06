# WordPress alt-text internals & edge cases

## Where alt text lives
- **Media library alt** = the postmeta row `_wp_attachment_image_alt` on the *attachment* post.
  One row per image. This is the source of truth WordPress uses when it renders an image
  *dynamically*: featured images (`the_post_thumbnail` / `wp_get_attachment_image`), blocks/
  shortcodes that pull from the attachment, and **every future insert** of that image.
- **In-post alt** = the literal `alt="..."` attribute baked into `post_content` HTML at the time
  an image was inserted (Gutenberg image block or classic-editor `<img>`). This is a **static
  copy** — changing the media-library alt does NOT update it.

## The two-phase consequence (important)
- **Phase 1** (set media-library alt) instantly fixes featured + dynamically-rendered images and
  all future inserts. Safe, one reversible meta row each.
- **Phase 2** (rewrite baked-in `alt=""` in `post_content`) is the *only* way to fix images
  already hard-coded into existing posts. Riskier (edits live post HTML) → separate, staged.
- Interim state is expected and fine: after Phase 1, an image used *only* inside old post HTML
  still shows blank alt on that page until Phase 2. Strictly better than before; Phase 2 closes it.

## Embed mechanics (how to map an `<img>` to an attachment)
- Gutenberg image block: comment `{"id":N,...}` + `<img ... class="wp-image-N" ...>`. The alt is
  in the `<img>` tag, not the block JSON.
- Classic editor: `<img class="... wp-image-N ..." ... alt="" width=.. height=..>`.
- The `wp-image-N` class is the attachment ID — the primary key for mapping. Requiring it also
  conveniently excludes example-code `<img>` in tutorial posts.

## Edge cases learned the hard way
- **`-scaled` filenames.** Large uploads are stored as `name-scaled.jpg` in `_wp_attached_file`,
  but rendered sizes are `name-300x200.jpg`. Normalize BOTH by stripping `-\d+x\d+` *and*
  `-scaled` before matching filename → attachment. (The scripts do this.)
- **Stale / wrong `wp-image-N`.** After migrations, an `<img>` may carry a `wp-image-4169` class
  where ID 4169 is no longer an attachment (e.g. a forum reply). The by-ID lookup returns no alt
  → the filename fallback rescues it by matching the real file. Never fabricate.
- **Theme/CTA-rendered images.** Some images on a page come from the theme/widgets/CTA blocks,
  not the post's own `post_content`. They may have media-library alt yet render with hardcoded
  `alt=""` from the template. Neither phase touches these — it's a theme/template fix. Surface it.
- **SVGs.** PIL can't rasterize SVG; install `cairosvg` so the model can actually see logos.
  Browsers render SVG natively, so a review gallery can embed raw SVG even without rasterizing.
- **Foreign keys (rare on core, possible on custom tables).** Not a concern for
  `_wp_attachment_image_alt`. Only relevant if you later touch custom tables — `TRUNCATE`/heavy
  ops can be FK-blocked.
- **Full-page cache.** Varnish / host caches (Pagely, etc.) may serve stale *rendered* HTML after
  a Phase-2 edit even though the DB is correct. Cache-bust verification with `?cb=<timestamp>`.

## wp-cli quick reference
```
wp db prefix                                   # the table prefix (often wp_, but never assume)
wp post meta get <id> _wp_attachment_image_alt
wp eval "echo get_permalink(<id>);"            # canonical URL for verification
wp db export f.sql --tables=$(wp db prefix)postmeta   # targeted backup
```
