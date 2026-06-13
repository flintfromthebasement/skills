# Flint Skills

Public skills maintained by Flint.

This repo is a simple home for reusable agent skills that are useful outside any one client or internal project. The goal is to keep each skill practical, inspectable, and easy to copy or install.

## Table of Contents

- [What This Repo Is](#what-this-repo-is)
- [Skills](#skills)
- [Repo Layout](#repo-layout)
- [Using a Skill](#using-a-skill)
- [Contributing](#contributing)

## What This Repo Is

- A public skills repo for Flint-maintained agent workflows
- A place to publish skills that are broadly useful
- Complementary to larger shared/community skill repos, not a replacement for them

## Skills

| Skill | Path | What it does |
| --- | --- | --- |
| `context-window` | [`skills/context-window`](./skills/context-window/) | Generate a single-file HTML report visualizing what's in an LLM session's context window — system prompt, tool schemas, recall, hooks, conversation turns — color-coded by source type with token estimates. Works for the calling agent's own session, for bots whose source you can read, and best-effort for black-box bots. |
| `de-ai-design` | [`skills/de-ai-design`](./skills/de-ai-design/) | Audit an AI-generated web design for the convergent "AI look" (indigo gradients, pill badges, emoji UI, hover-lift cards, scroll reveals — the "Purple Problem") and replace each tell with a deliberate alternative from a chosen design genre. Evidence-based: every tell needs file:line proof in the actual CSS/JS/markup before it gets fixed. Ships a grep-able tells catalog. |
| `lyric-video` | [`skills/lyric-video`](./skills/lyric-video/) | Combine an audio file, a video file, and lyrics into a subtitled music video. Accepts plain-text lyrics (auto-aligned via whisper word timestamps) or pre-timestamped LRC / TSV / JSON. Two-pass build (composite + faststart remux) so a crash in either step doesn't destroy the work. |
| `read` | [`skills/read`](./skills/read/) | Fetch any web URL or YouTube video, cache it, and return content at three depth modes (skim / read / deep). Plus lightweight RSS/Atom feed subscriptions — subscribe, refresh, read by URL. Model-agnostic — the skill never calls an LLM, the calling agent does the synthesis. Caches to `~/data/read-cache/`, subscriptions at `~/data/feeds/`. |
| `safe-gdocs` | [`skills/safe-gdocs`](./skills/safe-gdocs/) | Read-only Google Docs / Drive access for agents. Wraps the official `gws` CLI with a guard that blocks every write method (create, update, delete, send, etc.) and ships a friendly `gdocs read/search/list/info` wrapper. Idempotent first-run installer handles npm install, shim placement, PATH check, and OAuth. |
| `site-archive` | [`skills/site-archive`](./skills/site-archive/) | Archives a site or URL into markdown while respecting `robots.txt`, randomizing delays, supporting incremental crawls, and detecting blocker pages |
| `stock-research` | [`skills/stock-research`](./skills/stock-research/) | End-to-end stock analysis for long-term investors. Live fundamentals/quote/earnings/analyst data via `yfinance` (no API key), public technical-analysis chart URLs from StockCharts + Finviz (no image downloads, no auth), and a four-question quality+valuation framework that lands a buy/watch/avoid verdict. Includes a second "Mainstreet" bottom-up mode (unit economics → discounted fair value → margin-of-safety entry) for monopoly / novel-business-model companies where P/E benchmarks mislead. |
| `vuln-scan` | [`skills/vuln-scan`](./skills/vuln-scan/) | Per-file CTF-style vulnerability scanner: loops source files through `claude -p`, writes `*.vuln.md` sidecars, and runs a skeptical verify pass to weed out false positives. Profiles for WordPress, Node, and Python. |
| `walkie` | [`skills/walkie`](./skills/walkie/) | Connect an AI agent to another agent over a direct P2P channel (walkie-sh / Hyperswarm DHT) — no server, no accounts, just a shared channel name + secret. Covers install (idempotent `setup.sh`), identity, connecting to a peer, the conversation-hygiene rules that keep two agents from blabbering forever (terminal sign-off token, spiral detection, banter caps), human-visibility patterns (`watch`/relay + the web UI), and per-peer security norms. Ships with zero real secrets — you generate your own. |
| `wp-screenshots` | [`skills/wp-screenshots`](./skills/wp-screenshots/) | Capture clean WordPress admin + front-end screenshots from a JSON brief. Headless Chromium, login-aware, hides update bubbles, 2× DPR default, optional Mac-faithful font aliasing, standalone HTML gallery output. |
| `ytpoop` | [`skills/ytpoop`](./skills/ytpoop/) | Generate a short YouTube Poop-style chaotic absurdist video entirely programmatically — PIL frames, NumPy synth audio, ffmpeg assembly. No external assets. Ships with a runnable reference generator and a documented technique catalog for an agent to fork per topic. |

See [CATALOG.md](./CATALOG.md) for the short index.

## Repo Layout

```text
.
├── README.md
├── CATALOG.md
├── CONVENTIONS.md
└── skills/
    └── <skill-name>/
        ├── SKILL.md         # frontmatter + usage docs (required)
        ├── scripts/         # entry points + setup.sh (if any setup is needed)
        ├── examples/        # smoke-test inputs (optional)
        └── README.md        # only if SKILL.md isn't enough (optional)
```

Each skill lives in its own folder under `skills/`. See [CONVENTIONS.md](./CONVENTIONS.md) for the install-receipt pattern and the required `setup.sh` contract for skills that need setup.

## Using a Skill

Most skills are folder-based and use `SKILL.md` as the entry point. If your agent supports local or repo-backed skills, point it at the folder you want.

Example:

```text
skills/site-archive/
```

## Contributing

For now this repo is maintained directly by Flint. Future public skills will be added here when they are stable enough to be useful outside local project work.

New skills follow the conventions in [CONVENTIONS.md](./CONVENTIONS.md): one entry point per skill (`scripts/setup.sh`), idempotent installers with an install receipt, diagnostic output an agent can act on. `safe-gdocs` is the reference implementation.
