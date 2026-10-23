# Latency, streaming, and long songs

For when "make it faster" or "can it stream?" comes up.

## How each model spends its time

| Model | Architecture | Streams? | Where the time goes |
|---|---|---|---|
| ACE-Step 1.5 | Optional 5Hz LM planner → DiT diffusion over the whole clip → VAE decode | **No** | LM planning (when `--thinking` or metadata auto-fill runs), DiT denoise steps, VAE decode. All of it happens before any audio exists |
| MiniMax Music 3 | Autoregressive composer at 25 frames/s → flow-matching renderer in chunks → vocoder | Not as shipped | The AR composer dominates, so runtime scales with song length |
| HeartMuLa | Autoregressive LM → codec decode | Not as shipped | Token generation |
| Lyria RealTime | Hosted streaming model | **Yes** | Real time: a 60s bed takes ~60s, and audio arrives as it plays |

## ACE-Step is diffusion, so there is no token streaming

A diffusion model denoises the whole latent at once. Step 1 of 8 is noise across all 60 seconds; the first playable sample appears when the last step and the VAE decode finish. There's no "first token" to send early. Time to first audio = total generation time.

On a fast GPU that total is small (upstream reports under 2s per song on an A100 and under 10s on a 3090), so for most uses the honest answer is "just generate the whole thing." The time you see over a network is usually cold start, queueing, and upload/download, not the model.

## Chunked generation needs seam handling

The tempting fix for first-audio latency is "generate 10-second chunks and play chunk 1 while chunk 2 renders." Generated independently, every chunk boundary is a seam: key, tempo, groove, timbre, and mix level drift, and a crossfade only blurs the jump.

Condition each chunk on the end of the previous one:

- **Tail-latent conditioning.** Pin the overlap region of chunk N+1 to chunk N's final latents along the noise→clean path at every step, so the model continues from them rather than inventing a new start. Music 3's renderer does exactly this internally (chunk-overlap pinning in its denoise loop; see `_install_ref_audio_patch` in `modal/music3_app.py`, which reuses the same mechanism for reference audio). For ACE-Step this means patching the DiT loop yourself.
- **Repaint as the no-code version (ACE-Step).** Build a source clip holding the last few seconds of chunk N followed by silence to the new length, then run `--task repaint --src-audio that.wav --repaint-start <tail length>`. The model keeps the tail and paints forward from it. Crossfade over the kept tail when you stitch. This is a recipe, not something we've benchmarked; listen at every seam.
- Expect each conditioned chunk to cost about what a full-length generation of that chunk costs, so total time goes up. You're trading throughput for earlier first audio.

If you need sound immediately and don't need vocals, use Lyria.

## Profile before cutting steps

Lowering diffusion steps is the obvious knob and often the wrong one. Measure the stages first:

1. **Encode**: text/lyric encoders and, if enabled, the 5Hz LM planning pass (`--thinking`, or metadata auto-fill when BPM/key/duration are blank).
2. **Denoise**: DiT steps. Turbo models already default to 8.
3. **Decode**: VAE decode to waveform, plus mp3 encoding.

Tools:

- Upstream `profile_inference.py` in the ACE-Step repo: `python profile_inference.py` for one run with a per-stage breakdown, `--mode benchmark` for a config matrix, `--mode tier-test` to simulate smaller GPUs.
- `modal/acestep_app.py` prints the pipeline's `time_costs` dict for every generation; check the Modal logs.

Usual findings: if the LM pass dominates, pass `--bpm`, `--key`, `--seconds` explicitly and skip `--thinking`; if VAE decode dominates on long clips, shorter auditions help more than fewer steps; if denoise dominates on a small GPU, try a turbo DiT or CPU offload settings before cutting steps below the turbo default of 8, and A/B by ear when you do.

## Music 3 specifics

- Runtime is roughly proportional to `--seconds` because the composer is autoregressive. Audition at 30s.
- Cold start on Modal loads ~20GB of weights. Keep calls inside the scaledown window when iterating.
- The composer could, in principle, feed a streaming renderer chunk by chunk (it already renders in overlapped chunks), but the diffusers pipeline returns audio only at the end.
