---
name: safe-gdocs
description: Read-only Google Docs / Drive access for an agent. Wraps the official Google Workspace CLI (`gws`) with a guard that blocks every write method (create, update, delete, send, modify, etc.) and ships a friendly `gdocs` wrapper for read/search/list/info on Docs. Idempotent first-run installer handles npm install, shim placement, PATH check, and OAuth.
---

# safe-gdocs

A read-only Google Docs / Drive surface for agents. Solves two problems:

1. **You want an agent to read Google Docs**, but `WebFetch` hits the auth wall.
2. **You don't want it writing anything** — no accidental edits, deletes, sends, or shares.

The skill installs the official Google Workspace CLI (`@googleworkspace/cli`) and shadows the `gws` binary with a guard script that blocks any write method at the CLI layer. Reads pass straight through. A small `gdocs` wrapper covers the common Docs operations with friendly URL handling.

## When to use

- An agent (or a human in agent-adjacent tooling) needs to read Google Docs content programmatically.
- You want a hard, scriptable read-only boundary — not just a policy or prompt rule.
- You're fine with per-user OAuth (the agent inherits the authenticating user's permissions).

## Setup

```bash
bash skills/safe-gdocs/scripts/setup.sh
```

The installer is idempotent. It:

1. Verifies `node` + `npm`.
2. Installs `@googleworkspace/cli` globally if missing.
3. Symlinks `gws` (the guard) and `gdocs` into `~/.local/bin` (or whatever you choose).
4. Verifies `~/.local/bin` is on `PATH` ahead of the npm global bin so the shim shadows the real binary. Prints the fix line if not.
5. Runs `gws auth login` if you haven't authenticated yet (browser OAuth flow).
6. Writes an install receipt at `~/.config/safe-gdocs/.installed`. Re-runs are no-ops unless you pass `--force`. (See [CONVENTIONS.md](../../CONVENTIONS.md) for the repo-wide install pattern.)

Flags:

- `--yes` — accept defaults, no prompts (still runs the OAuth flow if needed).
- `--force` — reinstall even if the sentinel exists.

## Usage

After setup, both binaries are on PATH:

```bash
gdocs read "https://docs.google.com/document/d/<id>/edit"
gdocs read <id> --md            # markdown export
gdocs search "site audit"
gdocs list --limit 5
gdocs info <id-or-url>
```

The underlying `gws` is also available with the guard in front of it, so an agent that already knows the Google Workspace CLI can use it directly:

```bash
gws drive files list --params '{"pageSize": 5}'
gws drive files create ...      # blocked by the guard
```

## What's blocked

Any arg matching this regex is rejected with a clear error before reaching the real binary:

```
create | copy | delete | update | batchUpdate | send | modify
modifyLabels | emptyTrash | trash | untrash | patch | insert | remove
```

The guard always lets `auth`, `schema`, `help`, and `--help` through.

## What's NOT solved

- **Permission scoping by user.** OAuth runs as a single identity. If your agent serves multiple users with different document access, you'll want a per-user OAuth flow on top of this — the guard only enforces read-only, not who-can-read-what.
- **Server-side write protection.** This is a CLI-layer guard. A determined process could call the real binary directly (`$(npm config get prefix)/bin/gws ...`). Treat it as a strong nudge, not a security boundary.
- **Rate limiting.** Google's API quotas still apply. Burst with care.

## Files

```
safe-gdocs/
├── SKILL.md
└── scripts/
    ├── setup.sh        # idempotent installer
    ├── gws-guard.sh    # read-only shim that shadows `gws`
    └── gdocs.sh        # friendly Docs wrapper
```

## Uninstall

```bash
rm ~/.local/bin/gws ~/.local/bin/gdocs
rm -rf ~/.config/safe-gdocs
npm uninstall -g @googleworkspace/cli   # optional
```

## Customizing what's blocked

Edit the `BLOCKED` regex in `scripts/gws-guard.sh`. The guard treats it as a word-boundary match against any arg, so the entries are method names from the Google Workspace CLI surface (Drive, Docs, Calendar, Gmail, etc.) — not a flag list.

If you want to allow a specific write (say, `gws drive files copy` for a backup task) the cleanest path is a sibling skill that shells out to the real binary at `$(npm config get prefix)/bin/gws` directly, with its own narrower guard.
