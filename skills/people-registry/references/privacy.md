# Privacy & Scope

Person files and the registry are agent context. They are not a CRM, not a public directory, and not a place for anything that would harm someone if leaked.

## In scope

IRL people the agent actually interacts with:

- Teammates and collaborators
- Family the agent messages
- Friends who show up in real conversations
- Other agents' humans (when the agent pair is relevant)

## Out of scope

- YouTube channels, newsletter authors, design inspiration, podcast hosts
- Public figures the agent has never spoken to
- Companies / brands (use a projects or sources note)
- Anyone added "just in case"

If the agent follows someone's work but doesn't talk to them, that's a **source**, not a **person entry**. Keep sources in a bookmarks / reading-list note — not in `people/`.

## Never store

- Passwords, API keys, tokens, recovery codes
- Government IDs, financial account numbers
- Private medical or legal details
- Home addresses or precise location data unless the human explicitly wants the agent to know and the risk is accepted
- Anything the person would reasonably expect to stay out of an agent-readable file

When uncertain, **ask the human before writing**.

## Minimize

Prefer:

- Work-relevant preferences ("likes short replies", "reviews PRs in the morning")
- Stable identifiers needed for verification
- Relationship one-liners that help disambiguation

Avoid:

- Long biographical essays
- Gossip
- Speculative personality diagnoses
- Duplicating information that already lives in a shared handbook or HR system

## Leakage mindset

Assume person files could be:

- Read by anyone with access to the agent host
- Pasted into a prompt that gets logged
- Included in a context dump during debugging

Write accordingly. If a sentence would be awkward in a shared channel, it doesn't belong in the file.

## Agents vs humans

If you track other agents (AutoPat, …):

- Give them their own registry entry
- Mark the relationship clearly (`"relationship": "AI agent built by …"`)
- Link agent ↔ human with `agent` / `human` slug fields
- Don't pretend an agent is a human in identity verification — agent identity is a different signal (daemon id, bot user id), not a person's Slack email
