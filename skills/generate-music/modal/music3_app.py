"""MiniMax Music 3 on Modal — lyrics + caption → full song (up to 5 min).

Source: https://huggingface.co/MiniMaxAI/MiniMax-Music3
Inference: huggingface/diffusers @ DIFFUSERS_REF (PR #14456, not on main yet).

Deploy:  modal deploy modal/music3_app.py
Weights: modal run modal/music3_app.py::download_weights
Status:  modal run modal/music3_app.py::weights_status
One-off: modal run modal/music3_app.py --lyrics-file l.txt --prompt "..." --out /tmp/m3.mp3

Hardware (diffusers docs): ~23GB bf16. L40S 48GB holds the full stack, no offload.
audio_duration is a cap — the LM may emit EOS earlier. 25 frames/sec AR dominates runtime.
"""

from __future__ import annotations

import pathlib
import re

import modal

app = modal.App("minimax-music3")

CKPT_DIR = "/ckpt"
weights = modal.Volume.from_name("minimax-music3-weights", create_if_missing=True)

# Pin the Music3 integration commit from the model card.
DIFFUSERS_REF = "dafe3733fcfdbf3c48915fe77be3aef65b5d6a2d"
HF_MODEL_ID = "MiniMaxAI/MiniMax-Music3"

# Diffusers modular half only. Skip SGLang qwen_7B shards + *.pth (~40GB).
ALLOW_PATTERNS = [
    "modular_model_index.json",
    "config.json",
    "language_model/*",
    "tokenizer/*",
    "transformer/*",
    "condition_encoder/*",
    "rvq_depth_decoder/*",
    "vocoder/*",
    "scheduler/*",
]

REQUIRED = (
    "language_model",
    "tokenizer",
    "transformer",
    "condition_encoder",
    "rvq_depth_decoder",
    "vocoder",
    "scheduler",
)

# Tag-only sheet sent when no lyrics are given.
INSTRUMENTAL_LYRICS = "\n".join(
    f"[{section}]\n(instrumental)" for section in ("Intro", "Verse", "Verse", "Verse", "Bridge", "Outro")
)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install(
        "torch",
        "torchaudio",
        "transformers>=4.56.0",
        "accelerate",
        "safetensors",
        "sentencepiece",
        "protobuf",
        "soundfile",
        "numpy",
        "huggingface_hub[hf_transfer]",
    )
    .pip_install(f"git+https://github.com/huggingface/diffusers.git@{DIFFUSERS_REF}")
    .env(
        {
            "HF_HOME": f"{CKPT_DIR}/hf-home",
            "TRANSFORMERS_CACHE": f"{CKPT_DIR}/hf-home",
            "DIFFUSERS_CACHE": f"{CKPT_DIR}/hf-home",
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
        }
    )
    .add_local_file(str(pathlib.Path(__file__).with_name("dav_encoder.py")), "/root/dav_encoder.py")
)

# Latents per AR frame: (44100 Hz / 512 hop) / 25 fps.
_LATENTS_PER_FRAME = 3.4453125


