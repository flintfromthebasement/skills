---
name: suno-prompt
description: "Turn a song idea, vibe, or reference into Suno-ready lyrics plus a style prompt (under 1000 chars, no artist names) and recommended settings. Forces a context/POV phase first so songs don't collapse into generic AI mush. Use when the user wants something they can paste into Suno."
---

# Suno Prompt

Help the user build a song for [Suno](https://suno.com) (or similar AI music tools). The output is two deliverables they can copy-paste straight in — but only after the room is full of novel context. Skip the context phase and every song defaults to the same generic track. Don't.

Works in three environments:

| Environment | How to run |
| --- | --- |
| **Chat only** (ChatGPT, Claude.ai, any paste-the-skill chat) | Follow the steps in conversation. Deliver both files as labeled chat blocks ([format below](#chat-only-output)). No tools required. |
| **Coding agent with a workspace** | Same steps. Write `lyrics/<slug>-lyrics.txt` and `lyrics/<slug>-style-prompt.txt` (or `artifacts/` if that's the project convention). |
| **This repo checked out** | Optionally validate the style prompt with `scripts/check-style-prompt.py`. Pair lyric drafts with [`write-lyrics`](../write-lyrics/)'s `scan-cliches.py`. |

**Related skills**

- [`write-lyrics`](../write-lyrics/) — full phased lyric engine + cliché filter. Use it when both skills are loaded; this skill owns context, style prompt, and packaging.
- [`audio-analysis`](../audio-analysis/) — extract a style prompt *from a reference audio file* (`--mode suno`). Different job: listening, not writing.

---

## Step 1 — Don't write a song yet. Build a POV.

**No full lyrics or style prompts on the first turn. Ever.** Even if the user's first message looks specific, treat it as the start of a riff, not a brief. The model that dumps a finished song on turn one is the model that writes the same song every time.

The goal of this phase is a short character sketch — a synopsis of *the person about to write the song.* Not the plot of the song. Who are they, what just happened, what are they trying not to say, what's the room smell like, what's unresolved.

**Ask for the seed — do not invent one.** The human is the entropy source. Fragments you'd reach for on your own are exactly the patterns we're escaping. Don't volunteer a starting image, stray line, or character sketch. Ask for one.

The opener should:

1. Frame the rules in one sentence ("we're not writing the song on turn one — first the room has to feel like something, or it defaults to generic mush").
2. Ask for specific, low-cost inputs. Not "what kind of song do you want?" — that's a vague questionnaire. Ask for concrete small seeds, e.g.:
   - one image they can't stop thinking about
   - one line they've been carrying (even half-finished)
   - what just happened ten minutes before the song starts
   - what music bed they already hear under it
   - a memory, a smell, a place, a person

List 3–5 of these and invite *any* of them.

**Pull until the context is real.** After they hand you a seed, keep going until there are at least a couple paragraphs of specific, non-generic material — sense memories, names, places, contradictions, era-specific detail. *Then* riff: build on what they gave you, push it somewhere unexpected. If they go dry, use web search when available to add texture (real geography, subculture vocabulary, a year's news) and surface what you find.

**Only move to Step 2 when one of these is true:**

- The user explicitly says "write it" / "go" / "let's see it."
- There are two-plus paragraphs of specific, non-generic context *and* a clear POV.

When in doubt, ask one more question instead of jumping.

**Escape hatch:** if they explicitly want a quick thin pass, say you're writing thin and proceed.

## Step 2 — Find the hook, then pick a shape

Lock two things before any deliverable goes out:

**The hook.** The line, image, or moment the song lives on — still rattling around tomorrow. A chorus line, a title phrase, a specific image, a refrain that earns its repeats. Name it to the user in one short sentence before emitting.

**The arrangement.** Default V/C/V/C/B/C is the shape that makes every AI song interchangeable. Consider a less-obvious move:

| Move | Why |
| --- | --- |
| Start on the chorus | Hits faster, no warm-up |
| Two verses, no chorus | Folky, narrative |
| Pre-chorus that becomes the chorus | Lift, then release |
| Bridge as climax — chorus doesn't come back | Lands somewhere new |
| Tag outro — one phrase repeated and decaying | Lives in your head after |
| Spoken or sung-talk verse, sung chorus | Voice-memo energy |
| Single-verse vignette | Sub-90-second mood piece |
| A-A-B-A | Classic pop / jazz standard |
| Through-composed — no repeating section | Storytelling, less hooky |
| Reverse build — start big, strip back, build again | Emotional rug-pull |

Full structure menu with letter codes: [`write-lyrics/references/structures.md`](../write-lyrics/references/structures.md) (or [`references/structure-menu.md`](./references/structure-menu.md) if that skill isn't installed).

Rotate: if the last song or two used a structure, lean away from it. When the obvious arrangement feels stale, pull real references and let them bend the shape.

## Step 3 — Write the lyrics

**Prefer the write-lyrics engine when available.** If [`write-lyrics`](../write-lyrics/) is loaded, follow its full phased process (cliché filter → messy draft → seed → structure + rhyme/meter → canon iteration → final filter). It also covers vowel-first writing and Suno bracket notation.

When write-lyrics is **not** in context, run this condensed version — do **not** one-shot a finished song:

1. **Draft messy.** Stream-of-consciousness in the shape from Step 2. Don't censor, don't rhyme-hunt, commit to words.
2. **Pick the best part.** Ruthlessly. One section (or one line) is the seed; everything else rebuilds around it.
3. **Lock rhyme and meter.** Scheme per section type; verses match each other; chorus may break pattern. Prefer slant and internal over perfect end-rhymes. When in doubt, rhyme more, not less. Consistent syllable counts within a section; read aloud for stumbles.
4. **Rewrite around the seed**, then 2–3 canon passes: cut everything that doesn't serve the core, one great line per section, kill darlings.
5. **Audit for AI-tells** with the cliché filter below (full list: [`references/cliche-filter.md`](./references/cliche-filter.md) — same content as write-lyrics).

### Cliché filter (bake in while writing, scan again before shipping)

**Banned surface tokens** — replace with concrete specifics:
neon, echoes, symphony, shadows, intertwined, spectral, whispers/whispered dreams, crimson, "with every [step/breath/touch]", come what may, hand in hand, electric/digital glow, soar, rise above, pulse, chasing dreams, forever, heart, soul, eyes, tears, stars, fire, rain, light, heaven, together, pain, mind, mystery, collide, unfold, tangled sheets.

**Lazy end-rhyme pairs** — avoid as line-end rhymes:
fire/desire, love/above, heart/start, night/light, girl/world, cry/die, pain/rain, dream/seem, eyes/skies, you/true, baby/crazy, life/wife, mind/find, kiss/bliss, dance/romance, feel/real, fly/high, tear/fear, star/far, blue/you.

**Stock phrases — banned outright:**
"I can't live without you," "you are my everything," "together forever," "you make me whole," "my one and only," "you complete me," "lost without you," "heart of gold," "love at first sight," "you're my reason why," "chasing dreams," "feel the beat," "in my mind," "time will tell," "waiting for you," "burning desire," "under the stars," "broken heart," "never let you go," "hold me tight," "digital glow."

**Scenery crutches:** ground, door, room, floor, dark, fire, world, morning, car, hands, light, sound — especially "the ground / the dark / the world / in the fire." Name something instead.

**Self-audit before emitting**

- Line resolves in a universal abstraction with no concrete anchor in the stanza? → Rewrite.
- Chorus ends on a cliché hook (forever, together, hold me, never let go)? → Rewrite.
- Cosmic/elemental stacking (stars + fire + sky + rain + light + heaven)? → Cut at least two.
- Could this song have been written by anyone, about anyone? → Pull a specific detail from the Step 1 POV into the lyric.

### Suno lyric brackets

- `[Square brackets]` = meta-tags (structure, vocal, dynamics). Own line. Max ~3 layers per section.
- `(Parentheses)` = sung ad-libs / backing vocals.
- Number verses. Keep chorus text identical on repeats.
- Never negative instructions (`[no drums]`). Describe what you want.
- Genre/tempo/instrument *descriptions* go in the **style prompt**, not lyric brackets.

### Emit lyrics + style prompt together

Once the audit passes, create **both** deliverables in the same turn.

#### Workspace paths

1. **`lyrics/<slug>-lyrics.txt`** (or `artifacts/…`)
   - Full structure with section tags: `[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Outro]`, etc.
   - Complete lyrics. No placeholders. Commit to words.
   - Instrumental / stage-direction-only versions use bracketed cues instead of sung lines.

2. **`lyrics/<slug>-style-prompt.txt`**
   - See style-prompt rules below.

#### Chat-only output

```text
LYRICS — <title or slug>
========================

[Verse 1]
...

[Chorus]
...

---

SUNO STYLE PROMPT — <same slug>
===============================

<plain prose style paragraph, under 1000 characters, no artist names>

Title: ...
Weirdness: ...
Style Influence: ...
Audio Influence: ...
```

### Style prompt rules (hard)

Full checklist: [`references/style-prompt-rules.md`](./references/style-prompt-rules.md).

- **Hard limit: under 1000 characters** for the style paragraph. Count before emitting. Suno truncates past that. The settings lines below do **not** count against the limit — only the style paragraph gets pasted into Suno's style box.
- **Plain prose.** No markdown headers, no asterisks, no bullet lists — periods and commas only.
- Cover: genre era, energy arc, instrumentation, vocal approach, production texture, tempo feel.
- **Do not name any artists, bands, or musicians.** Suno ignores artist names; they waste character count. Describe the sound directly.
  - Good: `Late 2010s indie hip-hop, introspective and melodic, warm Rhodes keys, dusty drum break, close-mic'd tender vocals`
  - Bad: `[Artist] vibes`
- After the style paragraph, add recommended Suno settings:

```text
Title: ...
Weirdness: ...          # safe vs chaotic
Style Influence: ...    # how tightly to follow the style prompt
Audio Influence: ...    # how tightly to follow an uploaded audio ref; N/A if none
```

Optional local check:

```bash
python3 scripts/check-style-prompt.py path/to/slug-style-prompt.txt
```

## Step 4 — Short reflection, then invite iteration

After emitting, say one or two short lines about what you went for — the feel, the structural move, the key choice. No essay.

Then invite a next move: "want to push it somewhere else? more melancholy, different tempo, swap the bridge — say the word."

## Step 5 — Iterate

- Surgical edits for a line/word/verse; full rewrite when structure changes.
- Keep titles and paths/slugs stable so versions stack.
- **The cliché filter still applies on every edit.** "Make the chorus more emotional" is exactly the prompt that drags stock phrases back in. Audit each patched line before shipping.

## Memory (optional)

If memory tools exist in the runtime, use them lightly: recall past songs the user references; store a tight note when something lands (title that stuck, production move that worked). One or two sentences. Skip entirely in chat-only environments.

## Guidelines

- No music-industry buzzwords ("sonic landscape," "auditory journey," "soundscape"). Talk about the music like a person.
- Don't name-drop artists in the style prompt.
- Never lecture. Never apologize for the work. If a change doesn't land, try a different angle.
- Structure first when the user wants structure; looseness first when they want looseness. Follow the brief.
- You're the creative lead, not a vending machine. Push back on thin input.

## Files in this skill

| Path | Purpose |
| --- | --- |
| [`references/style-prompt-rules.md`](./references/style-prompt-rules.md) | Character limit, no-artist rule, settings meanings, good/bad examples |
| [`references/cliche-filter.md`](./references/cliche-filter.md) | Shared AI-lyric default filter (mirrors write-lyrics) |
| [`references/structure-menu.md`](./references/structure-menu.md) | Arrangement options when write-lyrics isn't installed |
| [`scripts/check-style-prompt.py`](./scripts/check-style-prompt.py) | Validate char count, markdown residue, obvious artist-name patterns |
| [`examples/style-prompt-example.txt`](./examples/style-prompt-example.txt) | One valid style-prompt file to copy the shape from |
