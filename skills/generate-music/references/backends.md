# Backends: point the CLI at your own deployment

The CLI never ships with an endpoint. Pick one or more of these, set the env vars, and run `python3 scripts/generate-music.py --check`.

There is no `scripts/setup.sh`: the CLI is stdlib-only for the `api`, `gateway`, and `handoff` backends. The optional backends each need one install, listed in the table below (`pip install modal` + `modal token new`, or `pip install google-genai`).

| Backend | Models | You need |
|---|---|---|
| `api` | acestep | ACE-Step 1.5's own REST server, on your machine or anywhere you can reach |
| `modal` | acestep, music3, heartmula | A [Modal](https://modal.com) account, `pip install modal`, the apps in `../modal/` deployed |
| `gateway` | acestep, music3, heartmula | Any HTTP service speaking the submit_song / poll_song protocol (`../modal/gateway_app.py` is one) |
| `gemini` | lyria | `pip install google-genai`, `GEMINI_API_KEY` |
| `handoff` | suno | nothing |

`--backend auto` (the default) picks, per model: `MUSICGEN_<MODEL>_BACKEND` if set → for ACE-Step, `api` when `ACESTEP_API_URL` is set or an ACE-Step server answers on the default URL → `gateway` when configured → `modal` when the package is installed.

## Environment variables

| Variable | Default | Used by |
|---|---|---|
| `MUSICGEN_MODEL` | `acestep` | default `--model` |
| `MUSICGEN_OUT_DIR` | `./music-output` | where auto-named files go |
| `MUSICGEN_TIMEOUT` | `1800` | seconds to wait for a job |
| `MUSICGEN_<MODEL>_BACKEND` | (auto) | force a backend per model, e.g. `MUSICGEN_MUSIC3_BACKEND=gateway` |
| `ACESTEP_API_URL` | `http://127.0.0.1:8001` | `api` backend base URL |
| `ACESTEP_API_KEY` | (none) | sent as `Authorization: Bearer` when the server has a key |
| `MUSICGEN_MODAL_ACESTEP` | `acestep:AceStep` | Modal `app:Class` for each model; change if you deployed under other names |
| `MUSICGEN_MODAL_MUSIC3` | `minimax-music3:MiniMaxMusic3` | |
| `MUSICGEN_MODAL_HEARTMULA` | `heartmula:HeartMuLa` | |
| `MODAL_ENVIRONMENT` | (default env) | Modal environment to look apps up in |
| `MUSICGEN_GATEWAY_URL` | (none) | gateway base URL; the CLI appends `/submit_song` and `/poll_song` |
| `MUSICGEN_GATEWAY_SUBMIT_URL`, `MUSICGEN_GATEWAY_POLL_URL` | (derived) | for gateways where each endpoint has its own URL |
| `MUSICGEN_GATEWAY_TOKEN` | (none) | sent in the body as `token` and as a Bearer header |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | (none) | Lyria |
| `LYRIA_MODEL` | `models/lyria-realtime-exp` | Lyria model id |

Keep keys in your shell profile or a secrets manager, never in this folder.

## Local ACE-Step (your own GPU)

ACE-Step 1.5 runs on modest hardware: the 2B turbo model fits in under 4GB VRAM with offload, and works on CUDA, Apple Silicon (MPS), ROCm, and Intel XPU. Upstream's VRAM table: ≤6GB → 2B turbo, no LM; 8–16GB → 2B turbo + 0.6B/1.7B LM; 20GB+ → XL turbo/sft.

```bash
git clone https://github.com/ace-step/ACE-Step-1.5.git && cd ACE-Step-1.5
uv sync                           # see upstream docs/en/INSTALL.md for ROCm / Mac / XPU variants
ACESTEP_API_PORT=8011 uv run acestep-api     # first run downloads weights
```

Then:

```bash
export ACESTEP_API_URL=http://127.0.0.1:8011
python3 scripts/generate-music.py --check
python3 scripts/generate-music.py --model acestep --prompt "surf rock, reverb-drenched guitar, driving drums" --instrumental --seconds 30
```

**Port clash.** Upstream defaults to port 8001, which is also the default for AutoMem and other local services. The CLI's health probe only accepts a server that identifies as ACE-Step, so a clash shows up as "no ACE-Step server" rather than a confusing failure. Pick another port as above.

**Remote box.** Same server on a GPU machine on your LAN or tailnet: start it with `ACESTEP_API_HOST=0.0.0.0` and an `ACESTEP_API_KEY`, then set `ACESTEP_API_URL=http://<host>:<port>` and `ACESTEP_API_KEY` on the client. Don't expose it to the public internet without the key.

**Plain `http://` sends the key in the clear.** The same goes for `MUSICGEN_GATEWAY_TOKEN` on a self-hosted gateway. Over anything but loopback, carry it on an encrypted path: a WireGuard tailnet, an SSH tunnel (`ssh -N -L 8011:127.0.0.1:8011 <gpu-box>`, then `ACESTEP_API_URL=http://127.0.0.1:8011`), or TLS in front (`https://`). The bundled Modal gateway URL is already `https://`.

The API server also has a Gradio UI (`uv run acestep`) for poking at settings by hand, and `profile_inference.py` for timing (see `latency.md`).

## Modal (serverless GPU, pay per second)

The apps in `../modal/` are the ones we run. Each caches weights in a Modal Volume named `<app>-weights`, created in **your** workspace on first deploy.

**App names collide.** The bundled apps deploy as `acestep`, `minimax-music3`, `heartmula`, and `musicgen-gateway`, with volumes `acestep-weights`, `minimax-music3-weights`, and `heartmula-weights`. `modal deploy` replaces any same-named app in your workspace. If you already run apps with those names, edit the `modal.App(...)` and `modal.Volume.from_name(...)` names before deploying, then point the CLI at them with `MUSICGEN_MODAL_<MODEL>=app:Class` (and set the same variables on the gateway's `musicgen-gateway` secret).

The ACE-Step app loads the `acestep-v15-turbo` DiT and the 1.7B 5Hz LM (`acestep-5Hz-lm-1.7B`), both from upstream's main weights bundle; `download_weights` fetches them. Music 3's `download_weights` also fetches `dav.pth`, the encoder `--ref-audio` needs; `weights_status` reports it as `ref_audio_ready`.

```bash
pip install modal && modal token new

modal deploy modal/acestep_app.py
modal run modal/acestep_app.py::download_weights        # first time only

modal deploy modal/music3_app.py                         # L40S, ~23GB VRAM
modal run modal/music3_app.py::download_weights          # ~20–25GB, takes a while
modal run modal/music3_app.py::weights_status

modal deploy modal/heartmula_app.py
modal run modal/heartmula_app.py::download_weights
```

Run the CLI from the skill folder (the `modal` package must be importable by the Python you use):

```bash
python3 scripts/generate-music.py --model music3 --backend modal --prompt-file caption.txt --lyrics-file lyrics.txt
```

Cost notes: L40S, scale to zero after 2–3 minutes idle. Cold starts load weights (Music 3 is the slow one); later calls inside the scaledown window skip that. Our measured runs: ACE-Step 30s instrumental, 20s wall-clock warm; Music 3 20s clip, 75s wall-clock including cold start. A short ACE-Step song costs cents.

Each app also has its own `modal run` entrypoint for one-offs without the CLI.

**Pinned upstream builds.** Each image builds from a fixed upstream commit, so a redeploy can't pick up a changed API. Bump a pin deliberately and retest after.

| App | Upstream | Pin |
|---|---|---|
| `acestep_app.py` | https://github.com/ace-step/ACE-Step-1.5 | `ACESTEP_REF` = `ca1e85fe9430179831e6bc6be790c332190a3866` |
| `heartmula_app.py` | https://github.com/HeartMuLa/heartlib | `HEARTLIB_REF` = `3783bdb8441f2c298b1e64c8651173aac200361c` |
| `music3_app.py` | https://github.com/huggingface/diffusers (Music 3 PR) | `DIFFUSERS_REF` = `dafe3733fcfdbf3c48915fe77be3aef65b5d6a2d` |

The Modal ACE-Step app loads `acestep-v15-turbo` only, so `--dit-model` works on the `api` backend alone.

## Gateway (HTTP, for callers without Modal credentials)

`modal/gateway_app.py` puts a token-authed HTTP front on the three Modal apps, so a web app, a phone, or another agent can generate without Modal credentials.

```bash
modal secret create musicgen-gateway MUSICGEN_GATEWAY_TOKEN=$(openssl rand -hex 24)
modal deploy modal/gateway_app.py        # prints the base URL
export MUSICGEN_GATEWAY_URL=https://<printed-url>
export MUSICGEN_GATEWAY_TOKEN=<the token>
```

Protocol, if you'd rather write your own service in front of something else:

```
POST /submit_song  {token, model, tags, lyrics, instrumental, max_audio_length_ms, seed,
                    task_type, bpm, keyscale, timesignature, audio_cover_strength,
                    repainting_start, repainting_end, src_audio_b64, src_audio_name,
                    ref_audio_b64, ref_audio_name, ref_strength, ref_tile,
                    vocal_language, inference_steps, thinking}
                → {call_id, seed} | {error}
POST /poll_song    {token, call_id}
                → {status: "pending"} | {status: "done", mp3_b64} | {status: "error", error}
```

`tags` is the caption (prose for ACE-Step and Music 3, comma tags for HeartMuLa). Fields a model doesn't use are ignored. `thinking` defaults to false, as on ACE-Step's own API server. A bad token gets HTTP 401 and a body over 48MB gets 413; a Bearer header is checked before the body is read. When `seed` is omitted, the gateway picks one per call (ACE-Step, Music 3) and returns it with the `call_id`. `audio_cover_strength` defaults to 0.3 for `text2music` with a reference and 1.0 for source-audio tasks. For Music 3, `lyrics` may be a tag-only sheet alongside `instrumental: true`.

**Call IDs aren't scoped to the gateway.** `/poll_song` looks up any Modal function call ID in the workspace the gateway runs in, so a token holder who learns another call's ID can read its return value. The gateway is stateless and doesn't track which IDs it issued. Deploy it in a dedicated Modal workspace holding only the music apps, and give the token only to callers you'd trust with those apps' outputs.

## Lyria (Gemini API)

```bash
pip install google-genai
export GEMINI_API_KEY=...        # https://aistudio.google.com/apikey
python3 scripts/generate-music.py --model lyria --prompt "calm cinematic underscore, soft strings" --seconds 45 --bpm 90
```

## Music 3 on your own GPU

There's no turnkey local server for Music 3 yet. It needs ~23GB VRAM in bf16 and the pinned diffusers PR (`DIFFUSERS_REF` in `modal/music3_app.py`). The pipeline is plain diffusers `ModularPipeline.from_pretrained(<weights dir>)`; `music3_app.py`'s `MiniMaxMusic3.generate` is the reference for calling it. We run it on an AMD Radeon 8060S iGPU (Strix Halo, ROCm, 30GB+ of shared memory free) at ~35 minutes per 4-minute song, so it works on non-NVIDIA hardware but it's slow. If you build a local server, put the gateway protocol above in front of it and the CLI will use it unchanged.
