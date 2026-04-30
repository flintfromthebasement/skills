#!/usr/bin/env python3
"""make-lyric-video — combine audio + video + timestamped lyrics into a subtitled music video.

Two-pass build:
  1. Composite (ffmpeg burns ASS into the picture, swaps in the supplied audio).
  2. Faststart remux (relocates moov atom to the front for streaming).

Splitting the passes means a crash in step 2 leaves step 1's output intact and
recoverable, instead of a corrupt MP4 with a missing moov atom.

Usage:
  make-lyric-video --audio song.mp3 --video footage.mp4 --lyrics lyrics.lrc --out final.mp4

Lyric formats: .lrc / .tsv / .json (auto-detected). See SKILL.md for the format details.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

GAP = 0.05  # seconds between subtitle ends and the next start, prevents flicker overlap
MIN_LINE_LEN = 0.6  # minimum on-screen time for a line, even when crowded

ASS_HEADER_TMPL = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,{font},{font_size},&H00F0EBE0,&H00FFFFFF,&H80000000,&HC0000000,1,0,0,0,100,100,0,0,1,2.4,3.0,2,80,80,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def parse_lrc(path):
    """Parse LRC timestamps. Returns [(start, end, text)] with end inferred from next start."""
    pat = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)")
    raw = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            m = pat.match(ln)
            if not m:
                continue
            mins, secs, text = m.groups()
            t = int(mins) * 60 + float(secs)
            text = text.strip()
            if text:
                raw.append((t, text))
    raw.sort(key=lambda r: r[0])
    out = []
    for i, (start, text) in enumerate(raw):
        end = raw[i + 1][0] - GAP if i + 1 < len(raw) else start + 5.0
        out.append((start, max(end, start + MIN_LINE_LEN), text))
    return out


def parse_tsv(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split("\t")
            if len(parts) < 3:
                continue
            try:
                start = float(parts[0])
                end = float(parts[1])
            except ValueError:
                continue
            text = "\t".join(parts[2:]).strip()
            if text:
                out.append((start, end, text))
    return out


def parse_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        sys.exit(f"{path}: expected a JSON array of {{start, end, text}} objects")
    out = []
    for d in data:
        out.append((float(d["start"]), float(d["end"]), str(d["text"])))
    return out


def parse_lyrics(path):
    p = str(path).lower()
    if p.endswith(".lrc"):
        return parse_lrc(path)
    if p.endswith(".tsv") or p.endswith(".tab"):
        return parse_tsv(path)
    if p.endswith(".json"):
        return parse_json(path)

    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("[") and "]" in s and re.match(r"\[\d+:", s):
                return parse_lrc(path)
            if s.startswith("[") or s.startswith("{"):
                return parse_json(path)
            if "\t" in s:
                return parse_tsv(path)
            break
    sys.exit(f"could not auto-detect lyric format for {path} — use a .lrc/.tsv/.json extension")


def fmt_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    sec = t % 60
    return f"{h:d}:{m:02d}:{sec:05.2f}"


def build_ass(rows, out_path, font, font_size):
    rows = sorted(rows, key=lambda r: r[0])
    rows = [list(r) for r in rows]
    for i in range(len(rows) - 1):
        if rows[i][1] > rows[i + 1][0] - GAP:
            rows[i][1] = max(rows[i][0] + MIN_LINE_LEN, rows[i + 1][0] - GAP)

    events = []
    for start, end, text in rows:
        text = text.replace("\n", "\\N")
        events.append(
            f"Dialogue: 0,{fmt_time(start)},{fmt_time(end)},Lyric,,0,0,0,,"
            f"{{\\fad(220,220)}}{text}"
        )
    body = ASS_HEADER_TMPL.format(font=font, font_size=font_size) + "\n".join(events) + "\n"
    out_path.write_text(body, encoding="utf-8")


def escape_ass_path(p):
    """Escape a filesystem path for ffmpeg's filtergraph syntax."""
    s = str(p)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", r"\:")
    s = s.replace("'", r"\'")
    return s


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def require(binary, hint):
    if shutil.which(binary) is None:
        sys.exit(f"required binary not on PATH: {binary} — {hint}")


def main():
    ap = argparse.ArgumentParser(
        description="Combine audio + video + timestamped lyrics → subtitled music video"
    )
    ap.add_argument("--audio", required=True, help="Audio file (mp3/wav/m4a/...)")
    ap.add_argument("--video", required=True, help="Video file at least as long as the audio")
    ap.add_argument("--lyrics", required=True, help="Timestamped lyrics: .lrc / .tsv / .json")
    ap.add_argument("--out", required=True, help="Output mp4 path")
    ap.add_argument("--font", default="Liberation Sans")
    ap.add_argument("--font-size", type=int, default=46)
    ap.add_argument("--crf", type=int, default=18, help="x264 CRF (lower = better, default 18)")
    ap.add_argument("--preset", default="medium", help="x264 preset (default medium)")
    ap.add_argument("--ass", help="Path for the generated .ass (default: alongside output, deleted after)")
    ap.add_argument("--keep-ass", action="store_true", help="Keep the generated .ass file")
    ap.add_argument("--no-faststart", action="store_true", help="Skip the faststart remux pass")
    args = ap.parse_args()

    require("ffmpeg", "install via your package manager (e.g. `sudo apt install ffmpeg`)")
    require("ffprobe", "ships with ffmpeg")

    audio = Path(args.audio).resolve()
    video = Path(args.video).resolve()
    lyrics = Path(args.lyrics).resolve()
    out = Path(args.out).resolve()

    for p in (audio, video, lyrics):
        if not p.exists():
            sys.exit(f"missing input: {p}")

    out.parent.mkdir(parents=True, exist_ok=True)

    rows = parse_lyrics(lyrics)
    if not rows:
        sys.exit(f"no lyric lines parsed from {lyrics}")
    print(f"parsed {len(rows)} lyric lines (first: {rows[0][0]:.2f}s, last: {rows[-1][0]:.2f}s)")

    ass_path = Path(args.ass).resolve() if args.ass else out.with_suffix(".ass")
    build_ass(rows, ass_path, args.font, args.font_size)
    print(f"wrote {ass_path}")

    tmp = out.with_suffix(".tmp.mp4")
    filter_str = f"ass={escape_ass_path(ass_path)}"

    run([
        "ffmpeg", "-y", "-loglevel", "error", "-stats",
        "-i", str(video),
        "-i", str(audio),
        "-vf", filter_str,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264",
        "-crf", str(args.crf),
        "-preset", args.preset,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(tmp),
    ])

    if args.no_faststart:
        os.replace(tmp, out)
    else:
        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(tmp),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out),
        ])
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass

    if not args.keep_ass and not args.ass:
        try:
            ass_path.unlink()
        except FileNotFoundError:
            pass

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"done: {out} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
