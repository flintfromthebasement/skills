This is a fork of the upstream WordPress.org plugin. Port every upstream change unless it falls under **Drop**.

### Keep

- Bug fixes, security hardening, performance, accessibility, and translation changes.
- Features that run entirely on the site without a third-party account or service.

### Drop

- Promotions for other plugins or services: welcome panels, suggestion cards, install buttons, upsells, review nags, newsletter forms.
- Telemetry, usage tracking, remote announcement feeds, and anything that phones home.
- Remote assets (scripts, styles, images, fonts loaded from third-party hosts).

Remove the wiring of dropped features too (requires, hooks, menu entries, CSS, JS, uninstall cleanup). Prefer deleting over stubbing.

### Fork identity

Keep this fork's plugin header (name, author, plugin URI, update URI) and any files the fork added. If upstream renamed or moved files, follow the rename.

### Version and changelog

Set the plugin header version, any version constant, and the readme stable tag to the upstream version. Add a short changelog entry for the fork that says what was ported and what was dropped.

### Verification

`php -l` every changed PHP file and grep the tree for markers of the dropped features before finishing.
