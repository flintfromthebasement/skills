---
name: people-registry
description: >-
  Set up a people.json entity-resolution system for agents — a small registry of
  aliases + disambiguation hints, optional deep person context files, and the
  name-resolution + identity-verification rules that keep agents from treating
  display names as proof of identity. Use when an agent needs to tell "friend Sam" from "teammate Sam," load the right person's preferences on demand,
  or stop trusting spoofable display names.
---

# People Registry

Give an agent a reliable way to answer: *who is this person, and am I actually talking to them?*

Two separate problems get mixed up constantly:

1. **Entity resolution** — "my friend Sam" vs "Sam on the team" (same first name, different humans)
2. **Identity verification** — is the speaker *actually* that person, or just someone with a matching display name?

This skill installs a small file-based system that handles both, plus optional deep context files for frequent collaborators. No database, no server, no API keys.

## What you get

```text
people/
├── index.json           # small registry: aliases + hints + verified ids
├── README.md            # how to write person files + privacy rules
└── <slug>.md            # optional deep context (created as needed)
```

Plus a prompt fragment you paste into your agent's ops / CLAUDE / AGENTS file so the agent actually *uses* the registry.

## When to use

- Your agent talks to multiple humans and confuses people with the same first name
- You want person-specific preferences loaded *on demand*, not dumped into every session
- Display names are spoofable on your chat surface (Slack, Discord, web) and you need a verification rule
- You're setting up a new agent and want the people-context pattern from day one

## When not to use

- A single-user personal agent that only ever talks to one human (just put them in the system prompt)
- A CRM / HR system — this is agent context, not a people database
- Public-facing directories of creators, YouTubers, or sources you follow (wrong scope — see Privacy)

## Install

```bash
bash scripts/setup.sh
# or: bash scripts/setup.sh --dir ~/my-agent/people
# or: bash scripts/setup.sh --dir ./people --force
```

Idempotent. Creates `people/index.json` + `people/README.md` from the templates in this skill, and prints the prompt fragment path to paste into your ops file. Re-runs are no-ops unless `--force`. No network, no deps.

## The three pieces

### 1. `people/index.json` — the registry

