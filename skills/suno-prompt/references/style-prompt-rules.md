# Suno Style Prompt Rules

The style prompt is what goes in Suno's **Style** box. Separate from lyrics.

## Hard constraints

1. **Under 1000 characters** for the style paragraph. Count every character including spaces. Over = truncated by Suno.
2. **Plain prose only.** No `#` headers, no `*bold*`, no `- bullets`, no numbered lists inside the paragraph. Periods and commas.
3. **No artist, band, or musician names.** Suno ignores them; they burn budget. Describe era + genre + texture instead.
4. **No song titles as style references** inside the style box (same waste / ignore problem).
5. Settings lines (`Title:`, `Weirdness:`, etc.) sit *after* the paragraph and do **not** count toward the 1000.

## What to cover

Aim to hit most of these in one tight paragraph:

| Element | Examples of specificity |
| --- | --- |
| Genre + era | "early 2000s alternative country", "late-90s UK garage" |
| Energy arc | "starts hushed, opens on the second chorus, strip-back bridge" |
| Tempo feel | "mid-tempo sway ~85 BPM", "double-time verses, half-time chorus" |
| Instrumentation | "nylon-string guitar, upright bass, brushed snare, faraway pedal steel" |
| Vocal approach | "close-mic baritone, dry, conversational; stacked doubles on chorus only" |
| Production texture | "tape hiss, narrow stereo, no modern loudness war; room mics audible" |

## Settings meanings

| Setting | Meaning | Typical range notes |
| --- | --- | --- |
| **Title** | Suggested song title for the Suno field | Short, specific; avoid cliché abstractions alone ("Forever", "Dreams") |
| **Weirdness** | Safe vs chaotic generation | Lower = tighter/safer; higher = stranger deviations |
| **Style Influence** | How tightly Suno follows the style paragraph | Higher when the paragraph is precise and you want fidelity |
| **Audio Influence** | How tightly Suno follows an uploaded audio reference | `N/A` if there is no upload; otherwise match how much the ref should dominate |

Exact UI scales change across Suno versions — give a clear qualitative recommendation (e.g. "low–mid", "high", "55%") rather than inventing fake precision.

## Good example

```text
Early 2010s indie folk with a slow-build arc, roughly 78 BPM. Fingerpicked acoustic guitar in the verses, upright bass and brushed snare entering on verse two, pump organ pad under the chorus. Close-mic'd male vocal, dry and conversational, slight crack on higher notes; soft group harmonies only on the final chorus. Production is intimate and slightly lo-fi — room tone audible, gentle tape saturation, no modern gloss or sidechain pump. Ends on a decaying single guitar figure.

Title: Casserole in the Church Lot
Weirdness: low–mid
Style Influence: high
Audio Influence: N/A
```

## Bad examples (and why)

| Bad | Why |
| --- | --- |
| `In the style of Bon Iver and early Sufjan, sonic landscape of aching memory` | Artist names (ignored + waste); buzzword fluff |
| `*Indie folk* with **warm** vocals - guitar - bass - drums` | Markdown residue; list-y not prose |
| A 1600-character paragraph listing every plugin and mic model | Over the 1000 cap; Suno truncates |
| `Emotional, powerful, cinematic, epic journey of the heart` | Zero production information; pure abstraction |

## Character-count tips when you're over

Cut in this order:

1. Redundant adjectives ("warm soft gentle tender" → pick one)
2. Repeated instrument mentions
3. Energy-arc detail that lyrics brackets already cover
4. Production metaphors that don't change the sound

Never cut the genre/era or the vocal approach first — those steer generation hardest.

## Optional validation

```bash
python3 scripts/check-style-prompt.py path/to/slug-style-prompt.txt
```

Checks: style-paragraph length ≤ 1000, no markdown markers, heuristic artist-name warnings, settings lines present.