def _install_ref_audio_patch():
    """Teach the flow-matching denoise loop to pin latent regions to reference-audio latents.

    Convention (scheduler has invert_sigmas=true): time t ascends 0 -> 1, 0 = noise. The stock
    loop already pins the chunk-overlap region onto the (1-t)*noise + t*target path each step;
    this patch applies the same pinning to reference latents stashed on the pipeline as
    `_musicgen_ref` = {"latents": [1,128,L], "strength": float, "tile": bool}, releasing the pin
    once t > strength so lower strengths only seed timbre/texture.
    """
    import torch
    from diffusers.modular_pipelines.minimax_music3 import denoise as m3d

    if getattr(m3d, "_musicgen_ref_patched", False):
        return
    m3d._musicgen_ref_patched = True

    orig_prepare = m3d.MiniMaxMusic3ChunkPrepareLatentsStep.__call__

    def prepare_with_ref(self, components, block_state, k):
        components, block_state = orig_prepare(self, components, block_state, k)
        ref = getattr(components, "_musicgen_ref", None)
        block_state._musicgen_ref_chunk = None
        if ref is not None:
            latents = block_state.latents
            length = latents.shape[-1]
            offset = round(block_state.chunk_starts[k] * _LATENTS_PER_FRAME)
            ref_latents = ref["latents"].to(latents.device, latents.dtype)
            ref_len = ref_latents.shape[-1]
            feather = 86  # ~1s pin crossfade at the reference's end so free generation gets a hand-off
            chunk_ref = torch.zeros_like(latents)
            weight = torch.zeros(length, device=latents.device, dtype=latents.dtype)
            for i in range(length):
                j = offset + i
                if ref["tile"]:
                    j = j % ref_len
                elif j >= ref_len:
                    break
                chunk_ref[..., i] = ref_latents[..., j]
                if ref["tile"] or j < ref_len - feather:
                    weight[i] = 1.0
                else:
                    weight[i] = (ref_len - j) / feather
            if weight.any():
                block_state._musicgen_ref_chunk = (chunk_ref, weight, latents.clone(), ref["strength"])
        return components, block_state

    orig_inner = m3d.MiniMaxMusic3ChunkDenoiseInner.__call__

    def denoise_with_ref(self, components, block_state, k):
        ref_chunk = getattr(block_state, "_musicgen_ref_chunk", None)
        if ref_chunk is None:
            return orig_inner(self, components, block_state, k)

        chunk_ref, weight, init_noise, strength = ref_chunk
        latents = block_state.latents
        timesteps = block_state.timesteps
        overlap = block_state.overlap
        guider_inputs = {
            "encoder_hidden_states": (block_state.condition, torch.zeros_like(block_state.condition)),
        }
        for i, t in enumerate(timesteps):
            time_value = t.to(latents.dtype)
            if overlap > 0:
                latents[..., :overlap] = (1.0 - (1.0 - 1e-6) * time_value) * block_state.noise_prompt + (
                    time_value * block_state.previous_latent[..., :overlap]
                )
            if float(t) <= strength:
                pin = (1.0 - (1.0 - 1e-6) * time_value) * init_noise + time_value * chunk_ref
                latents = pin * weight + latents * (1.0 - weight)
            timestep = t.expand(latents.shape[0]).to(latents.dtype)
            components.guider.set_state(step=i, num_inference_steps=block_state.num_inference_steps, timestep=t)
            guider_state = components.guider.prepare_inputs(guider_inputs)
            for guider_state_batch in guider_state:
                components.guider.prepare_models(components.transformer)
                cond_kwargs = {key: getattr(guider_state_batch, key) for key in guider_inputs}
                guider_state_batch.noise_pred = components.transformer(
                    hidden_states=latents,
                    timestep=timestep,
                    return_dict=False,
                    **cond_kwargs,
                )[0]
                components.guider.cleanup_models(components.transformer)
            velocity = components.guider(guider_state)[0]
            latents = components.scheduler.step(velocity, t, latents, return_dict=False)[0]
            block_state.progress_bar.update()

        block_state.latents = latents
        return components, block_state

    m3d.MiniMaxMusic3ChunkPrepareLatentsStep.__call__ = prepare_with_ref
    m3d.MiniMaxMusic3ChunkDenoiseInner.__call__ = denoise_with_ref


def normalize_lyrics(lyrics: str) -> str:
    """Put section tags on their own line — same-line text is dropped by the model."""
    lines = []
    for raw in lyrics.splitlines():
        m = re.match(r"^(\[[^\]]+\])\s+(\S.*)$", raw.strip())
        if m:
            lines.append(m.group(1))
            lines.append(m.group(2))
        else:
            lines.append(raw.rstrip())
    return "\n".join(lines).strip()


