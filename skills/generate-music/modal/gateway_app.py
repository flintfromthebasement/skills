"""Token-authed HTTP gateway in front of the Modal music apps.

Gives non-Python callers (web apps, other agents, a phone) one base URL that speaks the
submit_song / poll_song protocol `scripts/generate-music.py --backend gateway` uses.
Optional: the CLI can call the Modal apps directly if you have Modal credentials locally.

Deploy:
  modal secret create musicgen-gateway MUSICGEN_GATEWAY_TOKEN=$(openssl rand -hex 24)
  modal deploy modal/gateway_app.py
  # prints https://<your-workspace>--musicgen-gateway-web.modal.run → MUSICGEN_GATEWAY_URL

Protocol (POST, JSON; token in the body as "token" or as `Authorization: Bearer`):
  /submit_song {model: acestep|music3|heartmula, tags, lyrics?, instrumental?,
                max_audio_length_ms?, seed?,
                acestep: task_type?, bpm?, keyscale?, timesignature?, audio_cover_strength?,
                         repainting_start?, repainting_end?, src_audio_b64?/src_audio_name?,
                         ref_audio_b64?/ref_audio_name?, vocal_language?, inference_steps?,
                         thinking? (default false)
                music3:  ref_audio_b64?/ref_audio_name?, ref_strength?, ref_tile?}
               -> {call_id, seed?}   (seed: the one used when you sent none; random per call)
  /poll_song   {call_id} -> {status: pending|done|error, mp3_b64?, error?}
A bad or missing token gets HTTP 401 {error: "unauthorized"}; a body over MAX_BODY_BYTES gets 413.
A Bearer header is checked before the body is read; a body-only token costs one capped read.

App names default to the ones in this folder; override with env vars on the secret
(MUSICGEN_MODAL_ACESTEP=app:Class, MUSICGEN_MODAL_MUSIC3=…, MUSICGEN_MODAL_HEARTMULA=…).
"""

import base64
import hmac
import json
import os
import random

import modal

app = modal.App("musicgen-gateway")
image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi[standard]")

# Room for base64 source/reference audio (a 5-minute mp3 is ~10MB encoded).
MAX_BODY_BYTES = 48 * 1024 * 1024

DEFAULTS = {
    "acestep": "acestep:AceStep",
    "music3": "minimax-music3:MiniMaxMusic3",
    "heartmula": "heartmula:HeartMuLa",
}


def _generator(model: str):
    app_name, _, cls_name = os.environ.get(f"MUSICGEN_MODAL_{model.upper()}", DEFAULTS[model]).partition(":")
    return modal.Cls.from_name(app_name, cls_name)().generate


def _b64(payload: dict, key: str):
    data = payload.get(key) or ""
    return base64.b64decode(data) if data else None


