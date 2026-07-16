# People Context Files

Person-specific context for frequent collaborators. Similar to how `AGENTS.md` helps repos communicate their patterns, these files help an agent understand individual communication preferences, interests, and work patterns.

## Purpose

- **Better personalization** — tailor responses to individual communication styles
- **Context continuity** — remember preferences across sessions
- **On-demand loading** — load only when that person is actually in the conversation
- **Name disambiguation** — handle multiple people with the same name via `index.json`

## When to Create a Person File

Create a new person file when someone:

- Interacts frequently with the agent (weekly or more)
- Has specific preferences or communication style
- Works on multiple projects the agent supports
- Is mentioned often in conversations or context

## File Structure

Use `_TEMPLATE.person.md` (copied by setup) or the template in the skill's `templates/person.md`.

Slug the filename as `lowercase-kebab` of the full name (`dave-burawski.md`). Keep the slug stable forever — rename display fields, not the file key.

## Files in This Directory

- `index.json` — entity-resolution registry (aliases + hints + verified ids)
- `OPS-SNIPPET.md` — paste into your agent's ops / system prompt
- `_TEMPLATE.person.md` — blank person file template
- `index.example.json` — fictional worked example (two colliding Sams)
- `<slug>.md` — deep context files, created as needed

**Note:** A primary collaborator file may live at the agent root (e.g. `OWNER.md`) due to frequency of interaction. Point at it from `index.json` via `context_file`.

## Privacy Guidelines

- **Never store secrets or credentials**
- **No private/sensitive personal information**
- Focus on work-related patterns and preferences
- If uncertain about what to include, ask
- Person files are for agent context, not public documentation
- Scope: IRL people the agent interacts with — not YouTube channels, creators, or sources you follow

## Loading Pattern

Person files are loaded **on-demand only**:

1. Check who's talking (verified id, then context clues)
2. If person file exists, load it
3. If uncertain, ask for clarification
4. Never auto-load all person files in every session

See `OPS-SNIPPET.md` for the full agent contract (identity verification + name resolution).