@app.function(
    image=image,
    volumes={CKPT_DIR: weights},
    timeout=6 * 60 * 60,
    memory=16 * 1024,
    cpu=4,
)
def download_weights():
    """Pull diffusers modular components from Hugging Face into the Modal volume."""
    import time
    from pathlib import Path

    from huggingface_hub import snapshot_download

    target = f"{CKPT_DIR}/MiniMax-Music3"
    Path(target).mkdir(parents=True, exist_ok=True)

    stop_commit = False

    def _commit_loop():
        import threading

        def loop():
            while not stop_commit:
                time.sleep(300)
                if stop_commit:
                    break
                try:
                    weights.commit()
                    print(f"volume checkpoint commit @ {time.strftime('%H:%M:%S')}")
                except Exception as e:
                    print(f"volume commit warn: {e}")

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return t

    _commit_loop()
    try:
        path = snapshot_download(
            repo_id=HF_MODEL_ID,
            local_dir=target,
            allow_patterns=ALLOW_PATTERNS,
            max_workers=8,
        )
    finally:
        stop_commit = True

    weights.commit()
    missing = [r for r in REQUIRED if not (Path(path) / r).exists()]
    total = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
    print(f"weights ready under {path} ({total / 1e9:.2f} GB)")
    if missing:
        raise RuntimeError(f"missing components after download: {missing}")
    return {"path": path, "bytes": total}


@app.function(image=image, volumes={CKPT_DIR: weights}, timeout=5 * 60, memory=4 * 1024)
def weights_status():
    from pathlib import Path

    root = Path(f"{CKPT_DIR}/MiniMax-Music3")
    if not root.exists():
        return {"ready": False, "bytes": 0, "components": {}}
    comps = {}
    for name in REQUIRED:
        p = root / name
        if p.exists():
            comps[name] = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        else:
            comps[name] = 0
    index = root / "modular_model_index.json"
    comps["modular_model_index.json"] = index.stat().st_size if index.is_file() else 0
    total = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    ready = all(comps[c] > 0 for c in REQUIRED) and comps["modular_model_index.json"] > 0
    return {"ready": ready, "bytes": total, "components": comps}


@app.cls(
    image=image,
    gpu="L40S",
    volumes={CKPT_DIR: weights},
    timeout=60 * 60,
    memory=32 * 1024,
    scaledown_window=180,
)
class MiniMaxMusic3:
    @modal.enter()
    def load(self):
        import os

        import torch
        from diffusers import ModularPipeline

        local = f"{CKPT_DIR}/MiniMax-Music3"
        if not os.path.isdir(local) or not os.path.isfile(f"{local}/modular_model_index.json"):
            raise RuntimeError(
                f"Weights missing at {local}. Run: modal run ...::download_weights"
            )

        self.torch = torch
        _install_ref_audio_patch()
        pipe = ModularPipeline.from_pretrained(local)
        pipe.load_components(dtype=torch.bfloat16)
        pipe.to("cuda")
        self.pipe = pipe
        self.dav_encoder = None
        print("MiniMaxMusic3 loaded")

    def _encode_reference(self, ref_audio: bytes, ref_name: str):
        """ref audio bytes -> [1, 128, L] flow latents (stereo folded as 2x64)."""
        import pathlib
        import subprocess
        import sys
        import tempfile

        import soundfile as sf

        if self.dav_encoder is None:
            from huggingface_hub import hf_hub_download

            dav_path = hf_hub_download(HF_MODEL_ID, "dav.pth", local_dir=f"{CKPT_DIR}/MiniMax-Music3")
            weights.commit()
            sys.path.insert(0, "/root")
            from dav_encoder import load_dav_encoder

            self.dav_encoder = load_dav_encoder(dav_path).eval().to("cuda")

        with tempfile.TemporaryDirectory() as td:
            src = pathlib.Path(td) / pathlib.Path(ref_name).name
            src.write_bytes(ref_audio)
            wav_path = pathlib.Path(td) / "ref-44k.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(wav_path)],
                check=True, capture_output=True,
            )
            wav, _ = sf.read(str(wav_path), dtype="float32", always_2d=True)
        audio = self.torch.from_numpy(wav.T).unsqueeze(1).to("cuda")  # [2, 1, T]
        with self.torch.no_grad():
            latents = self.dav_encoder(audio)  # [2, 64, L]
        return latents.reshape(1, 128, latents.shape[-1])

    @modal.method()
    def generate(
        self,
        prompt: str,
        lyrics: str,
        audio_duration: float = 60.0,
        seed: int = 42,
        instrumental: bool = False,
        ref_audio: bytes | None = None,
        ref_audio_name: str = "ref.wav",
        ref_strength: float = 0.35,
        ref_tile: bool = False,
    ) -> bytes:
        """Return 192k stereo MP3 bytes.

        lyrics: the sheet to sing, or a tag-only sheet for an instrumental. Empty lyrics fall back
        to INSTRUMENTAL_LYRICS. `instrumental` is accepted for protocol compatibility; the sheet
        decides.

        ref_audio: optional clip whose Flow-VAE latents are pinned into the denoise path.
        ref_strength 0..1 = how far along the noise->clean path the pin holds (1.0 ~ verbatim
        over the clip's span, 0.2-0.4 = timbre/room transfer). ref_tile loops the clip's
        latents across the whole song instead of only its own span.
        """
        import pathlib
        import subprocess
        import tempfile

        import numpy as np
        import soundfile as sf

        if not prompt.strip():
            raise ValueError("prompt (music description) is required")

        duration = max(5.0, min(300.0, float(audio_duration)))
        text = lyrics.strip()
        if not text:
            text = INSTRUMENTAL_LYRICS
        text = normalize_lyrics(text)

        self.pipe._musicgen_ref = None
        if ref_audio:
            latents = self._encode_reference(ref_audio, ref_audio_name)
            self.pipe._musicgen_ref = {
                "latents": latents,
                "strength": max(0.0, min(1.0, float(ref_strength))),
                "tile": bool(ref_tile),
            }
            print(f"reference latents: {tuple(latents.shape)} strength={ref_strength} tile={ref_tile}")

        audio = self.pipe(
            prompt=prompt.strip(),
            lyrics=text,
            audio_duration=duration,
            generator=self.torch.Generator("cuda").manual_seed(int(seed)),
            output="audios",
        )[0]

        sr = int(getattr(self.pipe, "sampling_rate", 44100) or 44100)
        wav = audio.float().cpu().numpy() if hasattr(audio, "float") else np.asarray(audio)
        if wav.ndim == 2 and wav.shape[0] <= 2:
            wav = wav.T

        with tempfile.TemporaryDirectory() as td:
            wav_path = pathlib.Path(td) / "song.wav"
            mp3_path = pathlib.Path(td) / "song.mp3"
            sf.write(str(wav_path), wav, sr)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "192k", str(mp3_path)],
                check=True,
                capture_output=True,
            )
            return mp3_path.read_bytes()


