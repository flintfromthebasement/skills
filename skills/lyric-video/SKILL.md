---
name: lyric-video
description: Combine an audio file, a video file, and lyrics into a subtitled music video. Accepts plain-text lyrics (the same format you paste into a Suno prompt) and auto-aligns them to the audio using whisper word timestamps; also accepts pre-timestamped LRC / TSV / JSON. Burns lyrics in as styled ASS subtitles with fade transitions, replaces the video's audio, and runs a two-pass encode (composite + faststart remux) so a crash in either step doesn't destroy the work.
---

# lyric-video

A minimal, reliable pipeline for turning a song + visual + lyrics into a finished music video.

```
audio.mp3  +  visual.mp4  +  lyrics.txt   →   final.mp4
```

Lyrics can be:

- **Plain text** — same format you'd paste into a Suno prompt. Section headers like `[Verse 1]`, `[Chorus]` are stripped. Each remaining line becomes one subtitle line. Timestamps are extracted automatically by running whisper on the audio and aligning whisper's word stream against the lyric sheet. (Whisper handles timing; the sheet stays canonical for spelling — whisper hallucinates on lyrics it half-hears.)
- **Timestamped** — `.lrc` / `.tsv` / `.json` are used as-is, no whisper run.

Subtitles are burned into the video as styled ASS with fade-in/out. The video's original audio is replaced by the supplied track. Output is H.264/AAC with `+faststart` so it streams immediately on YouTube/Vimeo/etc.

## When to use

- You have a song, some footage that covers the song's length, and lyrics — timestamped or not.
- You want a clean, repeatable build with no per-project ffmpeg incantations.
- You want the encode and the faststart remux split into two passes so one crash doesn't take down the whole render.

## When NOT to use

- Footage is shorter than the song. Loop, boomerang, or extend it first — this skill assumes the visual already covers the audio length.
- You want audio-reactive lights, glows, particle overlays, or other generative effects on top. That's a different skill (sister variant); this one is the plain subtitle-burn baseline.
- The audio doesn't actually contain the lyrics (instrumental, different language, mismatched track). Whisper will produce gibberish and alignment will fail.

## Setup

```bash
bash skills/lyric-video/scripts/setup.sh
```

Idempotent installer. It:

1. Verifies `ffmpeg`, `ffprobe`, and `python3` are on `PATH`.
2. Checks for `whisper` (used by plain-text lyric mode). Logs a warning if missing — doesn't fail. Timestamped lyric formats work without it.
3. Symlinks `make-lyric-video` into `~/.local/bin` (or whatever you choose).
4. Verifies the symlink wins on `PATH` and prints the fix line if not.
5. Writes an install receipt at `~/.config/lyric-video/.installed`. Re-runs are no-ops unless you pass `--force`.

See [CONVENTIONS.md](../../CONVENTIONS.md) for the repo-wide install pattern.

Flags:

- `--yes` — accept defaults, no prompts.
- `--force` — reinstall even if the receipt exists.

To enable plain-text lyric input, install whisper:

```bash
pip install -U openai-whisper
# or
pipx install openai-whisper
```

## Usage

Plain-text lyrics (auto-aligned via whisper):

```bash
make-lyric-video \
  --audio   song.mp3 \
  --video   footage.mp4 \
  --lyrics  lyrics.txt \
  --out     final.mp4
```

Pre-timestamped lyrics (no whisper):

```bash
make-lyric-video \
  --audio   song.mp3 \
  --video   footage.mp4 \
  --lyrics  lyrics.lrc \
  --out     final.mp4
```

That's the whole golden path. Output goes to `final.mp4`.

### Optional flags

