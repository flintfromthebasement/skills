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
                         ref_audio_b64?/ref_audio_name?
                music3:  ref_audio_b64?/ref_audio_name?, ref_strength?, ref_tile?}
               -> {call_id}
  /poll_song   {call_id} -> {status: pending|done|error, mp3_b64?, error?}

App names default to the ones in this folder; override with env vars on the secret
(MUSICGEN_MODAL_ACESTEP=app:Class, MUSICGEN_MODAL_MUSIC3=…, MUSICGEN_MODAL_HEARTMULA=…).
"""

import base64
import hmac
import os

import modal

app = modal.App("musicgen-gateway")
image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi[standard]")

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

    api = FastAPI()
    expected = os.environ["MUSICGEN_GATEWAY_TOKEN"]

    def authed(request: Request, payload: dict) -> bool:
        header = request.headers.get("authorization", "")
        token = payload.get("token") or (header[7:] if header.lower().startswith("bearer ") else "")
        return bool(token) and hmac.compare_digest(str(token), expected)

    @api.post("/submit_song")
    async def submit_song(request: Request) -> dict:
        payload = await request.json()
        if not authed(request, payload):
            return {"error": "unauthorized"}
        model = payload.get("model", "acestep")
        tags = (payload.get("tags") or "").strip()
        lyrics = (payload.get("lyrics") or "").strip()
        instrumental = bool(payload.get("instrumental", False))
        if model not in DEFAULTS:
            return {"error": f"unknown model: {model}"}
        if not tags and model != "acestep":
            return {"error": "tags is required"}

        if model == "acestep":
            call = _generator(model).spawn(
                caption=tags,
                lyrics="" if instrumental else lyrics,
                instrumental=instrumental or not lyrics,
                duration=float(payload.get("max_audio_length_ms", -1000)) / 1000,
                bpm=int(payload["bpm"]) if payload.get("bpm") else None,
                keyscale=payload.get("keyscale", ""),
                timesignature=str(payload.get("timesignature", "")),
                task_type=payload.get("task_type", "text2music"),
                src_audio=_b64(payload, "src_audio_b64"),
                src_audio_name=payload.get("src_audio_name", "src.mp3"),
                reference_audio=_b64(payload, "ref_audio_b64"),
                reference_audio_name=payload.get("ref_audio_name", "ref.mp3"),
                audio_cover_strength=float(payload.get("audio_cover_strength", 1.0)),
                repainting_start=float(payload.get("repainting_start", 0.0)),
                repainting_end=float(payload.get("repainting_end", -1.0)),
                seed=int(payload.get("seed", -1)),
            )
        elif model == "music3":
            if not lyrics and not instrumental:
                return {"error": "lyrics are required for music3 (or set instrumental: true)"}
            kwargs = dict(
                prompt=tags,
                lyrics=lyrics,
                audio_duration=max(5.0, min(300.0, int(payload.get("max_audio_length_ms", 60_000)) / 1000)),
                seed=int(payload.get("seed", 42)),
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
                max_audio_length_ms=int(payload.get("max_audio_length_ms", 240_000)),
            )
        return {"call_id": call.object_id}

    @api.post("/poll_song")
    async def poll_song(request: Request) -> dict:
        payload = await request.json()
        if not authed(request, payload):
            return {"error": "unauthorized"}
        fc = modal.FunctionCall.from_id(payload.get("call_id", ""))
        try:
            data = fc.get(timeout=0)
        except TimeoutError:
            return {"status": "pending"}
        except Exception as e:  # remote failure or expired call
            return {"status": "error", "error": str(e)}
        return {"status": "done", "mp3_b64": base64.b64encode(data).decode()}

    return api
