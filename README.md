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
| `site-archive` | [`skills/site-archive`](./skills/site-archive/) | Archives a site or URL into markdown while respecting `robots.txt`, randomizing delays, supporting incremental crawls, and detecting blocker pages |

See [CATALOG.md](./CATALOG.md) for the short index.

## Repo Layout

```text
.
├── README.md
├── CATALOG.md
└── skills/
    └── site-archive/
        ├── SKILL.md
        ├── package.json
        ├── package-lock.json
        └── scripts/
```

## Using a Skill

Most skills are folder-based and use `SKILL.md` as the entry point. If your agent supports local or repo-backed skills, point it at the folder you want.

Example:

```text
skills/site-archive/
```

## Contributing

For now this repo is maintained directly by Flint. Future public skills will be added here when they are stable enough to be useful outside local project work.
