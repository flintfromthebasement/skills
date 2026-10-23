"""HeartMuLa (heartlib) music generation on Modal serverless GPU.

Deploy:  modal deploy modal/heartmula_app.py
One-off: modal run modal/heartmula_app.py --lyrics-file lyrics.txt --tags "piano,happy"
Weights: modal run modal/heartmula_app.py::download_weights   (first time only)
"""

import modal

app = modal.App("heartmula")

CKPT_DIR = "/ckpt"
weights = modal.Volume.from_name("heartmula-weights", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install("git+https://github.com/HeartMuLa/heartlib.git", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)


@app.function(image=image, volumes={CKPT_DIR: weights}, timeout=3600)
def download_weights():
    from huggingface_hub import snapshot_download

    snapshot_download("HeartMuLa/HeartMuLaGen", local_dir=CKPT_DIR)
    snapshot_download("HeartMuLa/HeartMuLa-oss-3B-happy-new-year", local_dir=f"{CKPT_DIR}/HeartMuLa-oss-3B")
    snapshot_download("HeartMuLa/HeartCodec-oss-20260123", local_dir=f"{CKPT_DIR}/HeartCodec-oss")
    weights.commit()
    print("weights downloaded")


@app.cls(image=image, gpu="L40S", volumes={CKPT_DIR: weights}, timeout=1800, scaledown_window=120)
class HeartMuLa:
    @modal.enter()
    def load(self):
        import torch
        from heartlib import HeartMuLaGenPipeline

        self.torch = torch
        self.pipe = HeartMuLaGenPipeline.from_pretrained(
            CKPT_DIR,
            device={"mula": torch.device("cuda"), "codec": torch.device("cuda")},
            dtype={"mula": torch.bfloat16, "codec": torch.float32},
            version="3B",
        )

    @modal.method()
    def generate(
        self,
        lyrics: str,
        tags: str,
        max_audio_length_ms: int = 240_000,
        topk: int = 50,
        temperature: float = 1.0,
        cfg_scale: float = 1.5,
    ) -> bytes:
        import tempfile, pathlib, subprocess
        import torchaudio

        # torchaudio 2.9+ delegates save to torchcodec, which fails to load here;
        # write WAV via soundfile and transcode with ffmpeg instead
        def _save(path, wav, sample_rate):
            import soundfile as sf
            wav_path = str(path) + ".wav"
            sf.write(wav_path, wav.numpy().T, sample_rate)
            subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-b:a", "192k", str(path)], check=True, capture_output=True)

        torchaudio.save = _save

        with tempfile.TemporaryDirectory() as td:
            out = pathlib.Path(td) / "song.mp3"
            with self.torch.no_grad():
                self.pipe(
                    {"lyrics": lyrics, "tags": tags},
                    max_audio_length_ms=max_audio_length_ms,
                    save_path=str(out),
                    topk=topk,
                    temperature=temperature,
                    cfg_scale=cfg_scale,
                )
            return out.read_bytes()


@app.local_entrypoint()
def main(
    lyrics_file: str,
    tags: str = "piano,happy",
    out: str = "",
    max_seconds: int = 240,
    temperature: float = 1.0,
    cfg_scale: float = 1.5,
):
    import pathlib, datetime

    lyrics = pathlib.Path(lyrics_file).read_text()
    mp3 = HeartMuLa().generate.remote(
        lyrics, tags, max_audio_length_ms=max_seconds * 1000,
        temperature=temperature, cfg_scale=cfg_scale,
    )
    if not out:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        out = f"music-output/heartmula-{stamp}.mp3"
    p = pathlib.Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(mp3)
    print(f"saved {p} ({len(mp3)/1e6:.1f} MB)")
