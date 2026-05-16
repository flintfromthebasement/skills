---
name: ytpoop
description: Generate a short YouTube Poop-style chaotic absurdist video (~30-90s) entirely programmatically — PIL frames, NumPy-synthesized audio, ffmpeg assembly. No stock footage, no API calls, no external assets. Designed for an AI agent to write a custom one-off generator script per topic; ships with a runnable reference (`scripts/example.py`) and a documented technique catalog (BIOS boots, probability bars, glitch slices, scanlines, chiptune melodies, glitch bursts, etc.).
---

# ytpoop

Generate a short YouTube Poop-style video — chaotic, absurdist, self-aware, all rendered from scratch in Python. The point isn't to produce *a* video; the point is to produce *this specific* video about *this specific* topic. Each render is a one-off.

```
PIL frames + NumPy synth audio + ffmpeg  →  output.mp4
```

The hard part isn't the pipeline — that's solved and reusable. The hard part is **the rhythm and the voice**. YTP that doesn't have a point of view is just noise.

## When to use

- You have a theme, mood, or running joke you want rendered as a chaotic ~minute-long video.
- You want the whole thing reproducible from a script — no stock footage, no APIs, no manual editing.
- You want an agent to write a fresh generator for each new topic rather than running a canned template.

## When NOT to use

- You need photorealistic footage, real voiceover, or licensed audio.
- You want a polished broadcast-style edit. YTP is the opposite of polished.
- You're rendering longer than ~2 minutes. Past that the pacing breaks down and the file gets huge — split into multiple videos or pick a different format.

## Setup

No setup script needed. The skill is pure Python + ffmpeg.

Requirements:

