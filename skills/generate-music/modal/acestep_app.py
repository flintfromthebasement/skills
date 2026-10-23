"""ACE-Step 1.5 music generation on Modal serverless GPU.

Instrumental-capable text-to-music (MIT license). Prose caption + optional lyrics,
real instrumental flag, and reference-audio tasks (cover / repaint / lego / extract /
complete). Fast: seconds per track on datacenter GPUs.

Running ACE-Step on your own GPU instead? Skip Modal: `uv run acestep-api` from the
upstream repo and point the CLI at it with ACESTEP_API_URL (see references/backends.md).

Deploy:  modal deploy modal/acestep_app.py
Weights: modal run modal/acestep_app.py::download_weights   (first time only)
One-off: modal run modal/acestep_app.py --caption "ambient piano, warm" --duration 120
"""

import modal

app = modal.App("acestep")

CKPT_DIR = "/ckpt"
weights = modal.Volume.from_name("acestep-weights", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")
    # nano-vllm is vendored inside the repo (uv path source), so clone and
    # install it before the package itself — a plain git pip install can't see it
    .run_commands(
        "git clone --depth 1 https://github.com/ace-step/ACE-Step-1.5.git /opt/acestep",
        "pip install /opt/acestep/acestep/third_parts/nano-vllm --extra-index-url https://download.pytorch.org/whl/cu128",
        "pip install /opt/acestep --extra-index-url https://download.pytorch.org/whl/cu128",
    )
    .env({"ACESTEP_PROJECT_ROOT": CKPT_DIR, "ACESTEP_DISABLE_TQDM": "1"})
)


@app.function(image=image, volumes={CKPT_DIR: weights}, timeout=3600)
def download_weights():
    from pathlib import Path

    from acestep.model_downloader import ensure_dit_model, ensure_main_model

    checkpoints = Path(CKPT_DIR) / "checkpoints"
    ok, msg = ensure_main_model(checkpoints)
    print(f"main model: {ok} {msg}")
    ok, msg = ensure_dit_model("acestep-v15-turbo", checkpoints)
    print(f"dit model: {ok} {msg}")
    weights.commit()


@app.cls(image=image, gpu="L40S", volumes={CKPT_DIR: weights}, timeout=1800, scaledown_window=120)
class AceStep:
    @modal.enter()
    def load(self):
        from acestep.handler import AceStepHandler
        from acestep.llm_inference import LLMHandler

        self.dit = AceStepHandler()
        msg, ok = self.dit.initialize_service(
            project_root=CKPT_DIR,
            config_path="acestep-v15-turbo",
            device="cuda",
        )
        if not ok:
            raise RuntimeError(f"ACE-Step init failed: {msg}")
        self.llm = LLMHandler()
        self.llm.initialize(
            checkpoint_dir=f"{CKPT_DIR}/checkpoints",
            lm_model_path="acestep-5Hz-lm-0.6B",
            backend="pt",
            device="cuda",
        )
        weights.commit()

    @modal.method()
    def generate(
        self,
        caption: str,
        lyrics: str = "",
        instrumental: bool = True,
        duration: float = -1.0,
        bpm: int | None = None,
        task_type: str = "text2music",
        src_audio: bytes | None = None,
        src_audio_name: str = "src.mp3",
        reference_audio: bytes | None = None,
        reference_audio_name: str = "ref.mp3",
        audio_cover_strength: float = 1.0,
        repainting_start: float = 0.0,
        repainting_end: float = -1.0,
        seed: int = -1,
        keyscale: str = "",
        timesignature: str = "",
    ) -> bytes:
        import dataclasses
        import pathlib
        import subprocess
        import tempfile

        from acestep.inference import GenerationConfig, GenerationParams, generate_music

        supported = {f.name for f in dataclasses.fields(GenerationParams)}
        kwargs = dict(
            caption=caption,
            lyrics=lyrics,
            instrumental=instrumental,
            duration=float(duration),
            bpm=bpm,
            task_type=task_type,
            audio_cover_strength=float(audio_cover_strength),
            repainting_start=float(repainting_start),
            repainting_end=float(repainting_end),
            seed=int(seed),
            keyscale=keyscale,
            timesignature=timesignature,
        )
        audio_dir = tempfile.mkdtemp(prefix="acestep-in-")
        for key, blob, name in (
            ("src_audio", src_audio, src_audio_name),
            ("reference_audio", reference_audio, reference_audio_name),
        ):
            if blob:
                p = pathlib.Path(audio_dir) / pathlib.Path(name).name
                p.write_bytes(blob)
                kwargs[key] = str(p)
        dropped = sorted(k for k in kwargs if k not in supported)
        if dropped and (task_type != "text2music" or src_audio or reference_audio):
            raise RuntimeError(f"deployed ACE-Step build lacks params {dropped}; rebuild the image")
        params = GenerationParams(**{k: v for k, v in kwargs.items() if k in supported})
        config = GenerationConfig(batch_size=1, audio_format="mp3")
        with tempfile.TemporaryDirectory() as td:
            result = generate_music(self.dit, self.llm, params, config, save_dir=td)
            if not result.success or not result.audios:
                raise RuntimeError(f"ACE-Step generation failed: {result.error or result.status_message}")
            # Per-stage timings (LM / DiT denoise / VAE decode). Read these before cutting steps.
            time_costs = (getattr(result, "extra_outputs", None) or {}).get("time_costs")
            if time_costs:
                print("time_costs:", {k: round(v, 2) for k, v in time_costs.items() if isinstance(v, (int, float))})
            path = pathlib.Path(result.audios[0]["path"])
            if path.suffix.lower() != ".mp3":
                mp3 = path.with_suffix(".mp3")
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(path), "-b:a", "192k", str(mp3)],
                    check=True, capture_output=True,
                )
                path = mp3
            return path.read_bytes()


@app.local_entrypoint()
def main(
    caption: str,
    lyrics_file: str = "",
    instrumental: bool = True,
    duration: float = -1.0,
    out: str = "acestep-song.mp3",
    task: str = "text2music",
    src_audio: str = "",
    ref_audio: str = "",
    cover_strength: float = 1.0,
    repaint_start: float = 0.0,
    repaint_end: float = -1.0,
    seed: int = -1,
    bpm: int = 0,
    keyscale: str = "",
):
    import pathlib

    lyrics = pathlib.Path(lyrics_file).read_text() if lyrics_file else ""
    src = pathlib.Path(src_audio) if src_audio else None
    ref = pathlib.Path(ref_audio) if ref_audio else None
    data = AceStep().generate.remote(
        caption=caption,
        lyrics=lyrics,
        instrumental=instrumental,
        duration=duration,
        task_type=task,
        src_audio=src.read_bytes() if src else None,
        src_audio_name=src.name if src else "src.mp3",
        reference_audio=ref.read_bytes() if ref else None,
        reference_audio_name=ref.name if ref else "ref.mp3",
        audio_cover_strength=cover_strength,
        repainting_start=repaint_start,
        repainting_end=repaint_end,
        seed=seed,
        bpm=bpm or None,
        keyscale=keyscale,
    )
    pathlib.Path(out).write_bytes(data)
    print(f"saved {out} ({len(data)/1e6:.1f} MB)")
