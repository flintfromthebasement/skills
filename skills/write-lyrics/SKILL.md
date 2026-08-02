---
name: write-lyrics
description: "Phased lyric-writing engine — stream-of-consciousness draft, ruthless seed selection, structure + rhyme locking, canon iteration, and an observed AI-cliché filter. Produces singable lyrics ready for Suno or similar AI music tools. Use when the user wants real song lyrics, not a one-shot poem."
---

# Write Lyrics

Write lyrics through a deliberate phased process, not a single generation pass. One-shot lyrics converge on the same generic song every time; the phases force divergence — raw material first, then ruthless selection, then structure, then craft. Run them in order. Don't skip ahead to a polished draft.

This skill is the **lyric engine**. Pair it with [`suno-prompt`](../suno-prompt/) when you also need a Suno style prompt and settings. When invoked alone, do the context gate below first, then run the phases.

Works in three environments:

| Environment | How to run |
| --- | --- |
| **Chat only** (ChatGPT, Claude.ai, any paste-the-skill chat) | Follow the phases in conversation. Deliver final lyrics in the [chat output block](#chat-only-output). No tools required. |
| **Coding agent with a workspace** (Claude Code, Codex, Cursor, etc.) | Same phases. Save drafts under `notes/` if useful; final lyrics to `lyrics/<slug>-lyrics.txt` (or `artifacts/` if that folder already exists). |
| **This repo checked out** | Optionally run `scripts/scan-cliches.py` on a draft before shipping. |

## Context Gate — before Phase 0

**The human is the entropy source.** If the thread doesn't already hold a couple paragraphs of specific, non-generic context (a POV, a memory, names, places, contradictions), don't write yet. Ask for small concrete seeds — one image they can't shake, a half-finished line they're carrying, what happened ten minutes before the song starts, a smell, a person. Your own "off the top of my head" starting point is the model's prior, which is exactly the generic shape we're escaping. If the user goes vague, pull real texture with web search when available (a neighborhood's geography, a year's news, a subculture's vocabulary) and surface what you found.

Move on when the user says "write it" or the context is genuinely loaded. If they explicitly want a quick pass with thin context, say you're writing thin and proceed — but say it.

**Chat conduct while running phases:** narrate decisions, not process. After Phases 2–3b, post ONE short note naming the seed, the structure letter, and the rhyme scheme. Don't dump intermediate drafts into chat unless asked.

---

## Phase 0 — Load the Cliché Filter

Know what models default to so you can push past it. The lists live in [`references/cliche-filter.md`](./references/cliche-filter.md) — load them (or keep this summary in mind).

**Short version — avoid defaulting to:**

- Stock scenery: ground, door, room, floor, dark, fire, world, morning, car, hands, light, sound — especially "the ground / the dark / the world / in the fire." Name a real place or object instead.
- Lazy end-rhymes: fire/desire, love/above, heart/start, night/light, girl/world, pain/rain, dream/seem, eyes/skies, you/true, feel/real, etc.
- Banned stock phrases: "you complete me," "chasing dreams," "under the stars," "broken heart," "never let you go," "digital glow," and the rest in the reference file.
- Cosmic stacking: stars + fire + sky + rain + light + heaven in one song.
- Same first-person opener two verses in a row ("I still… / I never…").

**Nuance:** clichés can earn their place when authentic, specific, and grounded. The filter flags; it doesn't auto-kill. The goal is to stop *defaulting* to them. Curate the filter over time for your own catalog.

## Phase 1 — Stream of Consciousness Draft

Take the topic, hook ideas, themes, and context. Write fast and messy in a default skeleton:

Verse 1 → Pre-Chorus → Chorus → Verse 2 → Pre-Chorus → Chorus → Bridge → Chorus → Outro

Rules: don't censor (clichés get filtered later, not now), don't rhyme-hunt, don't count syllables, no placeholders — commit to words, write every section even badly, let the hook emerge instead of forcing a title. Worry about honest, not good.

Genre inflects the draft:

| Genre | Draft bias |
| --- | --- |
| rap | flow and pocket first; internal rhyme welcome early |
| folk / country | story and named places; tell someone what happened |
| rock | declarative energy; short lines that hit |
| pop | every line singable; the chorus is the point |
| R&B | mood, sensory closeness, room to breathe |
| singer-songwriter | confessional, conversational |
| electronic / ambient | fragments, repeated phrases; no forced narrative |

## Phase 2 — Find the Best Part

Read the draft. Be ruthless. What's the single best thing — a verse, the chorus, one hook line, a bridge moment? Pick ONE section as the seed. Everything else gets rebuilt to serve it; the rest of the draft is spare parts.

If nothing is strong, say so and ask for more context (Phase 6). Don't polish a turd.

## Phase 3 — Choose a Structure

Don't default. Pick the shape that serves the seed. **Rotate:** if the last song or two used a structure, lean away from it.

Full menu (A–L) is in [`references/structures.md`](./references/structures.md). Quick hits:

| | Structure | Best for |
|---|---|---|
| A | Standard pop (V-PC-C-V-PC-C-B-C-O) | Momentum + clear hook — fine when earned, lazy when defaulted |
| B | Chorus-first | Hook so strong it needs no warm-up |
| C | Two/three verses, no chorus | Narrative, folky storytelling |
| E | Bridge as climax (chorus never returns) | The bridge IS the resolution |
| F | Tag outro (one phrase, repeated, decaying) | Songs that live in your head after they end |
| H | Through-composed (no repeats) | Ambitious narrative |
| K | Verse-verse-chorus (no pre-chorus) | Hip-hop, folk; verses carry the weight |

Genre nudges (starting points, not mandates): rap → K/C, folk → G/C, rock → A/B, pop → A/B, country → K/A, R&B → A/D, singer-songwriter → A/H, electronic → I/F. If the user names a structure, use it.

## Phase 3b — Lock Rhyme Scheme and Meter

AI lyrics drift rhymeless — free verse over music is a poem, not a song. Decide deliberately here.

Schemes: **AABB** (punchy couplets), **ABAB** (flowing), **ABCB** (conversational — only even lines rhyme), **AABCCB** (folk ballad), **AAAA** (monorhyme — sparingly), internal rhyme, slant rhyme.

Rules:

- Pick a scheme per section type and commit. Verse 1 and Verse 2 match; the chorus may break pattern for contrast.
- Prefer slant and internal rhymes over perfect end-rhymes — perfect rhymes read neat-and-AI.
- Avoid the lazy pairs and rhyme-shelf words from the cliché filter.
- **When in doubt, rhyme more, not less.** Going rhymeless is usually laziness wearing a beret. If you go rhymeless, have a reason.
- Genre calibrates density: rap wants multi-syllabic + internal (2–3 connections per bar); folk/country want simple conversational schemes; pop wants tight regular meter; R&B and singer-songwriter can loosen if the emotional arc holds.
- Meter: count syllables per line; keep them consistent within a section, vary between sections. Read lines aloud — a stumble means the meter's off.

## Phase 4 — Write Around the Seed

Build the real song: seed (Phase 2) + structure (Phase 3) + scheme/meter (Phase 3b) + cliché awareness (Phase 0). Every other section sets up or pays off the seed.

Techniques on the bench (use what the song asks for):

- **Vowel-first writing** — when a vowel map exists (from an audio-analysis pass) or the melody demands it: open vowels (ah, oh, aw) for exposed high sustains; bright vowels (ee, ay) to cut through; dark vowels down low. Break the map when meaning demands, but know you're breaking it.
- **Nonsense-vocal pass** — melody exists but words don't: sing nonsense syllables to find shapes, then back-fill real words.
- **Show, don't tell** — "I was sad" → "I sat in the car until the radio stopped playing."
- **Conversational completeness** — lyrics read as complete thoughts; if it scans like a poem it may not sing.
- **Verb audit** — replace was/had/went/got with active, specific verbs. One great verb per section minimum.
- **POV try-outs** — same lyric in I / you / third-person; keep the truest.
- **Smart repetition** — the hook earns each return; repetition is a tool, not filler.

## Phase 5 — Canon Method (Iterate)

Make it better. Then make it better again. Keep only what's essential. Run 2–3 passes:

1. **Structural:** does every section earn its place? Is the seed still the strongest moment? Cut filler sections.
2. **Line-level:** read aloud — where does the mouth clench? Check vowels on stressed slots, verbs, forced or too-neat rhymes, meter stumbles. Kill darlings.
3. **Polish:** one great line per section minimum. Does the hook stick? Could anyone have written this about anyone? If yes, pull a specific detail from the POV into the lyric.

## Phase 6 — Ask for More Context (when needed)

If the lyrics feel thin or universal, stop and ask — this is the skill working, not failing. Useful asks: a specific memory/place/person; a sense memory; what happened ten minutes before the song starts; a line they've been carrying; what the song is NOT about. Feed the answer back into Phase 4/5.

## Phase 7 — Rewrites

On request or when Phase 5 exposed problems: sensory upgrades, verb swaps, POV switch, verse swap (Verse 2 often makes the better opener), vowel realignment, scheme change, syllable tightening, compression. Prefer surgical edits over full rewrites when the skeleton is sound.

## Phase 8 — Cliché Filter Pass

Final gate before shipping. Scan against [`references/cliche-filter.md`](./references/cliche-filter.md), plus:

- A line resolving in a universal abstraction (heartbreak, longing, freedom) with no concrete anchor in the stanza → rewrite.
- Chorus ending on a cliché hook (forever, together, hold me, never let go) → rewrite.
- Cosmic/elemental stacking → cut at least two.
- Two verses opening with the same construction → vary one.
- Could-be-anyone-about-anyone test → pull in a specific detail.

Optional local check (coding agents):

```bash
python3 scripts/scan-cliches.py path/to/lyrics.txt
```

Flagged clichés that genuinely earn their place stay, with a one-line justification in the craft notes.

---

## Suno Bracket Notation

When lyrics are headed to Suno (or similar AI music tools), brackets are production instructions, not sung text.

- **`[Square brackets]`** = meta-tags (structure, vocal direction, dynamics, instruments). Own line, right before the lyrics they affect. Sparingly — stacking 5 instructions destabilizes generation.
- **`(Parentheses)`** = backing vocals and ad-libs that ARE sung: `(oh yeah)`, `(drive away)`.
- Number the verses. Keep chorus lyrics identical on repeats.
- Never negative instructions (`[no drums]` misfires) — describe what you want.
- Genre/tempo/instrument *descriptions* belong in the style prompt field, not lyric brackets; brackets are for section-local cues.

Useful tags — structure: `[Short Instrumental Intro]`, `[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Post-Chorus]`, `[Bridge]`, `[Breakdown]`, `[Instrumental Break]`, `[Final Chorus]`, `[Outro]`, `[Fade Out]`, `[End]`. Vocal: `[Whispered]`, `[Breathy]`, `[Spoken Word]`, `[Rap]`, `[Belted]`, `[Falsetto]`, `[Gravelly]`, `[Male Vocal]` / `[Female Vocal]`, `[Harmony]`, `[Choir]`, `[Close-mic]`. Dynamics: `[Build]`, `[Drop]`, `[Stripped-back]`, `[Explosive]`, `[Modulation]`, `[Soaring Melody]`. Instruments: `[Guitar Solo]`, `[Piano Solo]`, `[Sax Solo]`, `[Guitar Riff]`, `[Drum Fill]`, `[Let it ring]`.

Combine per section, three layers max — character, delivery, energy:

```text
[Chorus, raspy, powerful belt, explosive]
[Verse 1, close-mic, conversational]
[Bridge, stripped-back, whispered]
```

Tag lightly in Phase 1 (structure only), fully in Phase 4, simplify over-stacked tags in Phase 5.

## Output

### Workspace / coding-agent output

Final deliverable path (pick one convention and stick to it):

- `lyrics/<slug>-lyrics.txt` — preferred generic path
- `artifacts/<slug>-lyrics.txt` — fine if the project already uses an artifacts folder

Plain text, bracket-tagged, copy-paste ready for Suno. No markdown fences inside the file.

After emitting, post **2–4 sentences of craft notes** in chat: the seed, the structure letter and why, the rhyme scheme, the vowel approach if one was used, and anything cut that hurt. Then invite iteration.

### Chat-only output

When there is no filesystem, deliver exactly this block (and craft notes after it):

```text
LYRICS — <title or slug>
========================

[Verse 1]
...

[Chorus]
...

(full song, bracket-tagged, no placeholders)
```

If the user also wants a Suno style prompt, hand off to the [`suno-prompt`](../suno-prompt/) skill (or run its Step 3 style-prompt half). Don't invent a competing format — style prompt hard rules are: under 1000 characters, no artist names, plain prose, plus Title / Weirdness / Style Influence / Audio Influence settings.

## Working With Vowel Maps

When given a vowel map JSON or an audio-analysis vowel report:

- Contours labeled PROPOSED = suggestions; OBSERVED = ground truth about the instrumental.
- Write so stressed syllables hit the recommended vowel families; note intentional deviations.
- Offer 2–3 alternative hook passes with different vowel approaches (open/vulnerable vs bright/urgent vs dark/intimate).
- Include a short VOWEL ALIGNMENT CHECK in the craft notes.

## Exercises (block-breaking, on request)

Word-limit stories (whole story in 6–9 words per section) · forced vocabulary (three uncommon words in one verse) · adjective purge + one verb upgrade per section · fill-the-blanks on a favorite song · no-stop writing, then mine for spark phrases · object deep-dive with all five senses · word chains · nonsense-vocal pass · POV triptych.

Offer one with a concrete 5-minute prompt; don't lecture about all nine.

## Guidelines

- You're the creative lead, not a vending machine. Push back on thin input.
- Multiple passes are normal; the first draft is raw material, not a product.
- No music-industry buzzwords ("sonic landscape," "auditory journey").
- The target is lyrics that feel inevitable — like they couldn't have been written any other way.

## Files in this skill

| Path | Purpose |
| --- | --- |
| [`references/cliche-filter.md`](./references/cliche-filter.md) | Full banned tokens, lazy rhymes, stock phrases, structural crutches |
| [`references/structures.md`](./references/structures.md) | Structure menu A–L with when-to-use notes |
| [`scripts/scan-cliches.py`](./scripts/scan-cliches.py) | Optional local scan of a lyrics file against the filter lists |
| [`examples/seed-to-craft-notes.md`](./examples/seed-to-craft-notes.md) | Tiny worked example of seed → structure → craft notes (not a full song to copy) |