@app.local_entrypoint()
def main(
    prompt: str = (
        "Genre: acoustic pop. BPM: 96. Key: C major. Warm and intimate, building gently into the chorus. "
        "Vocals: soft female lead, close and breathy, light stacked harmonies in the chorus. "
        "Arrangement: fingerpicked guitar and soft piano; brushed drums and upright bass enter in the chorus."
    ),
    lyrics: str = "",
    lyrics_file: str = "",
    out: str = "",
    seconds: float = 60.0,
    seed: int = 42,
    instrumental: bool = False,
    ref_audio: str = "",
    ref_strength: float = 0.35,
    ref_tile: bool = False,
):
    import datetime
    import pathlib

    status = weights_status.remote()
    if not status.get("ready"):
        raise SystemExit(f"Weights not ready: {status}. Run download_weights first.")

    text = lyrics
    if lyrics_file:
        text = pathlib.Path(lyrics_file).read_text()
    if not text.strip() and not instrumental:
        text = (
            "[verse]\n"
            "Morning light filtering through the pine\n"
            "Every quiet street is yours and mine\n"
            "[chorus]\n"
            "Softly the world begins to breathe"
        )

    ref = pathlib.Path(ref_audio) if ref_audio else None
    mp3 = MiniMaxMusic3().generate.remote(
        prompt=prompt,
        lyrics=text,
        audio_duration=seconds,
        seed=seed,
        instrumental=instrumental,
        ref_audio=ref.read_bytes() if ref else None,
        ref_audio_name=ref.name if ref else "ref.wav",
        ref_strength=ref_strength,
        ref_tile=ref_tile,
    )

    if not out:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = f"music-output/music3-{ts}.mp3"
    path = pathlib.Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(mp3)
    print(f"wrote {path} ({path.stat().st_size} bytes)")
    print(f"OUTPUT_FILE={path}")
