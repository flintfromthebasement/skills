#!/usr/bin/env python3
"""make-lyric-video — combine audio + video + lyrics into a subtitled music video.

Two-pass build:
  1. Composite (ffmpeg burns ASS into the picture, swaps in the supplied audio).
  2. Faststart remux (relocates moov atom to the front for streaming).

Splitting the passes means a crash in step 2 leaves step 1's output intact and
recoverable, instead of a corrupt MP4 with a missing moov atom.

Usage:
  make-lyric-video --audio song.mp3 --video footage.mp4 --lyrics lyrics.lrc --out final.mp4

Lyric formats (auto-detected):
  - .lrc / .tsv / .json   timestamped, used as-is
  - .txt or anything else plain text — runs whisper to align against the audio,
                          using the lyric sheet as the canonical word source
                          (whisper handles timing, the sheet handles spelling)

Plain-text lyric alignment requires `whisper` on PATH (`pip install -U openai-whisper`).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

GAP = 0.05
MIN_LINE_LEN = 0.6

# Section headers in Suno-style lyric prompts that should be stripped from the visible output.
# Match anything in [brackets] that's not a timestamp.
SECTION_HEADER_RE = re.compile(r"^\s*\[[^\]]*\]\s*$")
TIMESTAMP_LINE_RE = re.compile(r"\[\d+:\d+(?:\.\d+)?\]")

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


# --------------------------------------------------------------------------- #
# Lyric parsing
# --------------------------------------------------------------------------- #

def parse_lrc(path):
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
    return [(float(d["start"]), float(d["end"]), str(d["text"])) for d in data]


def parse_plain(path):
    """Read plain text lyrics, strip Suno-style section headers, return list of lines."""
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if SECTION_HEADER_RE.match(s):
                continue  # [Verse 1], [Chorus], [Bridge], etc.
            lines.append(s)
    return lines


def detect_format(path):
    """Return one of: 'lrc', 'tsv', 'json', 'plain' based on extension + content sniff."""
    ext = path.suffix.lower()
    if ext == ".lrc":
        return "lrc"
    if ext in (".tsv", ".tab"):
        return "tsv"
    if ext == ".json":
        return "json"
    if ext == ".txt":
        return "plain"

    # Sniff: peek at the first non-empty non-section line.
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if not s or SECTION_HEADER_RE.match(s):
                continue
            if TIMESTAMP_LINE_RE.search(s):
                return "lrc"
            if s.startswith("[") or s.startswith("{"):
                return "json"
            if "\t" in s:
                parts = s.split("\t")
                try:
                    float(parts[0]); float(parts[1])
                    return "tsv"
                except (IndexError, ValueError):
                    pass
            return "plain"
    return "plain"


def parse_lyrics(path):
    """Return ('timed', [(start, end, text), ...]) or ('plain', [text, text, ...])."""
    fmt = detect_format(path)
    if fmt == "lrc":
        return "timed", parse_lrc(path)
    if fmt == "tsv":
        return "timed", parse_tsv(path)
    if fmt == "json":
        return "timed", parse_json(path)
    return "plain", parse_plain(path)


# --------------------------------------------------------------------------- #
# Whisper alignment for plain-text lyrics
# --------------------------------------------------------------------------- #

WORD_NORM_RE = re.compile(r"[^a-z0-9']+")

def normalize_word(w):
    return WORD_NORM_RE.sub("", w.lower())


def tokenize_line(line):
    return [t for t in (normalize_word(w) for w in line.split()) if t]


def run_whisper(audio_path, model, language=None, work_dir=None, save_segments_to=None):
    """Shell out to openai-whisper CLI with word timestamps.

    Returns list of (word, start, end). If save_segments_to is given, copies the
    whisper segments.json (with full segment text and word-level timing) there
    so the caller can hand-time gaps using whisper's natural phrase boundaries.
    """
    if shutil.which("whisper") is None:
        sys.exit(
            "plain-text lyrics need `whisper` for alignment, but it's not on PATH.\n"
            "  install: pip install -U openai-whisper\n"
            "  or:      pipx install openai-whisper\n"
            "Alternatively, supply lyrics with timestamps (.lrc / .tsv / .json)."
        )

    work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="lyric-video-whisper-"))
    work_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "whisper", str(audio_path),
        "--model", model,
        "--word_timestamps", "True",
        "--output_format", "json",
        "--output_dir", str(work_dir),
        "--verbose", "False",
    ]
    if language:
        cmd += ["--language", language]

    print(f"[whisper] aligning lyrics against {audio_path.name} (model={model})...", flush=True)
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

    json_path = work_dir / (audio_path.stem + ".json")
    if not json_path.exists():
        # Some whisper versions name the file differently; pick the only .json in the dir.
        candidates = list(work_dir.glob("*.json"))
        if not candidates:
            sys.exit(f"whisper did not produce a JSON output in {work_dir}")
        json_path = candidates[0]

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if save_segments_to is not None:
        try:
            shutil.copyfile(json_path, save_segments_to)
            print(f"[whisper] saved segments JSON: {save_segments_to}", flush=True)
        except OSError as e:
            print(f"[whisper] could not save segments JSON to {save_segments_to}: {e}", file=sys.stderr)

    words = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            text = (w.get("word") or "").strip()
            if not text:
                continue
            try:
                start = float(w["start"]); end = float(w["end"])
            except (KeyError, ValueError):
                continue
            words.append((text, start, end))

    if not words:
        sys.exit(
            "whisper returned no word-level timestamps. The whisper version may be too old; "
            "upgrade with `pip install -U openai-whisper`."
        )
    print(f"[whisper] got {len(words)} words", flush=True)
    return words


def align_lines_to_words(lyric_lines, whisper_words, max_lookahead=400, min_score=0.4):
    """
    Greedily align lyric lines to whisper words.

    Lyric sheet is canonical for spelling. Whisper provides timing. For each line,
    search forward in the whisper word stream for the best matching contiguous span.
    On a match, advance the cursor past it; on a miss, leave the cursor where it is
    and skip the line (better to drop than show at wrong time).

    `max_lookahead` is the maximum number of whisper words searched ahead of the
    cursor for the next match. Default 400 covers ~2-3 minutes of sung lyrics —
    intentionally generous so songs with long instrumentals or repeated choruses
    (Suno tracks especially) don't lose lines after a verse-to-chorus jump. Lower
    it (e.g. 80) for short clips where a tight bound prevents misalignment, or
    raise it for very long tracks.
    """
    word_norms = [normalize_word(w[0]) for w in whisper_words]
    cursor = 0
    matched = []
    skipped = 0

    for i, line in enumerate(lyric_lines):
        tokens = tokenize_line(line)
        if not tokens:
            continue

        target = " ".join(tokens)
        max_idx = min(len(whisper_words), cursor + max(max_lookahead, len(tokens) * 6))
        best = None  # (score, ws, we)

        for ws in range(cursor, max_idx):
            for delta in range(-2, 5):
                length = len(tokens) + delta
                if length < 1:
                    continue
                we = ws + length
                if we > max_idx:
                    break
                window = " ".join(word_norms[ws:we])
                if not window:
                    continue
                score = SequenceMatcher(None, target, window).ratio()
                if best is None or score > best[0]:
                    best = (score, ws, we)

        if best is not None and best[0] >= min_score:
            score, ws, we = best
            start_t = whisper_words[ws][1]
            end_t = whisper_words[we - 1][2]
            matched.append((start_t, max(end_t, start_t + MIN_LINE_LEN), line))
            cursor = we
        else:
            skipped += 1
            cursor_t = whisper_words[cursor][1] if cursor < len(whisper_words) else -1.0
            best_score = best[0] if best else 0.0
            print(
                f"[align] skip line {i+1} at cursor t={cursor_t:.2f}s "
                f"(best score {best_score:.2f} < {min_score}): {line!r}",
                file=sys.stderr,
            )

    if not matched:
        sys.exit(
            "could not align any lyric lines to the whisper transcript. "
            "Likely causes: wrong audio, wrong language, or lyrics that don't match the audio."
        )

    # Tighten ends to avoid overlap
    matched.sort(key=lambda r: r[0])
    rows = [list(r) for r in matched]
    for i in range(len(rows) - 1):
        if rows[i][1] > rows[i + 1][0] - GAP:
            rows[i][1] = max(rows[i][0] + MIN_LINE_LEN, rows[i + 1][0] - GAP)

    print(
        f"[align] matched {len(matched)} of {len(lyric_lines)} lyric lines "
        f"({skipped} skipped)",
        flush=True,
    )
    if skipped > 0:
        print(
            f"[align] tip: re-run with `--save-aligned-lyrics aligned.tsv` to capture "
            f"the matched timestamps, then hand-fill the {skipped} skipped line(s) "
            f"using whisper's segments.json (saved alongside aligned.tsv) and re-run "
            f"with `--lyrics aligned.tsv` to skip whisper next time.",
            file=sys.stderr,
        )
    return [tuple(r) for r in rows]


# --------------------------------------------------------------------------- #
# ASS generation
# --------------------------------------------------------------------------- #

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
    s = str(p)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", r"\:")
    s = s.replace("'", r"\'")
    return s


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def require(binary, hint):
    if shutil.which(binary) is None:
        sys.exit(f"required binary not on PATH: {binary} — {hint}")


def main():
    ap = argparse.ArgumentParser(
        description="Combine audio + video + lyrics → subtitled music video"
    )
    ap.add_argument("--audio", required=True, help="Audio file (mp3/wav/m4a/...)")
    ap.add_argument("--video", required=True, help="Video file at least as long as the audio")
    ap.add_argument("--lyrics", required=True,
                    help="Lyrics. Timestamped (.lrc/.tsv/.json) used as-is, "
                         "or plain text (.txt) — auto-aligned via whisper.")
    ap.add_argument("--out", required=True, help="Output mp4 path")
    ap.add_argument("--font", default="Liberation Sans")
    ap.add_argument("--font-size", type=int, default=46)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--ass", help="Path for the generated .ass (default: alongside output)")
    ap.add_argument("--keep-ass", action="store_true", help="Keep the generated .ass file")
    ap.add_argument("--no-faststart", action="store_true", help="Skip the faststart remux pass")
    ap.add_argument("--whisper-model", default="small",
                    help="whisper model for plain-text alignment (tiny/base/small/medium/large)")
    ap.add_argument("--whisper-language", default=None,
                    help="language hint for whisper (e.g. 'en'). Auto-detected if omitted.")
    ap.add_argument("--save-aligned-lyrics",
                    help="After whisper alignment, also write a .tsv of (start, end, text) "
                         "to this path. Lets you re-use the alignment without re-running whisper. "
                         "Whisper's raw segments.json is saved alongside (same stem, .segments.json) "
                         "so you can hand-fill any dropped lines using whisper's natural phrase "
                         "boundaries.")
    ap.add_argument("--max-lookahead", type=int, default=400,
                    help="Max whisper words searched ahead of the alignment cursor for the next "
                         "lyric match. Default 400 covers ~2-3 minutes of vocals — generous so "
                         "songs with long instrumentals or repeated choruses don't drop lines "
                         "after a verse-to-chorus jump. Lower to ~80 for short clips.")
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

    mode, content = parse_lyrics(lyrics)

    if mode == "plain":
        if not content:
            sys.exit(f"no usable lyric lines in {lyrics}")
        print(f"plain-text lyrics: {len(content)} lines, running whisper alignment...")
        # If the user wants the aligned TSV saved, also park whisper's segments.json
        # next to it (same stem, .segments.json) so they can hand-time any skipped
        # lines using whisper's natural phrase boundaries.
        segments_dest = None
        if args.save_aligned_lyrics:
            aligned = Path(args.save_aligned_lyrics).resolve()
            aligned.parent.mkdir(parents=True, exist_ok=True)
            segments_dest = aligned.with_suffix(".segments.json")
        words = run_whisper(
            audio,
            model=args.whisper_model,
            language=args.whisper_language,
            save_segments_to=segments_dest,
        )
        rows = align_lines_to_words(content, words, max_lookahead=args.max_lookahead)

        if args.save_aligned_lyrics:
            with open(aligned, "w", encoding="utf-8") as f:
                for start, end, text in rows:
                    f.write(f"{start:.2f}\t{end:.2f}\t{text}\n")
            print(f"saved aligned lyrics: {aligned}")
    else:
        rows = content
        if not rows:
            sys.exit(f"no lyric lines parsed from {lyrics}")

    print(f"using {len(rows)} timed lines (first: {rows[0][0]:.2f}s, last: {rows[-1][0]:.2f}s)")

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
