---
name: audio-analysis
description: Analyze audio files or YouTube audio with a multimodal model — music/vibe/production feedback, comparing tracks, identifying mystery sounds, answering questions like "what key is this in?", and extracting Suno-ready style prompts from reference songs. Gemini recommended; OpenAI audio models as fallback. Also renders waveform/spectrogram artifacts locally with ffmpeg.
---

# Audio Analysis

Actually *listen* to audio and produce practical analysis. The runner sends the audio to a multimodal model, renders waveform and spectrogram PNGs with `ffmpeg`, pulls metadata with `ffprobe`, and can extract audio from YouTube with `yt-dlp`.

## Quick start

```bash
# General analysis
node scripts/run.mjs --file /path/to/song.mp3

# Ask a specific question of the audio
node scripts/run.mjs --file /path/to/sound.wav --prompt "What animal is this?"

# Extract production details and a Suno style prompt from a reference track
node scripts/run.mjs --url "https://www.youtube.com/watch?v=VIDEO_ID" --mode suno

# Compare versions of a track
node scripts/run.mjs --file v1.mp3 --file v2.mp3 --compare
```

Output goes to `./audio-analysis-output/<timestamp>/` (override with `--out`):

- `summary.md` — the analysis plus file metadata
- `manifest.json` — everything, machine-readable (`--json` prints it to stdout instead)
- `<file>.waveform.png` and `<file>.spectrogram.png` (skip with `--no-visuals`)

## Providers & models

**Gemini is the recommended provider** — Google's models are currently the strongest at native audio understanding, the Files API takes uploads up to 2GB, and long recordings work without chunking. Set `GEMINI_API_KEY` (get one free at https://aistudio.google.com/apikey). Default model: `gemini-2.5-flash`; use `--model gemini-2.5-pro` for harder listening tasks.

**Fallback: OpenAI** (`--provider openai`) uses audio-input chat completions (default model `gpt-audio-1.5`; `gpt-audio` also accepts audio input). Caveats vs Gemini: audio is sent inline as base64 (~20MB practical cap, so long recordings need Gemini or pre-trimming), non-wav/mp3 files are transcoded to mp3 first (needs `ffmpeg`), and `gpt-audio-1.5` intermittently wraps its answer in JSON — the runner detects this, retries, and salvages the prose, but expect occasional weaker output than Gemini.

Provider selection: `--provider auto` (default) prefers Gemini when a key is present, then falls back to OpenAI with a notice. Keys are read from the environment or `~/.env`.

Other providers (Anthropic Claude, most open-weight chat models) can't ingest raw audio as of mid-2026 — for those, the honest fallback is transcription (Whisper via the OpenAI path) plus the spectrogram/waveform images this skill already renders, but you lose actual musical listening. Don't pretend a transcript is an audio analysis.

## Modes

- `--mode general` (default): songs, recordings, mystery sounds, mix feedback, structure, vibe.
- `--mode suno`: production-focused breakdown plus a ready-to-use Suno style prompt under 1000 characters, with no artist/band/song names.

Use `--prompt` for the user's exact question or emphasis:

```bash
--prompt "What key is this in?"
--prompt "What genre tags would recreate this?"
--prompt "Is this a dog, coyote, or fox?"
--prompt "Focus on drum production and mix balance."
```

## Options

- `--file <path>` — local audio file; repeat for multiple files
- `--url <youtube-url-or-id>` — extract audio via `yt-dlp`; repeat for multiple
- `--mode general|suno`
- `--prompt <text>` — specific question or focus
- `--compare` — comparison output (implied when multiple inputs are given)
- `--transcribe` — also include a best-effort transcript/lyrics
- `--provider auto|gemini|openai` (default `auto`)
- `--model <model>` — override the provider's default model
- `--out <dir>` — output directory
- `--no-visuals` — skip waveform/spectrogram rendering
- `--json` — print the manifest JSON to stdout

## Requirements

- Node 18+ (uses built-in `fetch`; no npm dependencies)
- `GEMINI_API_KEY` (recommended) or `OPENAI_API_KEY`, in the environment or `~/.env`
- `ffmpeg` + `ffprobe` on PATH — metadata, visual artifacts, and OpenAI transcoding
- `yt-dlp` on PATH — only for `--url`

## Notes for agents

- If the user references an attached file, resolve it to a real saved path first. The runner rejects placeholder values like "attached mp3" or "this audio" — never substitute an unrelated local file.
- Keep the user-facing summary tight. In suno mode, surface the generated style prompt clearly. In comparison mode, explain tradeoffs and don't pick a winner unless asked.
- Uploaded Gemini files are deleted from Google's servers after analysis; YouTube temp downloads are cleaned up.
