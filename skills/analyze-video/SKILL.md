---
name: analyze-video
description: Analyze local video files or YouTube videos with a multimodal model — visual/frame/UI/slide inspection, production critique, timestamped scene breakdowns, and full multimodal summaries beyond what a transcript can give. Gemini recommended (watches the actual video natively); OpenAI vision fallback via frame sampling + Whisper transcript.
---

# Analyze Video

Watch a video with a multimodal model and report what's actually *shown*, not just what's said: frames, screen contents, slides, UI, movement, visual storytelling, production details. `yt-dlp` handles YouTube URLs (lightweight 480p download); `ffprobe` pulls metadata.

If the user only needs "what does this video say," a plain transcript is cheaper — use this skill when the visuals matter.

## Quick start

```bash
# Multimodal summary of a YouTube video
node scripts/run.mjs --url "https://www.youtube.com/watch?v=VIDEO_ID"

# What's on screen? (frames, slides, UI, screen text)
node scripts/run.mjs --url "https://www.youtube.com/watch?v=VIDEO_ID" --mode visual --prompt "What is shown on screen during the demo?"

# Production/style critique of a local file
node scripts/run.mjs --file demo.mp4 --mode production
```

Output goes to `./video-analysis-output/<timestamp>/` (override with `--out`):

- `summary.md` — the analysis plus video metadata
- `manifest.json` — everything, machine-readable (`--json` prints it to stdout instead)

## Providers & models

**Gemini is the recommended provider** — it's the only major API that ingests video natively (frames *and* audio together, uploads up to 2GB via the Files API), and Google's models are currently the strongest at video understanding. Set `GEMINI_API_KEY` (free at https://aistudio.google.com/apikey). Default model: `gemini-2.5-pro`; `--model gemini-2.5-flash` is faster/cheaper for casual summaries.

**Fallback: OpenAI** (`--provider openai`) approximates video understanding: the runner samples up to `--max-frames` timestamped frames with `ffmpeg` (default 20, max 50), transcribes the audio track via the transcription API, and sends both to a vision model (default `gpt-5.5`). This is genuinely useful for slides, UI, and scene-level questions, but it cannot see motion or anything between samples — the prompt tells the model to treat gaps as unobserved. Prefer Gemini for anything where continuous visuals matter.

Provider selection: `--provider auto` (default) prefers Gemini when a key is present, then falls back to OpenAI with a notice. Keys are read from the environment or `~/.env`.

The same frame-sampling trick works for any vision-capable model (Claude, open-weight VLMs): if you're an agent with vision but no Gemini/OpenAI key, you can extract frames yourself with the same ffmpeg pattern the runner uses and read them directly.

## Modes

- `--mode summary` (default): concise multimodal summary with the most important visual details.
- `--mode visual`: frame-level evidence — what is visibly shown, timeline of visible events, stated uncertainty.
- `--mode production`: editing, pacing, camera, lighting, graphics, sound, structure, style.
- `--mode deep`: full multimodal audit — timestamped chapters, takeaways, production DNA.

Use `--prompt` for the user's exact question or emphasis:

```bash
--prompt "Is this UI confusing? Focus on visible workflow problems."
--prompt "What visual jokes or gags are in this?"
--prompt "Give me production notes for making something similar."
```

## Options

- `--file <path>` or `--url <youtube-url-or-id>` (one, not both)
- `--mode summary|visual|production|deep`
- `--prompt <text>` — specific question or focus
- `--provider auto|gemini|openai` (default `auto`)
- `--model <model>` — override the provider's default model
- `--max-frames <n>` — OpenAI fallback frame budget, 1–50 (default 20)
- `--out <dir>` — output directory
- `--json` — print the manifest JSON to stdout

## Requirements

- Node 18+ (uses built-in `fetch`; no npm dependencies)
- `GEMINI_API_KEY` (recommended) or `OPENAI_API_KEY`, in the environment or `~/.env`
- `yt-dlp` on PATH — only for `--url`
- `ffprobe` on PATH — metadata; `ffmpeg` required for the OpenAI fallback (frame + audio extraction)

## Notes for agents

- If the user references an attached file, resolve it to a real saved path first. The runner rejects placeholder values like "attached video" or "this video" — never substitute an unrelated local file.
- Long videos: Gemini handles roughly 45–60 minutes per request comfortably at the 480p download this skill uses; for multi-hour videos, trim or analyze in segments.
- Uploaded Gemini files are deleted from Google's servers after analysis; YouTube temp downloads are cleaned up.
