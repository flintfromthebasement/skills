#!/usr/bin/env python3
"""generate-music — one CLI for several music models and wherever you host them.

Models:   acestep (ACE-Step 1.5), music3 (MiniMax Music 3), heartmula (HeartMuLa 3B),
          lyria (Google Lyria RealTime, instrumental), suno (prompt handoff, no API).
Backends: api      — ACE-Step's own REST server (local or remote), ACESTEP_API_URL
          modal    — the Modal apps shipped in ../modal/ (needs `pip install modal`)
          gateway  — any HTTP service speaking the submit_song / poll_song protocol
          gemini   — Lyria via the Gemini API (needs `pip install google-genai`)
          handoff  — Suno: writes paste-ready files, generates nothing

Stdlib only for the api / gateway backends. Prints OUTPUT_FILE=<abs path> on success.

Examples:
  generate-music.py --model acestep --prompt "lo-fi hip-hop, dusty Rhodes" --instrumental --seconds 60
  generate-music.py --model acestep --prompt "jazz trio" --task cover --src-audio song.mp3 --strength 0.3
  generate-music.py --model music3 --prompt-file caption.txt --lyrics-file lyrics.txt --seconds 180
  generate-music.py --model suno --prompt-file style.txt --lyrics-file lyrics.txt
  generate-music.py --check            # which backends are configured / reachable
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import mimetypes
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

MODELS = ("acestep", "music3", "heartmula", "lyria", "suno")
BACKENDS = {
    "acestep": ("api", "modal", "gateway"),
    "music3": ("modal", "gateway"),
    "heartmula": ("modal", "gateway"),
    "lyria": ("gemini",),
    "suno": ("handoff",),
}
# Duration cap per model when --seconds is omitted. None = let the model decide.
DEFAULT_SECONDS = {"acestep": None, "music3": 60.0, "heartmula": 120.0, "lyria": 30.0, "suno": None}
SECONDS_RANGE = {
    "acestep": (10.0, 600.0),
    "music3": (5.0, 300.0),
    "heartmula": (10.0, 240.0),
    "lyria": (5.0, 600.0),
}
MODAL_DEFAULTS = {
    "acestep": "acestep:AceStep",
    "music3": "minimax-music3:MiniMaxMusic3",
    "heartmula": "heartmula:HeartMuLa",
}
ACESTEP_DEFAULT_URL = "http://127.0.0.1:8001"
# Models whose backends take a seed; others ignore --seed.
SEEDED_MODELS = ("acestep", "music3", "lyria")
SUNO_STYLE_LIMIT = 1000


class GenError(RuntimeError):
    pass


class TransientError(GenError):
    """A connection failure or 5xx that is worth retrying while polling."""


def log(msg: str) -> None:
    print(f"[generate-music] {msg}", file=sys.stderr, flush=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "song"


def normalize_lyrics(lyrics: str) -> str:
    """Put section tags on their own line. `[Verse] words` loses the words on Music 3."""
    lines = []
    for raw in lyrics.splitlines():
        m = re.match(r"^(\[[^\]]+\])\s+(\S.*)$", raw.strip())
        if m:
            lines += [m.group(1), m.group(2)]
        else:
            lines.append(raw.rstrip())
    return "\n".join(lines).strip()


# ── backend resolution ─────────────────────────────────────────────────────────


def gateway_urls() -> tuple[str, str]:
    base = env("MUSICGEN_GATEWAY_URL").rstrip("/")
    submit = env("MUSICGEN_GATEWAY_SUBMIT_URL") or (f"{base}/submit_song" if base else "")
    poll = env("MUSICGEN_GATEWAY_POLL_URL") or (f"{base}/poll_song" if base else "")
    return submit, poll


def modal_available() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("modal") is not None
    except Exception:
        return False


def acestep_url() -> str:
    return env("ACESTEP_API_URL", ACESTEP_DEFAULT_URL).rstrip("/")


def acestep_healthy(url: str, timeout: float = 2.0) -> bool:
    """True only if an ACE-Step server answers. Port 8001 is also AutoMem's default."""
    try:
        req = urllib.request.Request(f"{url}/health", headers=acestep_headers())
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode() or "{}")
        return "ace-step" in str((body.get("data") or {}).get("service", "")).lower()
    except Exception:
        return False


