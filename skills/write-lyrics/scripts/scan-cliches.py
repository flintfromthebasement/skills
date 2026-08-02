#!/usr/bin/env python3
"""Scan a lyrics file against the write-lyrics cliché filter lists.

Usage:
  python3 scripts/scan-cliches.py path/to/lyrics.txt
  python3 scripts/scan-cliches.py path/to/lyrics.txt --json

Exit codes:
  0 — no hits (or only justified noise)
  1 — one or more flags
  2 — usage / file error

This is a dumb string scanner, not a judge. Hits are candidates to rewrite or
defend in craft notes — not automatic failures.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Keep lists in sync with references/cliche-filter.md (short machine-checkable subset).
STOCK_PHRASES = [
    "i can't live without you",
    "you are my everything",
    "together forever",
    "you make me whole",
    "my one and only",
    "you complete me",
    "lost without you",
    "heart of gold",
    "love at first sight",
    "you're my reason why",
    "chasing dreams",
    "feel the beat",
    "in my mind",
    "time will tell",
    "waiting for you",
    "burning desire",
    "under the stars",
    "broken heart",
    "never let you go",
    "hold me tight",
    "digital glow",
    "electric glow",
    "come what may",
    "hand in hand",
    "rise above",
    "tangled sheets",
    "whispered dreams",
]

LAZY_PAIRS = [
    ("fire", "desire"),
    ("love", "above"),
    ("heart", "start"),
    ("night", "light"),
    ("girl", "world"),
    ("cry", "die"),
    ("pain", "rain"),
    ("dream", "seem"),
    ("eyes", "skies"),
    ("you", "true"),
    ("baby", "crazy"),
    ("life", "wife"),
    ("mind", "find"),
    ("kiss", "bliss"),
    ("dance", "romance"),
    ("feel", "real"),
    ("fly", "high"),
    ("tear", "fear"),
    ("star", "far"),
    ("blue", "you"),
    ("town", "down"),
    ("all", "fall"),
]

RHYME_SHELF = {
    "know", "fast", "now", "go", "back", "down", "land", "way",
    "out", "light", "sound", "knew", "ground",
}

SCENERY_CONSTRUCTIONS = [
    r"\bthe ground\b",
    r"\bthe dark\b",
    r"\bthe world\b",
    r"\bthe door\b",
    r"\bthe fire\b",
    r"\bin the dark\b",
    r"\bin the fire\b",
]

SURFACE_TOKENS = [
    "neon lights", "neon cities", "neon", "echoes", "symphony", "shadows",
    "intertwined", "entwined", "spectral", "crimson", "soar", "pulse",
    "forever", "heaven", "mystery", "collide", "unfold",
]

COSMIC = {"stars", "fire", "sky", "skies", "rain", "light", "heaven"}

FIRST_PERSON_RUTS = [
    r"^i learned how to\b",
    r"^i still\b",
    r"^i never\b",
    r"^i know\b",
    r"^i want\b",
    r"^i'm scared of\b",
    r"^maybe i\b",
]

STRUCTURAL = [
    r"\blost in the \w+",
    r"\bi'm not scared of\b",
    r"\blet it \w+, let it \w+",
    r"\bmaybe \w+, maybe \w+",
    r"\bround and round\b",
    r"\bthings are changing\b",
    r"\bwe'll be okay\b",
]


def strip_brackets(text: str) -> str:
    """Drop [meta tags] so scanner focuses on sung lines."""
    return re.sub(r"\[[^\]]*\]", " ", text)


def line_end_word(line: str) -> str | None:
    # Drop trailing parenthetical ad-libs for end-rhyme checks.
    cleaned = re.sub(r"\([^)]*\)", "", line).strip()
    cleaned = re.sub(r"[^a-zA-Z'\s]", "", cleaned).strip().lower()
    if not cleaned:
        return None
    return cleaned.split()[-1].strip("'")


def scan(text: str) -> list[dict]:
    hits: list[dict] = []
    raw_lower = text.lower()
    body = strip_brackets(text)
    body_lower = body.lower()
    lines = body.splitlines()

    for phrase in STOCK_PHRASES:
        if phrase in body_lower:
            hits.append({"type": "stock_phrase", "match": phrase})

    for tok in SURFACE_TOKENS:
        # word-ish boundary for single tokens; substring for multi-word
        if " " in tok:
            if tok in body_lower:
                hits.append({"type": "surface_token", "match": tok})
        else:
            if re.search(rf"\b{re.escape(tok)}\b", body_lower):
                hits.append({"type": "surface_token", "match": tok})

    for pat in SCENERY_CONSTRUCTIONS:
        for m in re.finditer(pat, body_lower):
            hits.append({"type": "scenery_construction", "match": m.group(0)})

    for pat in STRUCTURAL:
        for m in re.finditer(pat, body_lower):
            hits.append({"type": "structural_device", "match": m.group(0)})

    # End-rhyme lazy pairs: consecutive non-empty sung lines
    end_words: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        w = line_end_word(line)
        if w:
            end_words.append((i, w))
            if w in RHYME_SHELF:
                hits.append({"type": "rhyme_shelf", "match": w, "line": i})

    for (i1, w1), (i2, w2) in zip(end_words, end_words[1:]):
        pair = (w1, w2)
        rev = (w2, w1)
        if pair in LAZY_PAIRS or rev in LAZY_PAIRS:
            hits.append({
                "type": "lazy_rhyme_pair",
                "match": f"{w1}/{w2}",
                "lines": [i1, i2],
            })

    # Cosmic stacking across the whole lyric
    present = sorted(w for w in COSMIC if re.search(rf"\b{w}\b", body_lower))
    if len(present) >= 3:
        hits.append({"type": "cosmic_stack", "match": ", ".join(present)})

    # First-person rut: consecutive verse-ish lines opening the same way
    # (simple: any two consecutive non-empty lines matching rut patterns)
    openings: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        s = line.strip().lower()
        if not s:
            continue
        for pat in FIRST_PERSON_RUTS:
            m = re.match(pat, s)
            if m:
                openings.append((i, m.group(0)))
                break
    for (i1, o1), (i2, o2) in zip(openings, openings[1:]):
        if o1 == o2 and i2 == i1 + 1:
            hits.append({
                "type": "first_person_rut",
                "match": o1,
                "lines": [i1, i2],
            })

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for h in hits:
        key = (h["type"], h["match"], tuple(h.get("lines", [])), h.get("line"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    return unique


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lyrics", type=Path, help="Path to lyrics .txt file")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    if not args.lyrics.is_file():
        print(f"error: file not found: {args.lyrics}", file=sys.stderr)
        return 2

    text = args.lyrics.read_text(encoding="utf-8", errors="replace")
    hits = scan(text)

    if args.json:
        print(json.dumps({"file": str(args.lyrics), "hit_count": len(hits), "hits": hits}, indent=2))
    else:
        print(f"scan-cliches: {args.lyrics} — {len(hits)} flag(s)")
        if not hits:
            print("clean (no list hits). Still run the could-be-anyone test by ear.")
            return 0
        by_type: dict[str, list] = {}
        for h in hits:
            by_type.setdefault(h["type"], []).append(h)
        for t, group in by_type.items():
            print(f"\n[{t}] x{len(group)}")
            for h in group:
                extra = ""
                if "line" in h:
                    extra = f" (line {h['line']})"
                elif "lines" in h:
                    extra = f" (lines {h['lines'][0]}–{h['lines'][1]})"
                print(f"  - {h['match']}{extra}")
        print(
            "\nFlags are candidates. Rewrite, or keep with a one-line craft-note justification."
        )

    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