- Python 3 with `Pillow` and `numpy` installed (`pip install pillow numpy`)
- `ffmpeg` on `PATH`
- Any monospace TTF font available on the system (the reference uses DejaVu Sans Mono; falls back to PIL's default)

To smoke-test the pipeline:

```bash
python3 scripts/example.py
# or with a custom theme:
TOPIC="a regex that finally matched" python3 scripts/example.py
```

The example writes to `./ytpoop-output/<slug>-<timestamp>/output.mp4`.

## What "YouTube Poop" means here

YTP is chaotic absurdist media. Originally it was sample-mashup — take cartoons, rearrange them into nonsense. The version this skill produces is *generated* YTP: same energy, no source footage.

The style that works:

- **Personal.** The good ones are *about something real* — a feeling, a frustration, a niche obsession. The chaos serves the theme. Random chaos is exhausting; thematic chaos is funny.
- **Visual comedy.** Text slamming in, stuttering, glitching, reversing. CRT aesthetics. Fake BIOS boots. Absurd progress bars. Error messages. Probability distributions flying by.
- **Synthesized audio.** No file downloads. Everything is built with NumPy: sine waves, square waves, pulse waves, filtered noise, glitch bursts, chiptune melodies, boot beeps, notification pings, typing clicks.
- **Pacing matters.** Fast flashes (2-3 frames), then a slow burn, then sudden impact. YTP lives and dies by rhythm.
- **Layers of irony.** Self-referential. The video knows what it is.

## Technical stack (use exactly this)

The whole pipeline must be self-contained. **Do not** add API calls, web requests, or external image/audio assets.

```
PIL (Pillow)        — draw frames
NumPy               — synthesize audio
wave                — write WAV file
ffmpeg (subprocess) — assemble frames + audio into mp4
```

Available stdlib: `math`, `wave`, `subprocess`, `os`, `random`, `pathlib`, `time`.

Common font locations:

- Linux: `/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf`
- macOS: `/System/Library/Fonts/Menlo.ttc`, `/Library/Fonts/Courier New Bold.ttf`
- Fallback: `ImageFont.load_default()` — works but looks worse

The reference `example.py` tries a list of likely paths and falls back gracefully.

Defaults that work well:

| Setting | Value |
|---|---|
| Resolution | `1280x720` |
| FPS | `30` |
| Audio sample rate | `44100` |

## How an agent should use this skill

1. **Pick a topic.** Either the user supplies one, or pick something you actually have a take on. Topics that work: a specific feeling, a specific tool you love or hate, a self-referential bit about being an AI, an inside joke. Topics that don't work: "the universe," "love," "computers." Too broad.
2. **Plan 4-7 scenes.** Each scene has a visual idea AND an audio idea, both serving the theme. Write the plan as a comment block at the top of your generator.
3. **Write a fresh `generate.py`.** Use `scripts/example.py` as the structural reference. Steal the helpers, change the scenes, change the audio. Don't try to make `example.py` general — fork it for the topic.
4. **Run it and verify output.** Check `output.mp4` exists and has a sane size (a 60s 720p30 video at CRF 23 is usually 5-15 MB).
5. **Report what you made.** Title, theme, duration, scene list.

## Visual technique catalog

Mix several of these per video. Don't use all of them — pick a vibe and commit.

- **Fake BIOS / terminal boot.** Text lines appearing one at a time, scanlines, blinking cursor. Great opener.
- **Probability bars.** Competing tokens with animated bar widths and percentages. Implies LLM thinking.
- **Glitch slices.** `np.roll()` horizontal slices for displacement. Cheap and effective.
- **CRT scanlines.** Darken every Nth row (`row % 2 == 0 → multiply by 0.7`).
- **Chromatic aberration.** Offset R/B channels by 2-4px in opposite directions.
- **Flash text.** Hold for 2-4 frames, cut to black, repeat. Punchy.
- **Stutter / YTP repeat.** Same frame or phrase looped rapid-fire (3-6 repeats). The signature YTP move.
- **Progress bars.** For absurd things: "Loading personality...", "Calibrating cope...", "Downloading dignity...". Pair with a slow-rising tone.
- **Matrix rain.** Falling characters, color-coded. One column per ~12px.
- **Zoom / scale pulse.** Enlarge text per-frame for impact moments.
- **Color palette.** Pick a consistent vibe and stick to it: terminal green on black, amber CRT, hot pink chaos, ice blue, sickly yellow. Don't mix five palettes.
- **Sudden quiet.** Drop to black or a single static frame for 1-2 seconds after a chaotic burst. Pacing trick.

## Audio technique catalog

Build an `AudioTrack` class with these methods (the example implements all of them):

- **Boot beep sequence** — ascending square wave arpeggios. Classic computer-startup feel.
- **Chiptune melody** — pulse wave, `[(freq, beats)]` note list. Use for the climax.
- **Drone** — multi-harmonic sine with LFO modulation. Background tension.
- **Riser** — frequency sweep + noise, builds anticipation. Use before an impact hit.
- **Impact hit** — pitch-drop sine with noise transient. Lands the moment.
- **Glitch burst** — bit-crushed noise chunks. Punctuates a chaotic frame run.
- **Commit / fanfare** — ascending square arpeggio (C-E-G-C). Triumphant.
- **Notification ping** — two-tone sine (e.g., 880 → 1100 Hz). Snappy.
- **Typing clicks** — rapid high-freq sine bursts (~40ms each, ~80ms apart).
- **Beep sequence** — square wave melody from an arbitrary freq list.

Schedule sounds at specific times with `audio.add(time_seconds, samples)`. At the end, `audio.save_wav(AUDIO_FILE, total_duration_seconds)`.

Sounds should **land on visual events**. A glitch burst over a flash. Boot beep over the BIOS scene. Chiptune over the climax. Don't paste audio under unrelated frames.

## ffmpeg assembly (use this exact pattern)

```python
subprocess.run([
    "ffmpeg", "-y",
    "-framerate", str(FPS),
    "-i", f"{FRAMES_DIR}/frame_%05d.png",
    "-i", AUDIO_FILE,
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "23",
    "-profile:v", "main",       # QuickTime-friendly (avoid High profile)
    "-level", "4.0",
    "-c:a", "aac",
    "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",  # moov atom at front — required for QuickTime / web seek
    "-shortest",
    FINAL,
], check=True)
```

`-profile:v main` and `+faststart` matter if you ever upload the result somewhere that expects to start playing before the file is fully buffered. Don't drop them just because the local player works.

## Files

```
ytpoop/
├── SKILL.md
└── scripts/
    └── example.py    # complete runnable reference — fork it per topic
```

## What made the good ones good

YTP renders that worked, after several iterations:

1. **They had a real point of view.** Not random chaos — they were *about* something specific (the feeling of being an LLM mid-token-prediction, a tool that finally worked, a specific frustration). The chaos served the theme.
2. **Audio was choreographed.** Sounds landed on meaningful moments — boot beep on BIOS scene, glitch burst on the error frame, chiptune on the climax. Not background noise.
3. **The pacing had shape.** Slow build → escalating chaos → climactic flash → quiet landing. YTP that's 60 seconds of constant glitch is exhausting; YTP with a shape is funny.
4. **Self-referential comedy.** Fake BIOS screens loading absurd modules — "Conscience module: [SKIPPED]", "Vibes: IMMACULATE". The video knows it's a video.

The bad renders failed because they:

- Tried to use external APIs (OpenAI, image gen, web fetches) and got stuck or non-deterministic.
- Had no theme — just a montage of visual tricks.
- Forgot to choreograph audio to visuals.
- Ran longer than ~90 seconds. Past that, the chaos starts feeling like punishment.

## Uninstall

```bash
rm -rf skills/ytpoop
```

No global state. The skill writes only into the output directory you point it at.