def resolve_backend(model: str, requested: str) -> str:
    allowed = BACKENDS[model]
    choice = requested if requested != "auto" else env(f"MUSICGEN_{model.upper()}_BACKEND")
    if choice:
        if choice not in allowed:
            raise GenError(f"backend '{choice}' not supported for {model} (use one of: {', '.join(allowed)})")
        return choice
    if len(allowed) == 1:
        return allowed[0]
    if model == "acestep" and (env("ACESTEP_API_URL") or acestep_healthy(acestep_url())):
        return "api"
    if all(gateway_urls()):
        return "gateway"
    if modal_available():
        return "modal"
    hint = {
        "acestep": f"start ACE-Step's API server (`uv run acestep-api`, default {ACESTEP_DEFAULT_URL}) "
        "or set ACESTEP_API_URL",
    }.get(model, "deploy ../modal/ and `pip install modal`")
    raise GenError(f"no backend configured for {model}: {hint}, or set MUSICGEN_GATEWAY_URL. See references/backends.md")


# ── HTTP helpers ───────────────────────────────────────────────────────────────


def http_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 120.0) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json", **(headers or {})}
    )
    return _read_json(req, timeout)


def _read_json(req: urllib.request.Request, timeout: float) -> dict:
    try:
        return json.loads(_fetch(req, timeout).decode() or "{}")
    except json.JSONDecodeError as e:
        raise GenError(f"bad JSON from {req.full_url}: {e}") from None


def _fetch(req: urllib.request.Request, timeout: float, opener=None) -> bytes:
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        cls = TransientError if e.code in (502, 503, 504) else GenError
        raise cls(f"HTTP {e.code} from {req.full_url}: {detail}") from None
    except urllib.error.URLError as e:
        raise TransientError(f"cannot reach {req.full_url}: {e.reason}") from None
    except OSError as e:  # timeouts and resets while reading
        raise TransientError(f"connection to {req.full_url} failed: {e}") from None


def same_host(url_a: str, url_b: str) -> bool:
    a, b = urllib.parse.urlsplit(url_a), urllib.parse.urlsplit(url_b)
    default = {"http": 80, "https": 443}
    try:
        return bool(a.hostname) and (a.hostname, a.port or default.get(a.scheme)) == (
            b.hostname, b.port or default.get(b.scheme))
    except ValueError:
        return False


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Drop the Authorization header when a redirect leaves the original host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and not same_host(newurl, req.full_url):
            new.remove_header("Authorization")
        return new


def multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = f"----generate-music-{uuid.uuid4().hex}"
    out = bytearray()
    for k, v in fields.items():
        if v is None:
            continue
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode()
        out += (json.dumps(v) if isinstance(v, bool) else str(v)).encode() + b"\r\n"
    for k, path in files.items():
        p = Path(path)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        out += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{p.name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode()
        out += p.read_bytes() + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


# ── ACE-Step REST API (upstream `acestep-api`) ─────────────────────────────────


def acestep_headers() -> dict:
    key = env("ACESTEP_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else {}


def cover_strength(a: argparse.Namespace) -> float:
    """ACE-Step audio_cover_strength: light for a text2music style reference, full for source-audio tasks."""
    if a.strength is not None:
        return a.strength
    return 0.3 if a.task == "text2music" else 1.0


def acestep_payload(a: argparse.Namespace) -> dict:
    lyrics = "[Instrumental]" if a.instrumental else a.lyrics_text
    p: dict = {
        "prompt": a.prompt_text,
        "lyrics": lyrics,
        "task_type": a.task,
        "batch_size": 1,
        "audio_format": "mp3",
        "thinking": bool(a.thinking),
    }
    if a.seconds:
        p["audio_duration"] = a.seconds
    if a.bpm:
        p["bpm"] = a.bpm
    if a.key:
        p["key_scale"] = a.key
    if a.time_signature:
        p["time_signature"] = a.time_signature
    if a.language:
        p["vocal_language"] = a.language
    if a.steps:
        p["inference_steps"] = a.steps
    if a.seed is not None and a.seed >= 0:
        p["seed"] = a.seed
        p["use_random_seed"] = False
    if a.task != "text2music" or a.src_audio or a.ref_audio:
        p["audio_cover_strength"] = cover_strength(a)
    if a.task == "repaint":
        p["repainting_start"] = a.repaint_start
        p["repainting_end"] = a.repaint_end
    if a.dit_model:
        p["model"] = a.dit_model
    return p


def run_acestep_api(a: argparse.Namespace) -> bytes:
    base = acestep_url()
    payload = acestep_payload(a)
    files = {}
    if a.src_audio:
        files["src_audio"] = a.src_audio
    if a.ref_audio:
        files["reference_audio"] = a.ref_audio
    if files:
        body, ctype = multipart(payload, files)
        req = urllib.request.Request(
            f"{base}/release_task", data=body, method="POST",
            headers={"Content-Type": ctype, **acestep_headers()},
        )
        resp = _read_json(req, 300)
    else:
        resp = http_json(f"{base}/release_task", payload, acestep_headers())
    task_id = (resp.get("data") or {}).get("task_id")
    if not task_id:
        raise GenError(f"ACE-Step release_task returned no task_id: {resp.get('error') or resp}")
    log(f"ACE-Step task {task_id} queued at {base}")

    deadline = time.time() + a.timeout
    while time.time() < deadline:
        time.sleep(a.poll_interval)
        try:
            resp = http_json(f"{base}/query_result", {"task_id_list": [task_id]}, acestep_headers())
        except TransientError as e:
            log(f"poll failed, retrying: {e}")
            continue
        items = resp.get("data") or []
        item = next((i for i in items if i.get("task_id") == task_id), items[0] if items else None)
        if not item:
            continue
        status = item.get("status")
        if status == 0:
            continue
        results = item.get("result") or "[]"
        if isinstance(results, str):
            try:
                results = json.loads(results)
            except json.JSONDecodeError:
                results = []
        if status == 2:
            err = item.get("error") or (results[0].get("error") if results else "") or results
            raise GenError(f"ACE-Step generation failed: {err}")
        if status == 1:
            if not results or not results[0].get("file"):
                raise GenError(f"ACE-Step finished without a file: {item}")
            file_url = results[0]["file"]
            if not file_url.startswith("http"):
                file_url = urllib.parse.urljoin(base + "/", file_url.lstrip("/"))
            metas = results[0].get("metas")
            if metas:
                log(f"ACE-Step metas: {json.dumps(metas)}")
            headers = acestep_headers() if same_host(file_url, base) else {}
            req = urllib.request.Request(file_url, headers=headers)
            try:
                return _fetch(req, 300, urllib.request.build_opener(_StripAuthOnRedirect))
            except GenError as e:
                raise GenError(f"ACE-Step finished but the download failed: {e}") from None
    raise GenError(f"ACE-Step task {task_id} still running after {a.timeout}s")


# ── gateway (submit_song / poll_song) ──────────────────────────────────────────


def outgoing_lyrics(a: argparse.Namespace) -> str:
    """Music 3 keeps a tag-only sheet under --instrumental; other models drop lyrics."""
    return a.lyrics_text if a.model == "music3" or not a.instrumental else ""


def gateway_payload(a: argparse.Namespace) -> dict:
    p: dict = {
        "model": a.model,
        "tags": a.prompt_text,
        "lyrics": outgoing_lyrics(a),
        "instrumental": bool(a.instrumental),
    }
    if a.seconds:
        p["max_audio_length_ms"] = int(a.seconds * 1000)
    if a.seed is not None:
        p["seed"] = a.seed
    if a.model == "acestep":
        p["task_type"] = a.task
        for key, val in (("bpm", a.bpm), ("keyscale", a.key), ("timesignature", a.time_signature)):
            if val:
                p[key] = val
        if a.task != "text2music" or a.src_audio or a.ref_audio or a.strength is not None:
            p["audio_cover_strength"] = cover_strength(a)
        if a.task == "repaint":
            p["repainting_start"] = a.repaint_start
            p["repainting_end"] = a.repaint_end
        if a.language:
            p["vocal_language"] = a.language
        if a.steps:
            p["inference_steps"] = a.steps
        p["thinking"] = bool(a.thinking)
    if a.model == "music3" and a.ref_audio:
        p["ref_strength"] = a.strength if a.strength is not None else 0.3
        p["ref_tile"] = bool(a.ref_tile)
    return p


def run_gateway(a: argparse.Namespace) -> bytes:
    submit, poll = gateway_urls()
    if not (submit and poll):
        raise GenError("gateway backend needs MUSICGEN_GATEWAY_URL (or both _SUBMIT_URL and _POLL_URL)")
    token = env("MUSICGEN_GATEWAY_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = gateway_payload(a)
    if token:
        payload["token"] = token
    for flag, key in (("src_audio", "src_audio"), ("ref_audio", "ref_audio")):
        path = getattr(a, flag)
        if path:
            payload[f"{key}_b64"] = base64.b64encode(Path(path).read_bytes()).decode()
            payload[f"{key}_name"] = Path(path).name
    resp = http_json(submit, payload, headers, timeout=300)
    call_id = resp.get("call_id")
    if not call_id:
        raise GenError(f"gateway submit failed: {resp.get('error') or resp}")
    log(f"gateway call {call_id} submitted")
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        time.sleep(a.poll_interval)
        body = {"call_id": call_id, **({"token": token} if token else {})}
        try:
            resp = http_json(poll, body, headers, timeout=300)
        except TransientError as e:
            log(f"poll failed, retrying: {e}")
            continue
        status = resp.get("status")
        if status == "done":
            return base64.b64decode(resp["mp3_b64"])
        if status == "error" or resp.get("error"):
            raise GenError(f"gateway generation failed: {resp.get('error')}")
    raise GenError(f"gateway call {call_id} still running after {a.timeout}s")


# ── Modal (apps in ../modal/) ──────────────────────────────────────────────────


def run_modal(a: argparse.Namespace) -> bytes:
    try:
        import modal
    except ImportError:
        raise GenError("modal backend needs `pip install modal` and `modal token new`") from None
    spec = env(f"MUSICGEN_MODAL_{a.model.upper()}", MODAL_DEFAULTS[a.model])
    app_name, _, cls_name = spec.partition(":")
    if not cls_name:
        raise GenError(f"MUSICGEN_MODAL_{a.model.upper()} must look like app:Class, got {spec!r}")
    kw = {"environment_name": env("MODAL_ENVIRONMENT")} if env("MODAL_ENVIRONMENT") else {}
    cls = modal.Cls.from_name(app_name, cls_name, **kw)
    log(f"calling Modal {app_name}:{cls_name} (cold start loads weights; first call can take minutes)")
    read = lambda p: Path(p).read_bytes() if p else None
    if a.model == "acestep":
        return cls().generate.remote(
            caption=a.prompt_text,
            lyrics="" if a.instrumental else a.lyrics_text,
            instrumental=bool(a.instrumental or not a.lyrics_text),
            duration=float(a.seconds or -1),
            bpm=a.bpm or None,
            keyscale=a.key or "",
            timesignature=a.time_signature or "",
            task_type=a.task,
            src_audio=read(a.src_audio),
            src_audio_name=Path(a.src_audio).name if a.src_audio else "src.mp3",
            reference_audio=read(a.ref_audio),
            reference_audio_name=Path(a.ref_audio).name if a.ref_audio else "ref.mp3",
            audio_cover_strength=cover_strength(a),
            repainting_start=a.repaint_start,
            repainting_end=a.repaint_end,
            seed=a.seed if a.seed is not None else -1,
            vocal_language=a.language or "",
            inference_steps=a.steps or 0,
            thinking=bool(a.thinking),
        )
    if a.model == "music3":
        kwargs = dict(
            prompt=a.prompt_text,
            lyrics=outgoing_lyrics(a),
            audio_duration=float(a.seconds),
            seed=a.seed if a.seed is not None else 42,
            instrumental=bool(a.instrumental),
        )
        if a.ref_audio:
            kwargs.update(
                ref_audio=read(a.ref_audio),
                ref_audio_name=Path(a.ref_audio).name,
                ref_strength=a.strength if a.strength is not None else 0.3,
                ref_tile=bool(a.ref_tile),
            )
        return cls().generate.remote(**kwargs)
    return cls().generate.remote(
        lyrics=a.lyrics_text,
        tags=a.prompt_text,
        max_audio_length_ms=int(a.seconds * 1000),
    )


# ── Lyria RealTime (Gemini API) ────────────────────────────────────────────────


def run_lyria(a: argparse.Namespace, out: Path) -> Path:
    try:
        import asyncio
        import wave

        from google import genai
        from google.genai import types
    except ImportError:
        raise GenError("lyria backend needs `pip install google-genai`") from None
    key = env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")
    if not key:
        raise GenError("lyria backend needs GEMINI_API_KEY (free key: https://aistudio.google.com/apikey)")
    rate, channels, width = 48000, 2, 2
    target = int(a.seconds * rate * channels * width)
    buf = bytearray()

    async def go() -> None:
        client = genai.Client(api_key=key, http_options={"api_version": "v1alpha"})
        cfg: dict = {"bpm": a.bpm or 110, "temperature": 1.0}
        if a.seed is not None and a.seed >= 0:
            cfg["seed"] = a.seed
        async with client.aio.live.music.connect(model=env("LYRIA_MODEL", "models/lyria-realtime-exp")) as s:
            await s.set_weighted_prompts(prompts=[types.WeightedPrompt(text=a.prompt_text, weight=1.0)])
            await s.set_music_generation_config(config=types.LiveMusicGenerationConfig(**cfg))
            await s.play()
            async for msg in s.receive():
                sc = msg.server_content
                if sc and sc.audio_chunks:
                    for chunk in sc.audio_chunks:
                        buf.extend(chunk.data)
                if len(buf) >= target:
                    return

    try:
        asyncio.run(asyncio.wait_for(go(), timeout=a.seconds + 30))
    except (TimeoutError, asyncio.TimeoutError):
        log(f"Lyria stream timed out with {len(buf) / (rate * channels * width):.1f}s collected")
    if not buf:
        raise GenError("Lyria returned no audio")
    wav = out.with_suffix(".wav")
    with wave.open(str(wav), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(bytes(buf[:target]))
    if out.suffix.lower() == ".wav":
        return wav
    if not shutil.which("ffmpeg"):
        log("ffmpeg not found; keeping WAV")
        return wav
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "192k", str(out)], check=True)
    wav.unlink()
    return out


# ── Suno handoff ───────────────────────────────────────────────────────────────


def run_suno(a: argparse.Namespace, out: Path) -> list[Path]:
    stem = out.with_suffix("")
    style = a.prompt_text.strip()
    files = []
    style_path = Path(f"{stem}-style-prompt.txt")
    style_path.write_text(style + "\n")
    files.append(style_path)
    if a.lyrics_text and not a.instrumental:
        lyr = Path(f"{stem}-lyrics.txt")
        lyr.write_text(a.lyrics_text + "\n")
        files.append(lyr)
    if len(style) > SUNO_STYLE_LIMIT:
        log(f"WARN: style prompt is {len(style)} chars; Suno caps it at {SUNO_STYLE_LIMIT}. Trim it.")
    log("Suno has no public API: open https://suno.com/create → Custom, paste the lyrics and style prompt.")
    if a.instrumental:
        log("Toggle Instrumental on in Suno.")
    return files


# ── main ───────────────────────────────────────────────────────────────────────


def check() -> int:
    print(f"acestep api   {acestep_url()}  {'ACE-Step server found' if acestep_healthy(acestep_url()) else 'no ACE-Step server'}"
          f"{'  (ACESTEP_API_KEY set)' if env('ACESTEP_API_KEY') else ''}")
    submit, poll = gateway_urls()
    print(f"gateway       {'configured' if submit and poll else 'not configured'}"
          f"{'  (token set)' if env('MUSICGEN_GATEWAY_TOKEN') else ''}")
    print(f"modal         {'python package installed' if modal_available() else 'not installed (pip install modal)'}")
    for m in ("acestep", "music3", "heartmula"):
        print(f"  {m:<10}  {env(f'MUSICGEN_MODAL_{m.upper()}', MODAL_DEFAULTS[m])}")
    print(f"lyria         {'GEMINI_API_KEY set' if env('GEMINI_API_KEY') or env('GOOGLE_API_KEY') else 'no GEMINI_API_KEY'}")
    for m in MODELS:
        try:
            print(f"→ {m:<10} auto backend = {resolve_backend(m, 'auto')}")
        except GenError as e:
            print(f"→ {m:<10} {e}")
    return 0


def read_text(inline: str, path: str, what: str) -> str:
    if path:
        p = Path(path)
        if not p.is_file():
            raise GenError(f"{what} file not found: {path}")
        return p.read_text()
    return inline or ""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate music with ACE-Step 1.5, MiniMax Music 3, HeartMuLa, Lyria, or a Suno handoff.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples:")[1] if "Examples:" in __doc__ else "",
    )
    p.add_argument("--check", action="store_true", help="Show configured backends and exit")
    p.add_argument("--model", choices=MODELS, default=env("MUSICGEN_MODEL", "acestep"))
    p.add_argument("--backend", default="auto", help="auto | api | modal | gateway | gemini | handoff")
    p.add_argument("--prompt", default="", help="Caption / style description (model-specific; see references/models.md)")
    p.add_argument("--prompt-file", default="")
    p.add_argument("--lyrics", default="", help="Lyrics with [Section] tags on their own lines")
    p.add_argument("--lyrics-file", default="")
    p.add_argument("--instrumental", action="store_true", help="No vocals")
    p.add_argument("--seconds", type=float, default=None, help="Duration cap (model default if omitted)")
    p.add_argument("--seed", type=int, default=None, help="Same inputs + seed = same audio (random if omitted)")
    p.add_argument("--out", default="", help="Output path (.mp3; Lyria also accepts .wav)")
    g = p.add_argument_group("ACE-Step")
    g.add_argument("--task", default="text2music",
                   choices=("text2music", "cover", "repaint", "lego", "extract", "complete"))
    g.add_argument("--src-audio", default="", help="Source track for cover / repaint / lego / extract / complete")
    g.add_argument("--ref-audio", default="", help="Style reference clip (ACE-Step) or sound-transfer clip (Music 3)")
    g.add_argument("--strength", type=float, default=None,
                   help="ACE-Step audio_cover_strength 0-1 (default 0.3 with text2music --ref-audio, 1.0 for "
                        "source-audio tasks) / Music 3 ref_strength (default 0.3)")
    g.add_argument("--ref-tile", action="store_true", help="Music 3: tile the reference across the whole song")
    g.add_argument("--repaint-start", type=float, default=0.0)
    g.add_argument("--repaint-end", type=float, default=-1.0)
    g.add_argument("--bpm", type=int, default=0)
    g.add_argument("--key", default="", help='e.g. "E minor"')
    g.add_argument("--time-signature", default="", help="2, 3, 4, or 6")
    g.add_argument("--language", default="", help="Vocal language code (en, ja, zh, …)")
    g.add_argument("--steps", type=int, default=0, help="Diffusion steps (turbo default 8)")
    g.add_argument("--thinking", action="store_true", help="Let ACE-Step's 5Hz LM plan audio codes first")
    g.add_argument("--dit-model", default="", help="ACE-Step DiT model name on the API server")
    p.add_argument("--timeout", type=float, default=float(env("MUSICGEN_TIMEOUT", "1800")))
    p.add_argument("--poll-interval", type=float, default=3.0)
    p.add_argument("--dry-run", action="store_true", help="Print the resolved backend and request; send nothing")
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if a.check:
        return check()
    try:
        a.prompt_text = read_text(a.prompt, a.prompt_file, "prompt").strip()
        a.lyrics_text = normalize_lyrics(read_text(a.lyrics, a.lyrics_file, "lyrics"))
        for f in (a.src_audio, a.ref_audio):
            if f and not Path(f).is_file():
                raise GenError(f"audio file not found: {f}")
        if not a.prompt_text and a.model != "acestep":
            raise GenError("--prompt or --prompt-file is required")
        if not a.prompt_text and not a.lyrics_text and a.task == "text2music":
            raise GenError("give ACE-Step at least a --prompt or --lyrics")
        if a.model in ("music3", "heartmula") and not a.instrumental and not a.lyrics_text:
            raise GenError(f"{a.model} needs --lyrics/--lyrics-file (or --instrumental)")
        if a.model == "heartmula" and a.instrumental:
            raise GenError("HeartMuLa is vocal-only; use acestep or lyria for instrumentals")
        if a.model == "lyria" and a.lyrics_text:
            log("Lyria is instrumental-only; ignoring lyrics")
        if a.task != "text2music" and a.model != "acestep":
            raise GenError("--task is ACE-Step only")
        if a.task in ("cover", "repaint", "lego", "extract", "complete") and not a.src_audio:
            raise GenError(f"--task {a.task} needs --src-audio")
        if a.ref_audio and a.model not in ("acestep", "music3"):
            raise GenError("--ref-audio works with acestep and music3 only")

        if a.seconds is None:
            a.seconds = DEFAULT_SECONDS[a.model]
        if a.seconds is not None and a.model in SECONDS_RANGE:
            lo, hi = SECONDS_RANGE[a.model]
            a.seconds = max(lo, min(hi, float(a.seconds)))

        if a.model in SEEDED_MODELS and (a.seed is None or a.seed < 0):
            a.seed = random.randint(0, 2**31 - 1)
            log(f"seed={a.seed} (random; pass --seed {a.seed} to repeat this take)")
        elif a.model not in SEEDED_MODELS and a.seed is not None:
            log(f"{a.model} has no seed control; ignoring --seed")
            a.seed = None

        backend = resolve_backend(a.model, a.backend)
        if a.dit_model and backend != "api":
            raise GenError(f"--dit-model needs the api backend; the {backend} ACE-Step app runs a fixed DiT "
                           "(acestep-v15-turbo in ../modal/acestep_app.py)")

        if a.out:
            out = Path(a.out).expanduser()
        else:
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            out_dir = Path(env("MUSICGEN_OUT_DIR", "music-output")).expanduser()
            out = out_dir / f"{a.model}-{slugify(a.prompt_text or a.lyrics_text)}-{ts}.mp3"
        out = out.resolve()

        if a.dry_run:
            req = {
                "api": lambda: {"url": f"{acestep_url()}/release_task", "payload": acestep_payload(a)},
                "gateway": lambda: {"url": gateway_urls()[0], "payload": gateway_payload(a)},
            }.get(backend, lambda: {"model": a.model})()
            print(json.dumps({"model": a.model, "backend": backend, "out": str(out), "request": req}, indent=2))
            return 0

        out.parent.mkdir(parents=True, exist_ok=True)
        log(f"model={a.model} backend={backend} seconds={a.seconds} seed={a.seed} instrumental={a.instrumental}")
        started = time.time()
        if backend == "handoff":
            for f in run_suno(a, out):
                print(f"OUTPUT_FILE={f}")
            return 0
        if backend == "gemini":
            final = run_lyria(a, out)
        else:
            data = {"api": run_acestep_api, "gateway": run_gateway, "modal": run_modal}[backend](a)
            if not data:
                raise GenError("backend returned no audio")
            out.write_bytes(data)
            final = out
        log(f"done in {time.time() - started:.1f}s → {final} ({final.stat().st_size / 1e6:.1f} MB)")
        print(f"OUTPUT_FILE={final}")
        return 0
    except GenError as e:
        log(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
