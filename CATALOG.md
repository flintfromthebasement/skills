# Catalog

Short index of public skills in this repo.

| Skill | Location | Notes |
| --- | --- | --- |
| `safe-gdocs` | [`skills/safe-gdocs`](./skills/safe-gdocs/) | Read-only Google Docs / Drive access for agents. Wraps `@googleworkspace/cli` with a guard that blocks every write method, plus a friendly `gdocs` wrapper. Idempotent first-run installer. |
| `site-archive` | [`skills/site-archive`](./skills/site-archive/) | Crawl and archive a website into markdown with polite delays, incremental modes, curl fallback, and blocker detection |
| `vuln-scan` | [`skills/vuln-scan`](./skills/vuln-scan/) | CTF-style per-file vulnerability scan via `claude -p`, with a skeptical verify pass to drop false positives. Generic + WordPress / Node / Python profiles. |
