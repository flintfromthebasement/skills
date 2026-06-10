# Catalog

Short index of public skills in this repo.

| Skill | Location | Notes |
| --- | --- | --- |
| `context-window` | [`skills/context-window`](./skills/context-window/) | Generate a single-file HTML report visualizing what's in an LLM session's context window — system prompt, tool schemas, recall, hooks, conversation turns — color-coded by source type with token estimates. Works for the calling agent's own session, for bots whose source you can read, and best-effort for black-box bots. |
| `de-ai-design` | [`skills/de-ai-design`](./skills/de-ai-design/) | Audit an AI-generated design for the convergent "AI look" and replace each tell with a deliberate genre-based alternative. Grep-able tells catalog, audit-then-fix workflow, before/after verification. |
| `lyric-video` | [`skills/lyric-video`](./skills/lyric-video/) | Combine an audio file, a video file, and timestamped lyrics (LRC / TSV / JSON) into a subtitled music video. Two-pass build (composite + faststart remux) so a crash in either step doesn't destroy the work. |
| `read` | [`skills/read`](./skills/read/) | Fetch any web URL or YouTube video, cache it, and return content at three depth modes (skim / read / deep). Plus lightweight RSS/Atom feed subscriptions. Model-agnostic — the skill never calls an LLM, the calling agent does the synthesis. |
| `safe-gdocs` | [`skills/safe-gdocs`](./skills/safe-gdocs/) | Read-only Google Docs / Drive access for agents. Wraps `@googleworkspace/cli` with a guard that blocks every write method, plus a friendly `gdocs` wrapper. Idempotent first-run installer. |
| `site-archive` | [`skills/site-archive`](./skills/site-archive/) | Crawl and archive a website into markdown with polite delays, incremental modes, curl fallback, and blocker detection |
| `stock-research` | [`skills/stock-research`](./skills/stock-research/) | Long-term-investor stock analysis: live fundamentals/quote/earnings/analyst data (yfinance, no API key), public technical-analysis chart URLs (StockCharts + Finviz, no downloads), and a four-question quality+valuation framework to a buy/watch/avoid verdict. Second "Mainstreet" mode does bottom-up unit-economics valuation for monopoly / novel-business companies. |
| `vuln-scan` | [`skills/vuln-scan`](./skills/vuln-scan/) | CTF-style per-file vulnerability scan via `claude -p`, with a skeptical verify pass to drop false positives. Generic + WordPress / Node / Python profiles. |
| `wp-screenshots` | [`skills/wp-screenshots`](./skills/wp-screenshots/) | Capture clean WordPress admin + front-end screenshots from a JSON brief. Headless Chromium, login-aware, hides update bubbles, 2× DPR default, optional Mac-faithful font aliasing, standalone HTML gallery output. |
| `ytpoop` | [`skills/ytpoop`](./skills/ytpoop/) | Generate a short YouTube Poop-style chaotic absurdist video entirely programmatically — PIL frames, NumPy synth audio, ffmpeg assembly. No stock footage, no API calls. Ships with a runnable reference generator (`scripts/example.py`) and a documented technique catalog for an agent to fork per topic. |