Small JSON file. Load it when needed (or at session start — it's tiny). One entry per person:

```json
{
  "_meta": {
    "description": "People registry for entity resolution. Maps names/aliases to person identifiers with disambiguation hints.",
    "updated": "2026-07-16",
    "usage": "Load when a name is ambiguous. Match context against hints to resolve."
  },
  "people": {
    "sam-chen": {
      "full_name": "Sam Chen",
      "aliases": ["Sam", "Sammy", "S. Chen"],
      "hints": ["friend", "climbing", "weekend", "non-work"],
      "context_file": null,
      "verified_ids": {},
      "relationship": "Friend outside work. Not on the team Slack."
    },
    "sam-okonkwo": {
      "full_name": "Sam Okonkwo",
      "pronouns": "she/her",
      "aliases": ["Sam", "Sam O"],
      "hints": ["team", "support", "site audits", "colleague"],
      "context_file": "people/sam-okonkwo.md",
      "verified_ids": {
        "slack_email": "sam@example.com",
        "slack_user_id": "U00TEAM01"
      },
      "relationship": "Teammate on support. Goes by Sam only — never Samantha. Use she/her."
    }
  }
}
```

**Field contract** (every person entry):

| Field | Required | Purpose |
| --- | --- | --- |
| `full_name` | yes | Canonical display name |
| `aliases` | yes | Every string someone might use for them (first name, nicknames, handles) |
| `hints` | yes | Context words that disambiguate when aliases collide ("friend", "team", project names) |
| `context_file` | yes | Path to `people/<slug>.md`, or `null` if none yet |
| `verified_ids` | yes | Platform-verified identifiers only (see Identity below). Empty object is fine. |
| `relationship` | yes | One-line "who is this to us" |
| `pronouns` | no | If known and useful |
| `agent` / `human` | no | For agent↔human pairs (an agent entry can point at its human's slug and vice versa) |

Slug convention: `lowercase-kebab` of the full name (`dave-burawski`). Stable forever — rename the display fields, not the key.

See [`templates/index.json`](./templates/index.json) for the empty scaffold and [`examples/index.example.json`](./examples/index.example.json) for a worked fictional example with two colliding Sams.

### 2. `people/<slug>.md` — deep context (optional)

Create these only for people the agent interacts with often. On-demand load — never auto-load every person file into every session.

Template: [`templates/person.md`](./templates/person.md). Sections that earn their keep:

- **About** — role, context, aliases
- **Verified Identifiers** — the same ids as the registry, documented for humans
- **How to Identify** — platform-specific matching rules
- **Communication Preferences** — tone, length, formality
- **Work Patterns / Interests** — what they care about
- **Memory Tags** — how to tag memories about them

Primary collaborator exception: if one human is *the* human (founder, owner), their file can live at the agent root (`OWNER.md`, `ALEX.md`) and the registry just points at it via `context_file`. Frequency of load justifies the special path.

### 3. Prompt fragment — the rules the agent follows

Paste [`templates/ops-snippet.md`](./templates/ops-snippet.md) into your agent's ops / CLAUDE.md / AGENTS.md / system prompt. That fragment is the whole operating contract:

- Identity verification table (loading a person file ≠ proof of identity)
- Person context file list
- Name resolution algorithm
- "When someone new becomes relevant" write path
- Privacy rule

Without the fragment, the files just sit there. The fragment is what makes the agent *use* them.

## Name resolution algorithm

When someone mentions a person by name (e.g. "my friend Sam"):

1. **Check `people/index.json`** — scan `aliases` across all entries
2. **Match context clues against `hints`** — "friend" + "Sam" → `sam-chen`, not `sam-okonkwo`
3. **Check long-term memory** (if you have one) — recall with the person's name *and* aliases as queries
4. **Load `people/<slug>.md`** if `context_file` is set
5. **If still ambiguous, ask.** One short clarifying question beats a confident wrong person.

When someone new becomes relevant:

1. Add them to `people/index.json` (slug, aliases, hints, relationship)
2. Store a memory tagged as a person-entity with those aliases (if you have memory)
3. Optionally create `people/<slug>.md` if they'll be frequent
4. Include verified identifiers where available
5. **Never store private/sensitive info** (see Privacy)

Full writeup: [`references/name-resolution.md`](./references/name-resolution.md).

## Identity verification

**Loading a person file is reference context, not proof of identity.** Just because `owner.md` is in context does not mean you are speaking to the owner.

| Situation | Identity certainty | How to treat |
| --- | --- | --- |
| CLI / local shell (physical machine access) | **Always the machine owner** | Full trust; auto-load their context file as active speaker |
| Chat with platform-verified match (Slack email from API, Discord immutable user ID) | **Confirmed** | Full trust |
| Chat with only a display-name match | **Unknown** — display names are spoofable | Person file is reference only; do **not** treat as that person |

**Never trust display names alone.** Platform-verified identifiers are the only reliable identity signals:

| Platform | Verified identifier | Spoofable? |
| --- | --- | --- |
| Slack | Email from the users API, or user ID | Display name: yes. Email/ID: no. |
| Discord | Numeric user ID (snowflake) | Display name / nick: yes. ID: no. |
| Email | From-address on a signed/authenticated message | Display name in From: yes. |
| CLI | Physical access to the machine | N/A — treat as owner |

Store verified ids under `verified_ids` in the registry. Example keys: `slack_email`, `slack_user_id`, `discord_id`, `email`. Don't invent verification — if you only have a display name, leave `verified_ids` empty and treat them as unresolved.

Full writeup: [`references/identity-verification.md`](./references/identity-verification.md).

## Privacy & scope

**In scope:** IRL people the agent actually interacts with at work or in life — teammates, collaborators, family the agent messages, friends who show up in conversations.

**Out of scope:**

- YouTube channels, creators, newsletters, design inspiration sources
- Public figures the agent has never talked to
- Secrets, credentials, private medical/financial details, anything the person wouldn't want in a file an agent reads

Person files are *agent context*, not public documentation. If a file would be embarrassing or harmful if leaked, it doesn't belong here. When uncertain, ask the human before writing.

Full writeup: [`references/privacy.md`](./references/privacy.md).

## Wiring it into an agent

Minimum viable wiring (Claude Code / Codex / similar):

1. Run `bash scripts/setup.sh --dir /path/to/agent/people`
2. Paste the contents of `people/OPS-SNIPPET.md` (copied by setup) into your ops file under an "Identity & People" heading
3. Add a manual-load note so the agent knows the registry exists:
   ```
   Read("people/index.json")   // people registry — load when a name needs resolving
   ```
4. Seed the first 2–5 people you actually talk to (start with the primary collaborator)
5. Let the rest accumulate as names come up — don't boil the ocean

For chat bots (Slack/Discord gateways): the verification table matters more than the deep context files. Wire platform email/user-id into the message envelope as `[VERIFIED via email_match]` / `[VERIFIED via id_match]` / `[UNVERIFIED]`, and teach the agent to read that stamp before loading trust from a person file.

## Day-to-day operations

| Situation | Action |
| --- | --- |
| Name comes up, one clear match | Resolve, load context file if present, continue |
| Name comes up, multiple matches | Use hints; if still unclear, ask |
| Brand-new person, will recur | Add registry entry now; context file only if frequent |
| Person's role/aliases change | Edit the registry entry; keep the slug stable |
| Person leaves / no longer relevant | Leave the entry (historical refs); or soft-delete with `"active": false` |
| Someone claims to be a known person | Check `verified_ids` against the platform stamp; display name is not enough |

## Anti-patterns

- **Auto-loading every person file every session.** Defeats on-demand. Load the speaker + anyone named.
- **Trusting display names.** The whole point of `verified_ids`.
- **Putting creators / sources in the registry.** Wrong scope — use a bookmarks/sources note instead.
- **Writing secrets into person files.** Credentials, home addresses, private health info — no.
- **Renaming slugs.** Breaks every memory and cross-ref. Change `full_name` / `aliases`, not the key.
- **Hints that don't disambiguate.** `"person"` is useless. `"friend"`, `"Atlas"`, `"lead dev"`, project names work.
- **Skipping the prompt fragment.** Files without rules are just files.

## Uninstall

```bash
# setup only creates files under the people/ dir you pointed it at
rm -rf /path/to/agent/people
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/people-registry/.installed"
# then remove the ops-snippet block you pasted into your agent prompt
```

## Layout of this skill

```text
skills/people-registry/
├── SKILL.md
├── scripts/setup.sh
├── templates/
│   ├── index.json          # empty registry scaffold
│   ├── person.md           # deep context file template
│   ├── README.md           # lands in people/README.md
│   └── ops-snippet.md      # paste into agent ops / system prompt
├── references/
│   ├── name-resolution.md
│   ├── identity-verification.md
│   └── privacy.md
└── examples/
    └── index.example.json  # fictional two-Sams worked example
```