@app.function(image=image, secrets=[modal.Secret.from_name("musicgen-gateway")])
@modal.asgi_app()
def web():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    api = FastAPI()
    expected = os.environ["MUSICGEN_GATEWAY_TOKEN"]

    def token_ok(token) -> bool:
        return bool(token) and hmac.compare_digest(str(token), expected)

    def bearer(request: Request) -> bool | None:
        """True/False for a valid/invalid Bearer header, None when there is none."""
        header = request.headers.get("authorization", "")
        return token_ok(header[7:]) if header.lower().startswith("bearer ") else None

    def error(msg: str, status: int) -> JSONResponse:
        return JSONResponse({"error": msg}, status_code=status)

    async def authed_payload(request: Request) -> tuple[dict | None, JSONResponse | None]:
        header_ok = bearer(request)
        if header_ok is False:
            return None, error("unauthorized", 401)
        declared = request.headers.get("content-length", "")
        if declared and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
            return None, error("request body too large", 413)
        body = bytearray()
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY_BYTES:
                return None, error("request body too large", 413)
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            return None, error("body must be a JSON object", 400)
        if not header_ok and not token_ok(payload.get("token")):
            return None, error("unauthorized", 401)
        return payload, None

    def pick_seed(payload: dict) -> int:
        seed = payload.get("seed")
        return random.randint(0, 2**31 - 1) if seed is None or int(seed) < 0 else int(seed)

    def cover_strength(payload: dict, task_type: str) -> float:
        default = 0.3 if task_type == "text2music" else 1.0
        return float(payload.get("audio_cover_strength", default))

    @api.post("/submit_song")
    async def submit_song(request: Request):
        payload, err = await authed_payload(request)
        if err:
            return err
        model = payload.get("model", "acestep")
        tags = (payload.get("tags") or "").strip()
        lyrics = (payload.get("lyrics") or "").strip()
        instrumental = bool(payload.get("instrumental", False))
        if model not in DEFAULTS:
            return {"error": f"unknown model: {model}"}
        if not tags and model != "acestep":
            return {"error": "tags is required"}

        seed = None
        if model == "acestep":
            duration = float(payload.get("max_audio_length_ms", -1000)) / 1000
            task_type = payload.get("task_type", "text2music")
            seed = pick_seed(payload)
            call = _generator(model).spawn(
                caption=tags,
                lyrics="" if instrumental else lyrics,
                instrumental=instrumental or not lyrics,
                duration=min(600.0, duration) if duration > 0 else -1.0,
                bpm=int(payload["bpm"]) if payload.get("bpm") else None,
                keyscale=payload.get("keyscale", ""),
                timesignature=str(payload.get("timesignature", "")),
                task_type=task_type,
                src_audio=_b64(payload, "src_audio_b64"),
                src_audio_name=payload.get("src_audio_name", "src.mp3"),
                reference_audio=_b64(payload, "ref_audio_b64"),
                reference_audio_name=payload.get("ref_audio_name", "ref.mp3"),
                audio_cover_strength=cover_strength(payload, task_type),
                repainting_start=float(payload.get("repainting_start", 0.0)),
                repainting_end=float(payload.get("repainting_end", -1.0)),
                seed=seed,
                vocal_language=str(payload.get("vocal_language") or ""),
                inference_steps=int(payload.get("inference_steps") or 0),
                thinking=bool(payload.get("thinking", False)),
            )
        elif model == "music3":
            if not lyrics and not instrumental:
                return {"error": "lyrics are required for music3 (or set instrumental: true)"}
            seed = pick_seed(payload)
            kwargs = dict(
                prompt=tags,
                lyrics=lyrics,
                audio_duration=max(5.0, min(300.0, int(payload.get("max_audio_length_ms", 60_000)) / 1000)),
                seed=seed,
                instrumental=instrumental,
            )
            ref = _b64(payload, "ref_audio_b64")
            if ref:
                kwargs.update(
                    ref_audio=ref,
                    ref_audio_name=payload.get("ref_audio_name", "ref.wav"),
                    ref_strength=float(payload.get("ref_strength", 0.3)),
                    ref_tile=bool(payload.get("ref_tile", False)),
                )
            call = _generator(model).spawn(**kwargs)
        else:
            if not lyrics:
                return {"error": "lyrics are required for heartmula"}
            call = _generator(model).spawn(
                lyrics=lyrics,
                tags=tags,
                max_audio_length_ms=max(10_000, min(240_000, int(payload.get("max_audio_length_ms", 240_000)))),
            )
        return {"call_id": call.object_id, **({"seed": seed} if seed is not None else {})}

    @api.post("/poll_song")
    async def poll_song(request: Request):
        payload, err = await authed_payload(request)
        if err:
            return err
        fc = modal.FunctionCall.from_id(payload.get("call_id", ""))
        try:
            data = fc.get(timeout=0)
        except TimeoutError:
            return {"status": "pending"}
        except Exception as e:  # remote failure or expired call
            return {"status": "error", "error": str(e)}
        return {"status": "done", "mp3_b64": base64.b64encode(data).decode()}

    return api
