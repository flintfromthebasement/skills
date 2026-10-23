---
name: generate-music
description: "Generate songs and instrumentals with open and hosted music models (ACE-Step 1.5, MiniMax Music 3, HeartMuLa, Google Lyria RealTime) or hand off to Suno. One CLI, backends you point at your own GPU, Modal, or an HTTP gateway via env vars. Includes which model to use for what (speed vs vocals vs length), per-model prompting, reference-audio covers/repaints, and latency notes. Use when the user wants an actual audio file, not just lyrics."
---

# Generate Music

Turn a caption (and usually lyrics) into an mp3. The CLI picks a model and a backend, submits, polls, downloads, and prints `OUTPUT_FILE=<path>`.

```bash
python3 scripts/generate-music.py --check        # what's configured / reachable

# Fast instrumental sketch on a local ACE-Step server
python3 scripts/generate-music.py --model acestep --instrumental --seconds 60 \
  --prompt "warm lo-fi hip-hop, dusty Rhodes, vinyl crackle, boom-bap drums, upright bass" --bpm 85

# Full vocal song on MiniMax Music 3
python3 scripts/generate-music.py --model music3 --seconds 180 \
  --prompt-file caption.txt --lyrics-file lyrics.txt

# Suno: write paste-ready files, nothing generated
python3 scripts/generate-music.py --model suno --prompt-file style.txt --lyrics-file lyrics.txt
```

No backend is baked in. You run the model somewhere (your GPU, your Modal account, your own HTTP service) and tell the CLI where with env vars. Setup for each path: [`references/backends.md`](references/backends.md).

**Related skills.** [`write-lyrics`](../write-lyrics/) for the words, [`suno-prompt`](../suno-prompt/) for Suno style prompts (and a good POV pass before any model), [`audio-analysis`](../audio-analysis/) to listen to what came back, [`lyric-video`](../lyric-video/) to put it on screen.

## Pick a model

| Model | Use it for | Vocals | Length | Speed | Runs on |
|---|---|---|---|---|---|
| **ACE-Step 1.5** | Fast sketches, instrumentals, beds, **anything with reference audio** (cover, style transfer, repaint a section) | Yes, decent; not the best singer | 10–600s | Seconds per song on a datacenter GPU; under 10s on a 3090 (upstream figure) | Your GPU (<4GB VRAM for the 2B turbo), Mac, ROCm, or Modal |
| **MiniMax Music 3** | The finished vocal song: best singing and lyric adherence of the open models in our tests, long-form structure | Best | 5–300s (cap; may end early) | Slow. Autoregressive at 25 frames/s; minutes per song on an L40S, ~35 min for 4 min on a big AMD iGPU | ~23GB VRAM (bf16). Modal L40S or a 24GB+ card |
| **HeartMuLa 3B** | Second vocal option when Music 3 is unavailable or you want a different voice | Yes | up to 240s | Minutes | 24GB-class GPU (we run it on an L40S) or Modal |
| **Lyria RealTime** (Google) | Instrumental beds and background music with zero GPU setup; the only true streaming model here | No | any (streams in real time) | Wall-clock ≈ duration | Gemini API key |
| **Suno** (handoff) | Quality ceiling, Personas, Audio Influence | Best overall | ~4 min | n/a | suno.com, no public API |

**Rules of thumb.**

- Iterating on an idea? ACE-Step. Ten takes in the time Music 3 does one.
- The words matter and someone will sing along? Music 3, or Suno.
- You have a riff, a demo, or a song to restyle? ACE-Step with `--src-audio` / `--ref-audio`. Music 3 can't hear audio (except the sound-transfer hack in `modal/music3_app.py`, which copies timbre, not composition).
- Solo instrument piece? ACE-Step with the riff as reference audio at strength 0.2. Music 3 adds a band or a singer no matter what the caption says.
- Background music for a video, no GPU? Lyria.
- Offline on a laptop with no GPU at all? ACE-Step's 2B turbo with CPU offload, or Meta's `facebook/musicgen-small` (≤30s clips, CC-BY-NC weights, not wrapped here).

Details, prompting per model, and the reference-audio recipes: [`references/models.md`](references/models.md).

## Workflow

