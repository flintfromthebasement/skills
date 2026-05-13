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
| `safe-gdocs` | [`skills/safe-gdocs`](./skills/safe-gdocs/) | Read-only Google Docs / Drive access for agents. Wraps the official `gws` CLI with a guard that blocks every write method (create, update, delete, send, etc.) and ships a friendly `gdocs read/search/list/info` wrapper. Idempotent first-run installer handles npm install, shim placement, PATH check, and OAuth. |
| `site-archive` | [`skills/site-archive`](./skills/site-archive/) | Archives a site or URL into markdown while respecting `robots.txt`, randomizing delays, supporting incremental crawls, and detecting blocker pages |
| `vuln-scan` | [`skills/vuln-scan`](./skills/vuln-scan/) | Per-file CTF-style vulnerability scanner: loops source files through `claude -p`, writes `*.vuln.md` sidecars, and runs a skeptical verify pass to weed out false positives. Profiles for WordPress, Node, and Python. |
| `wp-screenshots` | [`skills/wp-screenshots`](./skills/wp-screenshots/) | Capture clean WordPress admin + front-end screenshots from a JSON brief. Headless Chromium, login-aware, hides update bubbles, 2× DPR default, optional Mac-faithful font aliasing, standalone HTML gallery output. |

See [CATALOG.md](./CATALOG.md) for the short index.

## Repo Layout

```text
.
├── README.md
├── CATALOG.md
├── CONVENTIONS.md
└── skills/
    ├── safe-gdocs/
    │   ├── SKILL.md
    │   └── scripts/
    │       ├── setup.sh
    │       ├── gws-guard.sh
    │       └── gdocs.sh
    ├── site-archive/
    │   ├── SKILL.md
    │   ├── package.json
    │   ├── package-lock.json
    │   └── scripts/
    │       ├── setup.sh
    │       ├── crawl.mjs
    │       └── detect-blockers.mjs
    └── vuln-scan/
        ├── SKILL.md
        └── scripts/
            ├── scan.sh
            └── verify.sh
```

## Using a Skill

Most skills are folder-based and use `SKILL.md` as the entry point. If your agent supports local or repo-backed skills, point it at the folder you want.

Example:

```text
skills/site-archive/
```

## Contributing

For now this repo is maintained directly by Flint. Future public skills will be added here when they are stable enough to be useful outside local project work.

New skills follow the conventions in [CONVENTIONS.md](./CONVENTIONS.md): one entry point per skill (`scripts/setup.sh`), idempotent installers with an install receipt, diagnostic output an agent can act on. `safe-gdocs` is the reference implementation.
