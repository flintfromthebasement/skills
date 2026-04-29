# Skill Conventions

How skills in this repo are structured. Aimed at humans writing skills and at agents installing them.

## TL;DR

Every skill that needs setup ships an idempotent `scripts/setup.sh` that records its work in an **install receipt** file. Re-runs are no-ops unless `--force`.

## Why

Skills in this repo are meant to be installed by both humans and agents. Agents lose state between sessions, so the install path needs to be:

1. **Self-describing** — one entry point per skill: `bash scripts/setup.sh`. No language-roulette ("is it npm? pip? cargo? bare README?").
2. **Idempotent** — safe to re-run any number of times. The skill checks for prior state instead of re-doing work.
3. **Diagnosable** — when something is wrong (PATH not shadowing, missing dep, no auth), the script prints the fix line to stdout. That output is signal an agent can act on.

A `package.json` solves the dependency-install problem and nothing else. The hard parts of skill setup — symlinks, PATH ordering, OAuth, system binaries, config dirs — are exactly the parts package managers don't help with.

## Layout

```
skills/<skill-name>/
├── SKILL.md            # frontmatter (name, description) + usage docs
├── scripts/
│   └── setup.sh        # idempotent installer (if any setup is needed)
└── README.md           # optional, only if SKILL.md isn't enough
```

The bare-minimum runnable skill is just `SKILL.md` + a script. Add `setup.sh` only when there's real setup work (deps to install, symlinks to place, auth to run).

## SKILL.md frontmatter

```yaml
---
name: <skill-name>
description: <one-sentence what it does + when to use it>
---
```

The `description` is what gets surfaced in skill-discovery tooling. Make it specific. "Read-only Google Docs access" beats "tool for working with Google Docs."

## The install receipt

Skills that have a `setup.sh` write a small receipt to:

```
${XDG_CONFIG_HOME:-$HOME/.config}/<skill-name>/.installed
```

The receipt's *existence* is the signal "setup ran successfully." Its contents are diagnostic: install timestamp, paths the script touched, version of any tooling installed. Re-runs read the receipt and exit early.

This is the same pattern cloud-init calls "semaphore files" and Ansible's `creates:` idiom relies on — sometimes called a "sentinel file" in container-bootstrap circles. We use **install receipt** because it's clearer about what the file means.

### Required setup.sh contract

Every `setup.sh` must:

1. **Skip if installed.** First check is `[[ -f "$RECEIPT" && $FORCE -eq 0 ]]` — exit 0 and log "already installed."
2. **Be idempotent.** Every step must check current state before acting. Don't `ln -s` blindly — verify the link points where you expect first.
3. **Support `--force`.** Reinstall even if the receipt exists.
4. **Support `--yes` / `-y`.** Accept defaults non-interactively. OAuth flows that genuinely need a browser can still block, but warn loudly and offer to skip.
5. **Diagnose, don't fail silently.** When a precondition isn't met (PATH ordering wrong, missing system dep), print the exact fix the user needs to apply.
6. **Write the receipt last.** Only after all steps succeeded. A partial install should leave no receipt so the next run picks up where it left off.

### Recommended structure

```bash
#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/<skill-name>"
RECEIPT="$CONFIG_DIR/.installed"

ASSUME_YES=0; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --force) FORCE=1 ;;
    --help|-h) sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  esac
done

log()  { printf '[<skill-name>] %s\n' "$*"; }
warn() { printf '[<skill-name>] WARN: %s\n' "$*" >&2; }
die()  { printf '[<skill-name>] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ -f "$RECEIPT" && $FORCE -eq 0 ]]; then
  log "already installed — receipt at $RECEIPT"
  log "re-run with --force to reinstall"
  exit 0
fi

# ... idempotent setup steps ...

mkdir -p "$CONFIG_DIR"
{
  printf 'installed_at=%s\n' "$(date -Iseconds)"
  printf 'skill_dir=%s\n' "$SKILL_DIR"
  # whatever else future-you / future-agent needs to know
} > "$RECEIPT"

log "done."
```

`safe-gdocs/scripts/setup.sh` is the reference implementation. Copy from there.

## Idempotent symlink installation

If the skill installs binaries into a bin dir, replace existing links only when they point somewhere else, and warn when overwriting:

```bash
install_link() {
  local target="$1" linkpath="$2" name="$3"
  chmod +x "$target"
  if [[ -L "$linkpath" || -e "$linkpath" ]]; then
    local current
    current=$(readlink -f "$linkpath" 2>/dev/null || echo "")
    if [[ "$current" == "$(readlink -f "$target")" ]]; then
      log "$name already linked"
      return
    fi
    warn "$linkpath exists and points to $current — replacing"
    rm -f "$linkpath"
  fi
  ln -s "$target" "$linkpath"
  log "linked $name: $linkpath -> $target"
}
```

## PATH-shadowing skills

If the skill's job is to shadow an existing binary (like `safe-gdocs` shadowing `gws`), the setup script must:

1. Detect where the real binary lives (e.g. `npm config get prefix`).
2. Place the shim somewhere the user controls (`~/.local/bin` by default).
3. **Verify** the shim wins on PATH by running `command -v <name>` and checking the resolved path.
4. If it doesn't win, print the exact PATH export line the user needs to add to their shell rc.

The shim itself must be able to find the real binary regardless of how the user's PATH is configured — env var override, PATH walk skipping itself, fallback to a known install location. See `safe-gdocs/scripts/gws-guard.sh:resolve_real_gws()` for the reference implementation.

## When `setup.sh` isn't needed

Pure script skills with no deps and no system state don't need an installer. `vuln-scan` is an example — it's just shell scripts that shell out to `claude -p`. The "install" is "clone the repo." Don't write a setup.sh for the sake of having one.

The rule: if there's any state outside the skill folder that needs to exist before the skill can run (installed packages, symlinks in PATH, OAuth tokens, config dirs), write a `setup.sh`. Otherwise skip it.

## Uninstall

Skills should document an uninstall path in `SKILL.md`. There's no convention for an `uninstall.sh` yet — the install receipt should record paths touched, so a hand-written `rm` line in the docs is enough. Revisit if skills start touching enough places that an uninstaller is worth maintaining.