| Flag | Default | Notes |
|---|---|---|
| `--font` | `Liberation Sans` | Font family. Anything libass can find on your system. |
| `--font-size` | `46` | In pixels at 1280×720 reference resolution. ASS scales it. |
| `--crf` | `18` | x264 quality. 18 is visually lossless-ish. Higher = smaller + worse. |
| `--preset` | `medium` | x264 speed/quality preset. `slow` for archival, `veryfast` for drafts. |
| `--ass` | `<out>.ass` (temp) | Path for the generated ASS file. |
| `--keep-ass` | off | Keep the ASS file next to the output instead of deleting it. |
| `--no-faststart` | off | Skip the faststart remux. Output won't begin playback until fully buffered. |
| `--whisper-model` | `small` | whisper model for plain-text alignment. `tiny`/`base`/`small`/`medium`/`large`. Bigger = slower + more accurate. |
| `--whisper-language` | auto | Language hint for whisper (e.g. `en`). Speeds up alignment + avoids language-detection mistakes. |
| `--save-aligned-lyrics` | off | After whisper alignment, save a `.tsv` of the resulting timestamps to this path. Re-use it next time instead of re-running whisper. |

## Lyric formats

Auto-detected by file extension and content. All times are seconds (or `mm:ss.xx` for LRC).

### Plain text — `.txt` (or anything not matching the formats below)

The same shape you'd paste into a Suno prompt. One subtitle line per non-empty source line. Section headers in `[brackets]` are stripped.

```
[Verse 1]
I got a wire in my chest, it hums after midnight
Neon in the sink, dirty shoes in the hall light

[Chorus]
Another bad night dressed up like freedom
Windows down, I do not need a reason
```

When this format is detected, the skill runs `whisper` on the audio with word-level timestamps, then aligns the lyric sheet against whisper's word stream:

- The lyric sheet is canonical for **spelling** — whisper hallucinates on mumbled or background-mixed lyrics, so we never use whisper's text.
- Whisper is canonical for **timing** — it knows where each word actually lands in the audio.
- Each lyric line gets the start time of its first matched whisper word and the end time of its last matched word. Lines that don't align (>0.4 token similarity) are dropped with a stderr note rather than shown at the wrong time.

Pass `--save-aligned-lyrics aligned.tsv` to capture the produced timestamps so you can iterate on visuals without re-running whisper.

### LRC — `.lrc`

Industry-standard timestamped lyrics. One timestamp per line; the end of each line is inferred from the start of the next (with a small gap to prevent overlap).

```
[ti:Song Title]
[ar:Artist]

[00:20.12]I got a wire in my chest, it hums after midnight
[00:24.28]Neon in the sink, dirty shoes in the hall light
[00:29.78]I said I was good, I practiced it all week
```

Metadata-only lines (`[ti:]`, `[ar:]`, `[al:]`, etc.) are skipped automatically.

### TSV — `.tsv` or `.tab`

Tab-separated. Most flexible — explicit start AND end per line.

```
20.12	22.62	I got a wire in my chest, it hums after midnight
24.28	29.73	Neon in the sink, dirty shoes in the hall light
29.78	33.37	I said I was good, I practiced it all week
```

### JSON — `.json`

```json
[
  {"start": 20.12, "end": 22.62, "text": "I got a wire in my chest, it hums after midnight"},
  {"start": 24.28, "end": 29.73, "text": "Neon in the sink, dirty shoes in the hall light"}
]
```

A plain-text example ships in `examples/sample.txt` and a timestamped example in `examples/sample.lrc` for smoke-testing.

## How it works

```
┌── parse lyrics ──┐
│  detect format   │
└─┬───────────────┬┘
  │               │
  │ timed         │ plain text
  │               ▼
  │       ┌── run whisper ─────────┐
  │       │ word-level timestamps  │
  │       └────────┬───────────────┘
  │                ▼
  │       ┌── align lines → words ──────────────┐
  │       │ greedy fuzzy match, ratio ≥ 0.4     │
  │       │ drop lines that don't align cleanly │
  │       └────────┬────────────────────────────┘
  ▼                ▼
  (start, end, text) tuples
         │
         ▼
┌── tighten + ASS ──┐    avoid overlap, add fade(220, 220)
│  build .ass file  │
└────────┬─────────┘
         ▼
┌── pass 1: composite ──────────────────────────┐
│  ffmpeg -i video -i audio                     │
│         -vf "ass=<path>"                      │
│         -map 0:v(filtered) -map 1:a           │
│         -c:v libx264 -crf 18 -c:a aac         │
│         -shortest  out.tmp.mp4                │
└────────┬──────────────────────────────────────┘
         ▼
┌── pass 2: faststart ──────────────────────────┐
│  ffmpeg -i out.tmp.mp4                        │
│         -c copy -movflags +faststart out.mp4  │
└────────┬──────────────────────────────────────┘
         ▼
      out.mp4
```

