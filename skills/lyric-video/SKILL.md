---
name: lyric-video
description: Combine an audio file, a video file, and timestamped lyrics into a subtitled music video. Bakes the lyrics into the picture as ASS subtitles with fade transitions, replaces the video's audio with the supplied track, and runs a two-pass encode (composite, then faststart remux) so a crash in either step doesn't destroy the work. Accepts LRC, TSV, or JSON lyric formats.
---

# lyric-video

A minimal, reliable pipeline for turning a song + visual + timestamped lyrics into a finished music video.

```
audio.mp3  +  visual.mp4  +  lyrics.lrc   →   final.mp4
```

The lyrics are burned into the video as styled subtitles (ASS with fade-in/out). The video's original audio is replaced by the supplied audio track. Output is H.264/AAC with `+faststart` so it streams immediately on YouTube/Vimeo/etc.

## When to use

- You have a song, some footage that runs for the song's length, and lyrics with timestamps.
- You want a clean, repeatable build with no per-project ffmpeg incantations.
- You want the encode and the faststart remux split into two passes so one crash doesn't take down the whole render.

## When NOT to use

- Footage is shorter than the song. Loop, boomerang, or extend it first — this skill assumes the visual already covers the audio length.
- You want audio-reactive lights, glows, particle overlays, or other generative effects on top. That's a different skill (sister variant); this one is the plain subtitle-burn baseline.
- Your "lyrics" don't have timestamps yet. Run an alignment step first (e.g. whisper word-timestamps + fuzzy match against the lyric sheet) and feed the resulting timestamps in.

## Setup

```bash
bash skills/lyric-video/scripts/setup.sh
```

Idempotent installer. It:

1. Verifies `ffmpeg`, `ffprobe`, and `python3` are on `PATH`.
2. Symlinks `make-lyric-video` into `~/.local/bin` (or whatever you choose).
3. Verifies the symlink wins on `PATH` and prints the fix line if not.
4. Writes an install receipt at `~/.config/lyric-video/.installed`. Re-runs are no-ops unless you pass `--force`.

See [CONVENTIONS.md](../../CONVENTIONS.md) for the repo-wide install pattern.

Flags:

- `--yes` — accept defaults, no prompts.
- `--force` — reinstall even if the receipt exists.

## Usage

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

## Lyric formats

Auto-detected by file extension and content. All times are seconds (or `mm:ss.xx` for LRC).

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

A small example LRC ships in `examples/sample.lrc` for smoke-testing.

## How it works

```
┌── parse lyrics ──┐
│  LRC/TSV/JSON   │
└────────┬────────┘
         │  (start, end, text) tuples
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
- **No alignment.** Lyrics arrive timestamped. If you have plain lyrics, align them first (e.g. with `whisper` + a fuzzy match against the sheet) and write out a TSV.
- **No styling beyond defaults.** The ASS style is a single sane preset (Liberation Sans, light text, soft shadow, bottom-center). Hand-edit the generated `.ass` (with `--keep-ass`) for one-off restyling, or fork the script for a different default.

## Files

```
lyric-video/
├── SKILL.md
├── scripts/
│   ├── setup.sh               # idempotent installer
│   └── make-lyric-video.py    # the actual builder
└── examples/
    └── sample.lrc             # tiny example for smoke tests
```

## Uninstall

```bash
rm ~/.local/bin/make-lyric-video
rm -rf ~/.config/lyric-video
```

## Troubleshooting

**"font not found"** — libass falls back automatically, but the output will look wrong. Install the font (`sudo apt install fonts-liberation` on Debian/Ubuntu) or pass `--font` with one you have.

**Lyrics drift / wrong line on screen** — your timestamps are off. The skill prints what it parsed; cross-check against the audio. Common causes: LRC offsets in the source file, frame-rate confusion (timestamps are in seconds, not frames), or whisper hallucinations bleeding into the alignment.

**Output doesn't start playing immediately on a CDN** — confirm `+faststart` actually ran. `ffprobe -show_format <file>` should show `iso5avc1mp42` brand and you should see `moov` near the start of the file (`xxd <file> | head -50`).

**"could not open" on YouTube** — usually a missing `moov` atom from a killed faststart pass. Re-run with `--no-faststart` to confirm pass 1 worked, then run the faststart remux manually:

```bash
ffmpeg -i out.tmp.mp4 -c copy -movflags +faststart out.mp4
```
