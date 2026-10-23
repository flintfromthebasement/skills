# Models: what each is for, and how to prompt it

Observations marked "we found" come from real A/B runs (judged by ear and by Gemini via the `audio-analysis` skill), not from model cards.

## ACE-Step 1.5

Open (MIT), diffusion (DiT) with an optional 5Hz LM "planner". Repo: https://github.com/ace-step/ACE-Step-1.5.

**Good at:** speed, instrumentals, genre range, and every reference-audio trick. **Weaker at:** lead vocal quality and long-form structure compared to Music 3.

**Caption.** Short prose, under 512 characters. Genre, instrumentation, production, mood. Never paste a Music 3 mega-caption in.

```
late-night jazz trio, brushed drums, upright bass walking, warm felt piano, smoky club room, relaxed swing
```

BPM, key, and time signature have typed parameters: `--bpm 96 --key "E minor" --time-signature 4`. Use them instead of prose. Leave them empty and the LM fills them in.

**Lyrics.** Section tags on their own line. `--instrumental` sends `[Instrumental]`. `--language ja` (etc.) for non-English vocals.

**Knobs.**

- `--seconds` 10–600. Omit to let the LM pick a length.
- `--steps` diffusion steps. Turbo models default to 8 (range 1–20); base models want 32–64.
- `--thinking` runs the 5Hz LM to plan audio codes first. Better structure, slower.
- `--dit-model` picks a DiT on the server (`acestep-v15-turbo`, `acestep-v15-xl-turbo`, …; list them with `GET /v1/models`). `api` backend only: the Modal app loads `acestep-v15-turbo`, so the CLI refuses the flag on `modal` and `gateway`.

### Reference audio (ACE-Step only)

| `--task` | What it does | Needs |
|---|---|---|
| `text2music` + `--ref-audio` | New song, borrowing the reference's sound and playing style | `--ref-audio`, `--strength` |
| `cover` | Re-render a track in a new style, keeping structure and melody | `--src-audio`, `--strength` |
| `repaint` | Regenerate one time window, keep the rest | `--src-audio`, `--repaint-start/end` |
| `lego` | Generate specific instrument tracks against a source | `--src-audio` |
| `extract` | Isolate instrument tracks (stem-ish) | `--src-audio` |
| `complete` | Add instruments to a partial mix (vocal → full band). **Not** time extension: output stays the source's length | `--src-audio` |

`--strength` (audio_cover_strength, 0–1): 1.0 hugs the source structure; 0.7–0.9 is a faithful cover; **0.2–0.4 is vibe-only style transfer**. Omit it and the CLI sends 0.3 for `text2music --ref-audio` and 1.0 for the source-audio tasks.

What we found:

- **Don't max the influence.** A 23s steel-guitar riff as reference: 0.2 came back "flawless" (solo fingerstyle, right key and tempo, new melody); 0.5 stayed correct but got repetitive and blocky. Same lore as Suno's Audio Influence slider.
- **Vocal covers need lyrics.** Cover a vocal track with empty lyrics and you get an instrumental. Pass the original (or new) lyrics.
- **No time extension.** To grow a riff into a song, use it as `--ref-audio` on `text2music` and describe the arrangement in the caption.
- **Fix bad bars with `repaint`** instead of re-rolling the whole song.

## MiniMax Music 3

Open weights (MiniMax-Music3 Community License: credit "MiniMax-Music3" on commercial UIs; companies over $20M/yr revenue need separate authorization). Autoregressive composer (25 frames/s) plus a flow-matching renderer. Weights: https://huggingface.co/MiniMaxAI/MiniMax-Music3. Runs through a diffusers PR that isn't on main yet; `modal/music3_app.py` pins the commit.

**Good at:** vocals, lyric adherence, full-song structure up to ~5 minutes. **Weaker at:** solo instruments, sparse arrangements, instrumentals, speed. Text only: it can't hear reference audio (see the sound-transfer note below).

**Lyrics.** Required unless `--instrumental`. Tags: `[Intro] [Verse] [Pre-Chorus] [Chorus] [Post-Chorus] [Bridge] [Instrumental] [Solo] [Outro]`, each on its own line. `[Verse] words` silently drops the words.