The two-pass split is on purpose. The `+faststart` step relocates the `moov` atom from the end of the file to the front, which means rewriting the entire MP4. If that step crashes (we have seen NVIDIA driver lockups midway through), pass 1's output is still a complete, playable file you can remux later. Combining `-movflags +faststart` into the encode pass means a crash there leaves you with a corrupt MP4 missing its `moov` atom and no easy way to recover.

## What's NOT included

- **No video extension.** Length-mismatched inputs use `-shortest` and silently truncate. If your song is 4:00 and your footage is 2:30, fix that upstream.
- **No audio-reactive overlays.** No lights, no glows, no particles. This is the plain-subtitle baseline. Sister skills can layer effects.
- **No styling beyond defaults.** The ASS style is a single sane preset (Liberation Sans, light text, soft shadow, bottom-center). Hand-edit the generated `.ass` (with `--keep-ass`) for one-off restyling, or fork the script for a different default.
- **No fancier alignment.** Plain-text mode uses whisper word-timestamps + a greedy fuzzy match. Good enough for clean studio vocals; can struggle on heavy mixing, ad-libs, or rapid delivery. If a line drops out of the alignment, fix it by feeding the file in as TSV with hand-corrected timing.

## Files

```
lyric-video/
├── SKILL.md
├── scripts/
│   ├── setup.sh               # idempotent installer
│   └── make-lyric-video.py    # parse → (whisper align if plain) → ASS → 2-pass ffmpeg
└── examples/
    ├── sample.lrc             # timestamped example
    └── sample.txt             # plain-text example (Suno-style)
```

## Uninstall

```bash
rm ~/.local/bin/make-lyric-video
rm -rf ~/.config/lyric-video
```

## Troubleshooting

**"font not found"** — libass falls back automatically, but the output will look wrong. Install the font (`sudo apt install fonts-liberation` on Debian/Ubuntu) or pass `--font` with one you have.

**Lyrics drift / wrong line on screen** — your timestamps are off. The skill prints what it parsed; cross-check against the audio. Common causes: LRC offsets in the source file, frame-rate confusion (timestamps are in seconds, not frames), or a whisper alignment that mismatched on a noisy section. Try a bigger whisper model (`--whisper-model medium` or `large`) and pass `--whisper-language en` to skip auto-detection.

**Plain-text lyrics: too many lines dropped** — whisper isn't recognizing the words. Try `--whisper-model medium` or `large` for better accuracy, set `--whisper-language` explicitly, or fall back to writing a TSV by hand. The dropped-line stderr output tells you which lines failed; you can fix just those in a TSV and re-run.

**Plain-text alignment is slow** — whisper is the bottleneck, not the encode. The `small` default takes a few minutes on a 4-minute song on CPU; `medium`/`large` are slower. Run once with `--save-aligned-lyrics aligned.tsv` and re-feed that TSV on subsequent renders to skip the whisper step entirely.

**Output doesn't start playing immediately on a CDN** — confirm `+faststart` actually ran. `ffprobe -show_format <file>` should show `iso5avc1mp42` brand and you should see `moov` near the start of the file (`xxd <file> | head -50`).

**"could not open" on YouTube** — usually a missing `moov` atom from a killed faststart pass. Re-run with `--no-faststart` to confirm pass 1 worked, then run the faststart remux manually:

```bash
ffmpeg -i out.tmp.mp4 -c copy -movflags +faststart out.mp4
```
