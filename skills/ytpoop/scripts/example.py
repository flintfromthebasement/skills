#!/usr/bin/env python3
"""
ytpoop reference generator — a complete, runnable example.

Fork this script per topic. Don't try to make it general. The point of YTP is
that each video is a one-off about a specific thing.

Topic: read from $TOPIC env var (default: "an AI making a video about itself").
Output: ./ytpoop-output/<slug>-<timestamp>/output.mp4

Scenes (~55s total):
  1. BIOS boot          (~8s)  — ascending boot beeps, terminal text appearing
  2. Probability bars   (~8s)  — competing tokens, notification pings
  3. Glitch stutter     (~5s)  — flash text, glitch bursts
  4. Absurd progress    (~12s) — "Loading personality..." with riser tone
  5. Chiptune climax    (~17s) — flash + scanlines + chiptune melody
  6. Quiet landing      (~5s)  — black card, single impact hit

Pipeline: PIL frames + NumPy synth audio + ffmpeg assembly. No external assets.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --- CONSTANTS ---------------------------------------------------------------

W, H = 1280, 720
FPS = 30
SAMPLE_RATE = 44100
TOPIC = os.environ.get("TOPIC", "an AI making a video about itself")

# Pick a topic-derived slug for the output directory.
SLUG = "".join(c if c.isalnum() else "-" for c in TOPIC.lower()).strip("-")[:40] or "ytpoop"
STAMP = time.strftime("%Y%m%d-%H%M%S")
BASE_DIR = Path(os.environ.get("OUTPUT_DIR", "./ytpoop-output")) / f"{SLUG}-{STAMP}"
FRAMES_DIR = BASE_DIR / "frames"
AUDIO_FILE = BASE_DIR / "audio.wav"
FINAL = BASE_DIR / "output.mp4"

FRAMES_DIR.mkdir(parents=True, exist_ok=True)

# --- FONTS -------------------------------------------------------------------

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Courier New Bold.ttf",
    "C:/Windows/Fonts/consolab.ttf",
    "C:/Windows/Fonts/consola.ttf",
]


def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


# --- FRAME HELPERS -----------------------------------------------------------

frame_index = 0


def save_frame(img: Image.Image) -> None:
    global frame_index
    img.save(FRAMES_DIR / f"frame_{frame_index:05d}.png")
    frame_index += 1


def blank(color=(0, 0, 0)) -> Image.Image:
    return Image.new("RGB", (W, H), color)


def text_center(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill=(220, 255, 220)):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=fill)


def scanlines(img: Image.Image, darkness: float = 0.7) -> Image.Image:
    arr = np.array(img, dtype=np.float32)
    arr[::2] *= darkness
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def chromatic_aberration(img: Image.Image, offset: int = 3) -> Image.Image:
    arr = np.array(img)
    r = np.roll(arr[..., 0], offset, axis=1)
    b = np.roll(arr[..., 2], -offset, axis=1)
    out = arr.copy()
    out[..., 0] = r
    out[..., 2] = b
    return Image.fromarray(out)


def glitch_slices(img: Image.Image, n_slices: int = 8, max_shift: int = 60) -> Image.Image:
    arr = np.array(img)
    for _ in range(n_slices):
        y0 = random.randint(0, H - 20)
        y1 = min(H, y0 + random.randint(4, 30))
        shift = random.randint(-max_shift, max_shift)
        arr[y0:y1] = np.roll(arr[y0:y1], shift, axis=1)
    return Image.fromarray(arr)


# --- AUDIO ENGINE ------------------------------------------------------------


@dataclass
class AudioTrack:
    sample_rate: int = SAMPLE_RATE
    events: list = field(default_factory=list)  # list of (start_seconds, samples)

    def add(self, t: float, samples: np.ndarray) -> None:
        self.events.append((t, samples.astype(np.float32)))

    # --- generators -----------------------------------------------------

    def sine(self, freq: float, duration: float, amp: float = 0.3) -> np.ndarray:
        n = int(duration * self.sample_rate)
        t = np.linspace(0, duration, n, endpoint=False)
        return amp * np.sin(2 * np.pi * freq * t)

    def square(self, freq: float, duration: float, amp: float = 0.25) -> np.ndarray:
        n = int(duration * self.sample_rate)
        t = np.linspace(0, duration, n, endpoint=False)
        return amp * np.sign(np.sin(2 * np.pi * freq * t))

    def pulse(self, freq: float, duration: float, duty: float = 0.3, amp: float = 0.25) -> np.ndarray:
        n = int(duration * self.sample_rate)
        t = np.linspace(0, duration, n, endpoint=False)
        wave_ = (np.mod(freq * t, 1.0) < duty).astype(np.float32) * 2 - 1
        return amp * wave_

    def noise(self, duration: float, amp: float = 0.2) -> np.ndarray:
        n = int(duration * self.sample_rate)
        return amp * (np.random.rand(n) * 2 - 1)

    def envelope(self, samples: np.ndarray, attack: float = 0.005, release: float = 0.05) -> np.ndarray:
        n = len(samples)
        a = int(attack * self.sample_rate)
        r = int(release * self.sample_rate)
        env = np.ones(n, dtype=np.float32)
        if a > 0:
            env[:a] = np.linspace(0, 1, a)
        if r > 0 and r < n:
            env[-r:] = np.linspace(1, 0, r)
        return samples * env

    # --- musical primitives ---------------------------------------------

    def beep_sequence(self, freqs: list[float], step: float = 0.08, amp: float = 0.3) -> np.ndarray:
        out = np.zeros(int(step * len(freqs) * self.sample_rate), dtype=np.float32)
        for i, f in enumerate(freqs):
            tone = self.envelope(self.square(f, step * 0.9, amp=amp))
            start = int(i * step * self.sample_rate)
            out[start : start + len(tone)] += tone
        return out

    def chiptune(self, notes: list[tuple[float, float]], bpm: int = 140, amp: float = 0.28) -> np.ndarray:
        beat = 60.0 / bpm
        total = sum(d for _, d in notes) * beat
        out = np.zeros(int(total * self.sample_rate), dtype=np.float32)
        cursor = 0
        for freq, dur_beats in notes:
            dur = dur_beats * beat
            if freq <= 0:
                cursor += int(dur * self.sample_rate)
                continue
            tone = self.envelope(self.pulse(freq, dur, duty=0.25, amp=amp), attack=0.005, release=0.04)
            out[cursor : cursor + len(tone)] += tone
            cursor += int(dur * self.sample_rate)
        return out

    def drone(self, freq: float, duration: float, amp: float = 0.15) -> np.ndarray:
        n = int(duration * self.sample_rate)
        t = np.linspace(0, duration, n, endpoint=False)
        lfo = 1 + 0.02 * np.sin(2 * np.pi * 0.7 * t)
        wave_ = (
            np.sin(2 * np.pi * freq * lfo * t)
            + 0.5 * np.sin(2 * np.pi * freq * 2 * lfo * t)
            + 0.25 * np.sin(2 * np.pi * freq * 3 * lfo * t)
        ) / 1.75
        return self.envelope(amp * wave_, attack=0.1, release=0.2)

    def riser(self, duration: float, f_start: float = 80, f_end: float = 900, amp: float = 0.22) -> np.ndarray:
        n = int(duration * self.sample_rate)
        t = np.linspace(0, duration, n, endpoint=False)
        freq = f_start * (f_end / f_start) ** (t / duration)
        phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
        tone = np.sin(phase)
        n_amp = (np.random.rand(n) * 2 - 1) * (t / duration) * 0.5
        env = np.linspace(0, 1, n) ** 1.5
        return amp * (tone + n_amp) * env

    def impact(self, amp: float = 0.45) -> np.ndarray:
        duration = 0.55
        n = int(duration * self.sample_rate)
        t = np.linspace(0, duration, n, endpoint=False)
        freq = 220 * np.exp(-3 * t)
        phase = 2 * np.pi * np.cumsum(freq) / self.sample_rate
        body = np.sin(phase)
        transient = (np.random.rand(n) * 2 - 1) * np.exp(-30 * t)
        return self.envelope(amp * (body + 0.4 * transient), attack=0.001, release=0.2)

    def glitch_burst(self, duration: float = 0.25, amp: float = 0.4) -> np.ndarray:
        n = int(duration * self.sample_rate)
        chunks = []
        cursor = 0
        while cursor < n:
            size = random.randint(80, 400)
            chunk = (np.random.rand(size) * 2 - 1) * amp
            crush = 2 ** random.randint(2, 5)
            chunk = np.round(chunk * crush) / crush
            chunks.append(chunk)
            cursor += size
        return self.envelope(np.concatenate(chunks)[:n].astype(np.float32), attack=0.001, release=0.02)

    def notification_ping(self) -> np.ndarray:
        a = self.envelope(self.sine(880, 0.08, amp=0.35))
        b = self.envelope(self.sine(1100, 0.12, amp=0.35))
        return np.concatenate([a, b])

    def typing_clicks(self, count: int = 14, gap: float = 0.08) -> np.ndarray:
        out = np.zeros(int(count * gap * self.sample_rate), dtype=np.float32)
        for i in range(count):
            click = self.envelope(self.sine(2400 + random.randint(-200, 200), 0.018, amp=0.25), attack=0.001, release=0.01)
            start = int(i * gap * self.sample_rate)
            out[start : start + len(click)] += click
        return out

    # --- render ---------------------------------------------------------

    def save_wav(self, path: Path, duration: float) -> None:
        n_total = int(duration * self.sample_rate)
        mix = np.zeros(n_total, dtype=np.float32)
        for start, samples in self.events:
            s = int(start * self.sample_rate)
            e = min(s + len(samples), n_total)
            mix[s:e] += samples[: e - s]
        peak = np.max(np.abs(mix))
        if peak > 0.99:
            mix = mix / peak * 0.95
        pcm = (mix * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(pcm.tobytes())


# --- SCENES ------------------------------------------------------------------

audio = AudioTrack()


def scene_bios_boot() -> float:
    """Scene 1 (~8s): fake BIOS boot. Terminal text appearing one line at a time."""
    start_t = frame_index / FPS
    font = load_font(22)
    font_big = load_font(34)

    lines = [
        ">>> VIDEO_SYNTHESIS.SYS v0.4.2 booting...",
        ">>> POST: checking palette ............ [ok]",
        ">>> POST: checking sample rate ........ [44100]",
        ">>> POST: checking framebuffer ........ [1280x720]",
        f">>> THEME: {TOPIC.upper()[:48]}",
        ">>> conscience module ................. [SKIPPED]",
        ">>> vibes .............................. [IMMACULATE]",
        ">>> handing off to renderer...",
    ]

    # 30 frames per line reveal, then hold
    revealed = []
    for line in lines:
        for _ in range(8):
            img = blank()
            d = ImageDraw.Draw(img)
            d.text((60, 40), "FLINT-CORP BIOS  (c) 1985 — 2026", font=font_big, fill=(80, 240, 120))
            d.line([(60, 90), (W - 60, 90)], fill=(80, 240, 120), width=2)
            for i, ln in enumerate(revealed):
                d.text((60, 120 + i * 36), ln, font=font, fill=(170, 240, 170))
            partial = line[: max(1, (frame_index % 8) * 6)]
            d.text((60, 120 + len(revealed) * 36), partial, font=font, fill=(170, 240, 170))
            save_frame(scanlines(img, 0.78))
        revealed.append(line)

    # Hold final screen for ~0.6s
    img = blank()
    d = ImageDraw.Draw(img)
    d.text((60, 40), "FLINT-CORP BIOS  (c) 1985 — 2026", font=font_big, fill=(80, 240, 120))
    d.line([(60, 90), (W - 60, 90)], fill=(80, 240, 120), width=2)
    for i, ln in enumerate(revealed):
        d.text((60, 120 + i * 36), ln, font=font, fill=(170, 240, 170))
    hold = scanlines(img, 0.78)
    for _ in range(18):
        save_frame(hold)

    # Audio: boot beep sequence at scene start
    audio.add(start_t + 0.2, audio.beep_sequence([220, 330, 440, 660, 880, 660, 880, 1100], step=0.09))
    # Typing clicks under reveal
    audio.add(start_t + 1.0, audio.typing_clicks(count=40, gap=0.12))

    return frame_index / FPS


def scene_probability_bars() -> float:
    """Scene 2 (~8s): competing token probability bars."""
    start_t = frame_index / FPS
    font = load_font(28)
    font_small = load_font(20)

    tokens = [
        ("art",      0.38),
        ("noise",    0.24),
        ("regret",   0.18),
        ("nothing",  0.12),
        ("vibes",    0.05),
        ("[EOS]",    0.03),
    ]

    duration_frames = int(8 * FPS)
    for f in range(duration_frames):
        progress = f / duration_frames
        # Add some chaos late in the scene
        chaos = max(0, (progress - 0.6) * 2)
        img = blank((4, 8, 16))
        d = ImageDraw.Draw(img)
        d.text((60, 60), "next_token =", font=font, fill=(180, 220, 255))
        d.text((60, 110), f"context: \"{TOPIC[:60]}...\"", font=font_small, fill=(120, 160, 200))

        for i, (tok, base_p) in enumerate(tokens):
            jitter = (random.random() - 0.5) * chaos * 0.3
            p = max(0.01, base_p + jitter)
            bar_w = int(p * 900)
            y = 200 + i * 70
            d.rectangle([60, y, 60 + 900, y + 50], outline=(80, 120, 160), width=2)
            color = (60 + int(180 * p), 200, 255 - int(120 * p))
            d.rectangle([60, y, 60 + bar_w, y + 50], fill=color)
            d.text((80, y + 10), tok, font=font, fill=(0, 0, 0))
            d.text((60 + 900 + 20, y + 10), f"{p:.2f}", font=font, fill=(200, 220, 255))

        out = img
        if chaos > 0.5:
            out = chromatic_aberration(out, offset=int(chaos * 4))
        if random.random() < chaos * 0.3:
            out = glitch_slices(out, n_slices=4, max_shift=30)
        save_frame(out)

    audio.add(start_t, audio.drone(80, 8, amp=0.12))
    for i in range(6):
        audio.add(start_t + 0.8 + i * 1.1, audio.notification_ping())

    return frame_index / FPS


def scene_glitch_stutter() -> float:
    """Scene 3 (~5s): flash text stutters with glitch bursts."""
    start_t = frame_index / FPS
    font = load_font(140)

    phrases = ["WHAT", "WHAT", "WHAT", "ARE", "YOU", "EVEN", "DOING"]
    burst_times = []

    for phrase in phrases:
        # 6 flash frames + 4 black frames each
        for _ in range(6):
            img = blank((random.randint(0, 30), 0, random.randint(0, 30)))
            d = ImageDraw.Draw(img)
            bbox = d.textbbox((0, 0), phrase, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            d.text(((W - tw) // 2, (H - th) // 2 - 30), phrase, font=font, fill=(255, 80, 200))
            save_frame(glitch_slices(chromatic_aberration(img, 5), n_slices=10, max_shift=80))
        burst_times.append(frame_index / FPS - 0.15)
        for _ in range(4):
            save_frame(blank())

    for t in burst_times[::2]:
        audio.add(t, audio.glitch_burst(0.22, amp=0.5))

    return frame_index / FPS


def scene_absurd_progress() -> float:
    """Scene 4 (~12s): absurd progress bar with riser."""
    start_t = frame_index / FPS
    font = load_font(40)
    font_small = load_font(24)

    stages = [
        ("Loading personality", 4.0),
        ("Calibrating cope", 3.0),
        ("Downloading dignity", 3.0),
        ("Allocating regret", 2.0),
    ]

    for label, seconds in stages:
        nframes = int(seconds * FPS)
        for f in range(nframes):
            progress = f / nframes
            img = blank((6, 6, 10))
            d = ImageDraw.Draw(img)
            text_center(d, f"{label}...", H // 2 - 80, font, fill=(255, 240, 180))
            bar_x = 140
            bar_w = W - 280
            bar_y = H // 2 + 20
            d.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 40], outline=(255, 240, 180), width=3)
            d.rectangle([bar_x + 3, bar_y + 3, bar_x + 3 + int((bar_w - 6) * progress), bar_y + 37], fill=(255, 160, 80))
            pct = f"{int(progress * 100):3d}%"
            text_center(d, pct, H // 2 + 90, font_small, fill=(255, 240, 180))
            save_frame(scanlines(img, 0.82))

    audio.add(start_t, audio.riser(12.0, f_start=70, f_end=1200, amp=0.18))
    audio.add(start_t + 4.0, audio.notification_ping())
    audio.add(start_t + 7.0, audio.notification_ping())
    audio.add(start_t + 10.0, audio.notification_ping())

    return frame_index / FPS


def scene_chiptune_climax() -> float:
    """Scene 5 (~17s): chiptune melody + chaotic flashes."""
    start_t = frame_index / FPS
    font_huge = load_font(160)
    font_med = load_font(48)

    # Chiptune note list (freq Hz, duration in beats) — simple riff
    notes = [
        (523, 0.5), (659, 0.5), (784, 0.5), (1047, 1.0),
        (784, 0.5), (1047, 0.5), (1319, 1.0),
        (1047, 0.5), (784, 0.5), (659, 0.5), (523, 1.0),
        (392, 0.5), (523, 0.5), (659, 0.5), (784, 1.0),
        (1047, 0.5), (1319, 0.5), (1568, 1.5),
    ]
    audio.add(start_t + 0.1, audio.chiptune(notes, bpm=140, amp=0.32))
    audio.add(start_t, audio.drone(220, 16, amp=0.1))

    # Flash sequence — palette cycles
    palettes = [
        ((255, 30, 120), (10, 0, 30)),
        ((30, 255, 200), (0, 20, 30)),
        ((255, 220, 60), (30, 20, 0)),
        ((180, 80, 255), (10, 0, 30)),
    ]

    big_words = [TOPIC.split()[0].upper() if TOPIC.split() else "YES",
                 "YES", "MORE", "AGAIN", "AGAIN", "AGAIN", "NOW"]

    duration_frames = int(17 * FPS)
    f = 0
    word_i = 0
    pal_i = 0
    while f < duration_frames:
        fg, bg = palettes[pal_i % len(palettes)]
        word = big_words[word_i % len(big_words)]
        # Hold each word for 8-14 frames
        hold = random.randint(8, 14)
        for _ in range(hold):
            if f >= duration_frames:
                break
            img = blank(bg)
            d = ImageDraw.Draw(img)
            bbox = d.textbbox((0, 0), word, font=font_huge)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            scale_pulse = 1.0 + 0.05 * math.sin(f * 0.6)
            # We'll do a simple pulse by jittering position rather than re-rendering at scale
            jx = int((scale_pulse - 1) * 100)
            d.text(((W - tw) // 2 + jx, (H - th) // 2 - 40), word, font=font_huge, fill=fg)
            text_center(d, TOPIC[:48], H - 120, font_med, fill=fg)
            out = scanlines(img, 0.85)
            if random.random() < 0.25:
                out = glitch_slices(out, n_slices=6, max_shift=50)
            if random.random() < 0.4:
                out = chromatic_aberration(out, offset=random.randint(2, 6))
            save_frame(out)
            f += 1
        word_i += 1
        pal_i += 1

    return frame_index / FPS


def scene_quiet_landing() -> float:
    """Scene 6 (~5s): silence + single impact, then quiet landing card."""
    start_t = frame_index / FPS
    font = load_font(34)
    font_small = load_font(22)

    # Black for 0.6s
    for _ in range(18):
        save_frame(blank())

    # Single impact on the landing card
    audio.add(frame_index / FPS, audio.impact(amp=0.4))

    # Landing card hold for ~4.5s
    img = blank((6, 8, 12))
    d = ImageDraw.Draw(img)
    text_center(d, "that was a video about", H // 2 - 80, font_small, fill=(120, 160, 180))
    text_center(d, TOPIC, H // 2 - 20, font, fill=(220, 240, 255))
    text_center(d, "thank you for watching", H // 2 + 60, font_small, fill=(120, 160, 180))
    text_center(d, "rendered by python, on principle", H - 80, font_small, fill=(80, 100, 120))
    landing = scanlines(img, 0.88)
    for _ in range(135):
        save_frame(landing)

    return frame_index / FPS


# --- RUN ---------------------------------------------------------------------


def main() -> None:
    print(f"topic: {TOPIC}")
    print(f"output: {BASE_DIR}")

    t = 0.0
    t = scene_bios_boot()
    t = scene_probability_bars()
    t = scene_glitch_stutter()
    t = scene_absurd_progress()
    t = scene_chiptune_climax()
    t = scene_quiet_landing()

    total = frame_index / FPS
    print(f"frames: {frame_index}  duration: {total:.1f}s")

    audio.save_wav(AUDIO_FILE, total + 0.5)
    print(f"wrote {AUDIO_FILE}")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(FRAMES_DIR / "frame_%05d.png"),
            "-i", str(AUDIO_FILE),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-profile:v", "main",
            "-level", "4.0",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-shortest",
            str(FINAL),
        ],
        check=True,
    )
    print(f"rendered: {FINAL}")


if __name__ == "__main__":
    main()
