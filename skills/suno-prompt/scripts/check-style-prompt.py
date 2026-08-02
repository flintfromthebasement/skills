#!/usr/bin/env python3
"""Validate a Suno style-prompt text file.

Usage:
  python3 scripts/check-style-prompt.py path/to/slug-style-prompt.txt
  python3 scripts/check-style-prompt.py path/to/slug-style-prompt.txt --json

Checks:
  - Style paragraph (everything before Title:/Weirdness:/etc.) ≤ 1000 chars
  - No markdown residue (* _ # ` - bullets)
  - Settings lines present (Title, Weirdness, Style Influence, Audio Influence)
  - Heuristic warning on capitalized multi-word proper-name patterns that look
    like artist drop-ins (high false-positive rate — advisory only)

Exit codes:
  0 — pass (warnings allowed)
  1 — hard failure (over limit, markdown, missing settings)
  2 — usage / file error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SETTING_KEYS = ("Title", "Weirdness", "Style Influence", "Audio Influence")
SETTING_RE = re.compile(
    r"^(Title|Weirdness|Style Influence|Audio Influence)\s*:",
    re.IGNORECASE | re.MULTILINE,
)
MD_PATTERNS = [
    (r"\*\*[^*]+\*\*", "bold **...**"),
    (r"(?<!\*)\*[^*\n]+\*(?!\*)", "italic *...*"),
    (r"`[^`]+`", "inline code"),
    (r"(?m)^#{1,6}\s", "markdown heading"),
    (r"(?m)^\s*[-*+]\s+\S", "markdown bullet"),
]


def split_prompt(text: str) -> tuple[str, dict[str, str]]:
    """Return (style_paragraph, settings_dict)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    style_lines: list[str] = []
    settings: dict[str, str] = {}
    in_settings = False

    for line in lines:
        m = re.match(
            r"^(Title|Weirdness|Style Influence|Audio Influence)\s*:\s*(.*)$",
            line.strip(),
            re.IGNORECASE,
        )
        if m:
            in_settings = True
            key = m.group(1).title()
            # Normalize key casing to canonical
            for canon in SETTING_KEYS:
                if canon.lower() == key.lower():
                    key = canon
                    break
            settings[key] = m.group(2).strip()
            continue
        if not in_settings:
            style_lines.append(line)

    # Trim trailing blank lines from style paragraph only
    style = "\n".join(style_lines).strip()
    return style, settings


def check(text: str) -> dict:
    style, settings = split_prompt(text)
    errors: list[str] = []
    warnings: list[str] = []

    n = len(style)
    if not style:
        errors.append("style paragraph is empty")
    elif n > 1000:
        errors.append(f"style paragraph is {n} chars (limit 1000; over by {n - 1000})")

    for pat, label in MD_PATTERNS:
        if re.search(pat, style):
            errors.append(f"markdown residue in style paragraph: {label}")

    for key in SETTING_KEYS:
        if key not in settings or not settings[key]:
            errors.append(f"missing settings line: {key}:")

    # Advisory: sequences of 2+ capitalized words that aren't at sentence start only
    # Very rough — "Rhodes" alone is fine; "Taylor Swift" is not.
    properish = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", style)
    # Allow common non-artist phrases
    allow = {
        "Audio Influence", "Style Influence", "British Invasion", "New Wave",
        "Hip Hop", "R B", "Drum Break", "Pedal Steel",
    }
    suspects = [p for p in properish if p not in allow]
    if suspects:
        warnings.append(
            "possible proper names in style paragraph (verify not artist names): "
            + ", ".join(sorted(set(suspects)))
        )

    if re.search(r"\bin the style of\b", style, re.I):
        warnings.append('phrase "in the style of" usually precedes an artist name — rewrite as genre/era')

    buzz = ["sonic landscape", "auditory journey", "soundscape", "aural tapestry"]
    for b in buzz:
        if b in style.lower():
            warnings.append(f'buzzword fluff: "{b}"')

    return {
        "style_chars": n,
        "style_paragraph": style,
        "settings": settings,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("prompt_file", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.prompt_file.is_file():
        print(f"error: file not found: {args.prompt_file}", file=sys.stderr)
        return 2

    text = args.prompt_file.read_text(encoding="utf-8", errors="replace")
    result = check(text)

    if args.json:
        # Don't dump full paragraph twice in boring way — include summary fields
        out = {
            "file": str(args.prompt_file),
            "style_chars": result["style_chars"],
            "settings": result["settings"],
            "errors": result["errors"],
            "warnings": result["warnings"],
            "ok": result["ok"],
        }
        print(json.dumps(out, indent=2))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"check-style-prompt: {args.prompt_file} — {status}")
        print(f"  style paragraph: {result['style_chars']} / 1000 chars")
        if result["settings"]:
            for k in SETTING_KEYS:
                v = result["settings"].get(k, "—")
                print(f"  {k}: {v}")
        for e in result["errors"]:
            print(f"  ERROR: {e}")
        for w in result["warnings"]:
            print(f"  WARN: {w}")
        if result["ok"] and not result["warnings"]:
            print("  clean.")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