1. **Get the words right first.** If the user wants a song and has no lyrics, run `write-lyrics` (or at least write one verse and a chorus). Section tags go on **their own line**: `[Verse]` then the words. The CLI fixes `[Verse] words` automatically, but write it right.
2. **Pick the model** from the table. Default to ACE-Step for a first pass unless they asked for a finished vocal.
3. **Write the caption for that model.** Each model wants a different shape:
   - ACE-Step: short prose, under 512 chars. Pass BPM/key/time signature as flags (`--bpm 96 --key "E minor"`), not prose.
   - Music 3: long structured caption, 250–600 words, producer vocabulary, always name the vocal gender and timbre.
   - HeartMuLa: comma-separated tags (`acoustic,folk,female vocal,warm,96 bpm`).
   - Lyria: one mood/instrumentation sentence; `--bpm` is honored.
   - Suno: the `suno-prompt` skill's style prompt, under 1000 chars, no artist names.
4. **Audition short.** 30s for a sketch, 60s default. Go to 180–300s only when the take is worth it.
5. **Keep the seed.** Same inputs + seed + length = same audio on ACE-Step and Music 3. Change only the seed for another take.
6. **Listen before you report.** Run `audio-analysis` on the result, or at least check `ffprobe` duration. A 4-second file usually means tags on the same line as lyrics or a too-short instrumental sheet.
7. **Report** the path, model, seed, seconds, and backend. Credit MiniMax-Music3 by name when you share Music 3 output (license requires it on commercial UIs).

## CLI reference

```
--model acestep|music3|heartmula|lyria|suno   (default $MUSICGEN_MODEL or acestep)
--backend auto|api|modal|gateway|gemini|handoff
--prompt / --prompt-file        caption or style prompt
--lyrics / --lyrics-file        section tags on their own lines
--instrumental                  no vocals
--seconds N                     duration cap (model default if omitted)
--seed N                        reproducible takes
--out path.mp3                  default $MUSICGEN_OUT_DIR (./music-output)/<model>-<slug>-<ts>.mp3

ACE-Step only:
--task text2music|cover|repaint|lego|extract|complete
--src-audio FILE                source track for cover / repaint / lego / extract / complete
--ref-audio FILE                style reference (also Music 3 sound transfer on Modal/gateway)
--strength 0-1                  audio_cover_strength (0.2 = loose style transfer; 1.0 = hug the source)
--repaint-start S --repaint-end S
--bpm --key --time-signature --language --steps --thinking --dit-model

--dry-run                       print the resolved backend + request, send nothing
--check                         show configured backends
```

Exit 0 and a `OUTPUT_FILE=` line mean the file exists. `--model suno` prints one `OUTPUT_FILE=` per text file it wrote.

## Latency, streaming, and long songs

Short version (full notes in [`references/latency.md`](references/latency.md)):

- **ACE-Step is diffusion: no token streaming.** The whole clip is denoised in parallel and arrives at once. "Time to first audio" is the full generation time. Lyria is the only model here that streams.
- **Chunking for faster first audio needs seam handling.** Generate chunk 2 conditioned on chunk 1's tail (ACE-Step `repaint` over a source that holds the tail, or tail-latent pinning like Music 3's own chunk-overlap does). Independent chunks stitched with a crossfade drift in key, tempo, and timbre at every seam.
- **Profile before cutting steps.** Time the stages (text/LM encode, DiT denoise, VAE decode) before lowering `--steps`. The turbo model already runs 8 steps; the LM planning pass and the VAE decode can be the bigger share. Upstream's `profile_inference.py` and the `time_costs` the Modal app prints give the breakdown.

## Errors

| Symptom | Fix |
|---|---|
| `no backend configured for …` | Run `--check`; set `ACESTEP_API_URL`, `MUSICGEN_GATEWAY_URL`, or install `modal` and deploy `modal/` (see backends.md) |
| ACE-Step "not reachable" but something runs on 8001 | Port clash. AutoMem and other services also default to 8001; start ACE-Step with `ACESTEP_API_PORT=8011` and set `ACESTEP_API_URL` to match |
| Few-second file | Tags on the same line as lyrics, or a Music 3 instrumental sheet with too few sections |
| Instrumental when you wanted vocals | Name the vocal gender + timbre in the caption (Music 3); pass lyrics (ACE-Step covers render instrumental without them) |
| Music 3 thin "demo" sound | Name 4+ instruments that stay in through the verses; avoid "raw", "simple", "stripped" |
| Modal first call takes minutes | Cold start loading weights (Music 3 ~20GB). Later calls in the scaledown window are fast |
| Lyria `ExperimentalWarning` | Expected; the realtime music API is still experimental |

## Uninstall

Nothing is installed outside the skill folder. Delete generated audio from `$MUSICGEN_OUT_DIR` (default `./music-output`). If you deployed the Modal apps: `modal app stop acestep` (and `minimax-music3`, `heartmula`, `musicgen-gateway`), then `modal volume delete <name>-weights` to drop cached weights.
