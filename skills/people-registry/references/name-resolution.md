# Name Resolution

How an agent turns a spoken name into a specific person entry.

## Why this exists

First names collide constantly. "Sam" might be a childhood friend or a lead developer. "Sam" might be a teammate who goes by Sam only (never Samantha) or someone's father. Without a registry + hints, agents either:

- Guess (and get it wrong with confidence)
- Ask every time (annoying for known people)
- collapse everyone named Sam into one mental bucket

## The algorithm

```
mention ("my friend Sam")
        │
        ▼
1. Load people/index.json
        │
        ▼
2. Find all entries whose `aliases` contain the name token
   (case-insensitive; match full alias strings, not substrings of other words)
        │
        ├─ 0 matches ──► treat as unknown; ask, or add as new if clearly recurring
        │
        ├─ 1 match ────► resolve to that entry; go to step 4
        │
        └─ N matches ──► step 3
                │
                ▼
3. Score each candidate by `hints` overlap with surrounding context
   ("friend", "team", project names, workplace, family terms, agent names…)
   Highest unique score wins. Tie → ask.
                │
                ▼
4. Optional: recall long-term memory with full_name + aliases as queries
   (confirms, enriches; does not override a clear registry match)
                │
                ▼
5. If context_file is set and the person is relevant to this turn, load it
                │
                ▼
6. Proceed. If anything still feels off, ask one short clarifying question.
```

## Writing good aliases

- Include the first name, full name, common nicknames, and handles people actually use
- Include abbreviated forms only if they're used in speech ("Sam O", "A.R.")
- Don't include other people's names as aliases
- Prefer exact strings the agent will see in chat over speculative ones

## Writing good hints

Hints are **disambiguators**, not biographies. Ask: *if two people share an alias, what words around the mention would point at this one?*

| Good hints | Bad hints |
| --- | --- |
| `friend`, `team`, `wife`, `lead dev` | `person`, `human`, `guy` |
| Project names: `Atlas`, `Northwind` | Generic job titles with no contrast |
| Workplace / community: `guild`, `lab` | Hints shared by every candidate |
| Agent they run: `AutoPat` | Their full name repeated |

A hint only earns its keep if it would change a resolution decision.

## Adding someone new

When a name keeps coming up and isn't in the registry:

1. Pick a stable slug: `lowercase-kebab` of the full name
2. Add the entry with `aliases`, `hints`, `relationship`, empty `verified_ids` if unknown
3. Store a memory (if you have one) tagged as a person-entity, including aliases
4. Create `people/<slug>.md` only if they'll be frequent (weekly+)
5. Fill `verified_ids` when you have a platform-verified signal — never invent one

## What not to resolve automatically

- Ambiguous mentions with no useful context ("tell Sam") and multiple candidates → ask
- Mentions of public figures / creators who aren't in the registry → don't invent entries
- Self-referential agent talk ("the agent should…") — that's nominative, not a person lookup

## Worked example

Registry has:

- `sam-chen` — aliases `["Sam"]`, hints `["friend", "climbing"]`
- `sam-okonkwo` — aliases `["Sam", "Sam O"]`, hints `["team", "support", "site audits"]`

| Mention | Resolution |
| --- | --- |
| "my friend Sam" | `sam-chen` (hint: friend) |
| "Sam on the team" | `sam-okonkwo` (hint: team) |
| "Sam" alone, no context | ask |
| "Sam O" | `sam-okonkwo` (only one alias match) |