**Caption.** The caption decides the sound; the lyrics don't. Write it long and concrete. MiniMax's own demo captions (https://minimax-ai.github.io/music3-demo/) are the house style:

- Open flat when you know them: `bpm is 165. key is E, and scale is major. 2000s Pop Punk.`
- 250–600 words for a full song.
- **Producer vocabulary, not adjectives**: "palm-muted downstrokes", "side-chain compression for a pumping feel", "reverse cymbal swells into transitions", "back-phrasing behind the beat". That steers far better than "energetic" or "dreamy."
- **State contrast between sections**: "narrative, subdued verses" vs "anthemic choruses".
- **Say what's absent**: "avoids a traditional drum kit; dampened tambourine and floor tom with mallets."
- **Always name vocal gender and timbre** on vocal tracks, or it may drift instrumental.
- Don't paste lyric lines into the caption. Don't invent a BPM, key, or vocal gender the user didn't give.

A structure that works (the model only needs the content, the headers are for you):

```
Global: genre/subgenre, tempo range, key if known, emotional arc, production profile.
Vocals: gender, timbre, delivery, harmonies, effects.
Arrangement: section by section, what enters, exits, or intensifies.
```

What we found:

- **Density is a prompt problem.** Words like "raw", "simple", "stripped", "close", or naming one guitar produce a hollow demo. Name 4+ instruments that stay in through the verses; save thin textures for the bridge.
- **It regresses toward mid-density.** Ask for a full band and it thins out; ask for one solo guitar and it adds bass, drums, synths, or a singer, even when the caption says "no vocals, one guitar only" three ways. Use ACE-Step for solo pieces.
- **Instrumentals end early.** A two-section sheet ended at ~35s on a 150s cap. A tag-only sheet (`[Intro]`, `[Verse]`×3, `[Bridge]`, `[Outro]`, each line `(instrumental)`) paced it to 88–150s. `--instrumental` with no lyrics sends that sheet; to shape the sections yourself, pass your own tag-only sheet with `--lyrics-file` alongside `--instrumental`. Keep the `(instrumental)` lines: bare structure tags invite vocals back.
- `--seconds` is a cap, not a target.

**Sound transfer (Modal app only).** `modal/music3_app.py` can pin a reference clip's latents into the renderer: `--ref-audio riff.wav --strength 0.2-0.4 --ref-tile` copies the reference's timbre, room, and technique across the song, and is the only way we found to keep Music 3 on a solo instrument. It doesn't teach the composer the riff; true continuation needs an audio→token encoder MiniMax didn't release.

## HeartMuLa 3B

Open vocal song model (https://github.com/HeartMuLa/heartlib). Lyrics + comma-separated style tags.

```
--prompt "acoustic,folk,female vocal,warm,intimate,96 bpm" --lyrics-file lyrics.txt
```

Vocal-only in practice; use ACE-Step or Lyria for instrumentals. Up to 240s. A useful second voice when Music 3's take isn't landing, and lighter to host. Check the model card for license terms before commercial use.

## Lyria RealTime (Google)

Hosted, instrumental-only, streaming. Needs `pip install google-genai` and `GEMINI_API_KEY` (free key at https://aistudio.google.com/apikey). Model `models/lyria-realtime-exp` (override with `LYRIA_MODEL`); the API is marked experimental.

One mood/instrumentation sentence: `calm cinematic underscore, soft strings, subtle piano`. `--bpm` is honored. 48kHz stereo; the CLI writes WAV and converts to mp3 with ffmpeg when available. Wall-clock time ≈ the duration you ask for, because it streams in real time.

Best for video beds and background music when you don't want to host anything.

## Suno (handoff)

Suno has no public API. `--model suno` writes `<out>-style-prompt.txt` and `<out>-lyrics.txt` for pasting into https://suno.com/create (Custom mode) and warns when the style prompt is over Suno's 1000-character limit. Write those with the [`suno-prompt`](../../suno-prompt/) skill: it forces a POV pass first and keeps artist names out.

Suno stays the quality ceiling, and its Audio Influence and Personas have no exact local equivalent. Nearest local moves: ACE-Step `cover` at 0.7–0.9 for structure-faithful, 0.2–0.4 for vibe; `repaint` for section remixes.

## Iteration ladder

1. **Sketch** with ACE-Step text2music: seconds, cheap, many seeds.
2. **Anchor** to a real recording if there is one: ACE-Step `cover` or `--ref-audio`.
3. **Fix sections** with `repaint` instead of re-rolling.
4. **Final vocal render** on Music 3: carry the key, BPM, and arrangement language you learned into a long caption.
5. **Compare against Suno** on the same idea when quality is the point.
