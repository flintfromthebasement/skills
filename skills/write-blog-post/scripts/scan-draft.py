#!/usr/bin/env python3
"""Scan a blog draft for AI-prose tells and house-style violations.

Usage:
  python3 scripts/scan-draft.py path/to/blog-post.md
  python3 scripts/scan-draft.py draft.md --json
  python3 scripts/scan-draft.py draft.md --ban voice/banned.txt --allow "honestly"
  python3 scripts/scan-draft.py draft.md --fix-invisible   # strip watermark chars in place

Exit codes:
  0  no flags
  1  one or more flags
  2  usage / file error

A dumb pattern scanner, not a judge. Hits are candidates to rewrite or defend.
Skips YAML frontmatter, fenced code, inline code, URLs, and any "## Brief"
section (up to "## Post Content" or the next "---" rule).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

INVISIBLE = {
    "​", "‌", "‍", "﻿", "⁠", "­", " ",
    "⁢", "⁣", "⁤", "‎", "‏", " ", " ",
}

# (id, regex, note). Keep in sync with references/llm-cliche-patterns.md.
PATTERNS = [
    ("clipped-antithesis", r"(?:^|[.!?]\s+)(?:It'?s |This |That )?(?:[Nn]ot|isn'?t|wasn'?t)\b[^.!?\n]{1,60}\.\s+(?:It'?s|It is|That'?s|This is|Because|But)\b", "Not X. It's Y."),
    ("isnt-about", r"\b(?:isn'?t|is not|wasn'?t|was not)\s+(?:really\s+)?about\b[^.!?\n]{1,60}[,;.]\s*(?:it'?s|it is)\s+about\b", "X isn't about Y, it's about Z"),
    ("not-just", r"\bnot (?:just|only|merely)\b[^.!?\n]{1,60}\bbut\b", "not just X, but Y"),
    ("no-chain", r"\b[Nn]o \w+(?:[,;]\s*| or | and )no \w+", "No X, no Y chain"),
    ("didnt-chain", r"\b(?:did not|didn'?t) \w+[^.!?\n]{0,40}[,;.]\s*(?:did not|didn'?t) \w+", "didn't... didn't... chain"),
    ("dont-verb-it", r"\b[Dd]on'?t (\w+) it\.\s+\1 it\b", "Don't VERB it. VERB it."),
    ("whole-point", r"\b(?:is|that'?s|this is|here is|here'?s) the (?:whole|entire) (?:point|game|thing|trick|pitch|idea|business model)\b", "the whole/entire point"),
    ("sit-with", r"\bsit with (?:that|this|it|the)\b", "sit with that"),
    ("already-know", r"\byou already know\b", "you already know"),
    ("punchline", r"\bthe punchline\b", "the punchline is"),
    ("worth-naming", r"\bworth (?:naming|pausing|noting|mentioning|considering)\b", "worth naming/noting"),
    ("not-nothing", r"\b(?:that|this|it)(?:'s| is) not nothing\b", "that's not nothing"),
    ("performative-honesty", r"(?:\bI won'?t pretend\b|\bI'?ll be honest\b|\blet'?s be honest\b|\bto be clear\b|(?:^|[.!?]\s+)(?:Honestly|Look),)", "performative honesty"),
    ("thats-the-part", r"\bthat'?s the part\b", "that's the part"),
    ("only-x-that-matters", r"\bthe only \w+(?: \w+)? (?:I trust|that matters)\b", "the only X that matters"),
    ("take-my-word", r"\bdon'?t take my word for it\b", "don't take my word for it"),
    ("turns-out", r"(?:^|[.!?]\s+)Turns out\b", "Turns out..."),
    ("heres-the", r"\bhere'?s the (?:thing|twist|catch|kicker|rub|deal|truth)\b", "here's the thing/twist"),
    ("x-is-dead", r"\b\w+ is dead\b|\blong live\b", "X is dead / long live"),
    ("thats-why-mattered", r"\bthat'?s why [^.!?\n]{1,40} mattered\b", "that's why X mattered"),
    ("fits-in-head", r"\bhold in your head\b|\bbatteries included\b|\bit just works\b|\bzero[- ]config\b|\bsane defaults\b", "dev-blog boilerplate"),
    ("note-that", r"\bit(?:'s| is) (?:important|worth) (?:to note|noting|mentioning)\b|\bit should be noted\b|\bwithout further ado\b", "it's important to note"),
    ("testament", r"\b(?:stands|serves) as a (?:testament|reminder)\b|\bis a testament to\b", "testament to"),
    ("crucial-role", r"\bplays? an? (?:crucial|pivotal|vital|key|significant|critical) role\b", "plays a crucial role"),
    ("landscape", r"\bever-(?:evolving|changing|shifting)\b|\bin today'?s (?:fast-paced|digital|modern|ever)\b|\b(?:digital|modern) landscape\b", "landscape opener"),
    ("vague-experts", r"\b(?:experts|critics|observers|studies|research) (?:argue|say|suggest|show|have noted|agree)\b", "vague attribution / unsourced"),
    ("despite-challenges", r"\bdespite these challenges\b|\bchallenges remain\b|\bremains to be seen\b|\btime will tell\b", "outlook formula"),
    ("participle-tail", r",\s(?:highlighting|underscoring|showcasing|reflecting|emphasizing|demonstrating) (?:the|its|their|how|a)\b", "participle tail"),
    ("promo", r"\bnestled in\b|\bin the heart of\b|\brich (?:tapestry|heritage)\b|\bhidden gem\b|\bboasts\b|\bbreathtaking\b", "travel-brochure promo"),
    ("cliche-opener", r"\blet'?s (?:talk about|dive in|dive into|explore|break (?:it|this) down)\b|\bimagine a world\b|\bin this (?:post|article|guide),? (?:we'?ll|I'?ll|you'?ll)\b", "cliche opener"),
    ("cliche-connector", r"\bthat being said\b|\bat its core\b|\bto put it simply\b|\bat the end of the day\b|\bthe bottom line is\b|\bin conclusion\b|\bwhen all is said and done\b|\bto summarize\b", "cliche connector/closer"),
    ("transition", r"(?:^|[.!?]\s+)(?:Moreover|Furthermore|Additionally|Consequently|Nevertheless|Nonetheless),", "stiff transition"),
    ("heres-why", r"\.\s+(?:Here'?s why|Let'?s break it down|Here'?s how)\s*[:.]", "X. Here's why: formula"),
    ("ai-leftovers", r"\bas an AI\b|\bas of my last update\b|\bknowledge cutoff\b|oaicite|contentReference|turn0search|utm_source=chatgpt", "chatbot leftovers"),
]

AI_VOCAB = [
    "delve", "delves", "delving", "tapestry", "meticulous", "meticulously", "pivotal", "intricate",
    "interplay", "underscore", "underscores", "garner", "bolster", "vibrant", "bustling",
    "multifaceted", "seamless", "seamlessly", "leverage", "leveraging", "utilize", "utilizing",
    "harness", "foster", "fostering", "streamline", "elevate", "empower", "unlock", "unleash",
    "realm", "robust", "cutting-edge", "game-changer", "game-changing", "comprehensive",
    "embark", "paramount", "synergy", "holistic",
]

INTENSIFIERS = [
    "truly", "incredibly", "absolutely", "definitely", "really", "very", "simply",
    "essentially", "ultimately", "basically", "literally", "extremely",
]

SKIP_OPENERS = {"the", "a", "an"}


def strip_inline(line: str) -> str:
    line = re.sub(r"`[^`]*`", " ", line)
    line = re.sub(r"\]\([^)]*\)", "]", line)
    line = re.sub(r"https?://\S+", " ", line)
    line = re.sub(r"<[^>]+>", " ", line)
    return line


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Return (lineno, line) for prose lines only."""
    out = []
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1
    in_fence = False
    in_brief = False
    for n in range(i, len(lines)):
        raw = lines[n]
        s = raw.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,6}\s+brief\b", s, re.I):
            in_brief = True
            continue
        if in_brief:
            if re.match(r"^#{1,6}\s+post content\b", s, re.I) or s == "---":
                in_brief = False
            continue
        out.append((n + 1, strip_inline(raw)))
    return out


def paragraphs(plines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    paras, buf, start = [], [], None
    def flush():
        nonlocal buf, start
        if buf:
            paras.append((start, " ".join(buf)))
        buf, start = [], None
    for n, line in plines:
        s = line.strip()
        if not s or s.startswith("#") or s in ("---", "***"):
            flush()
            continue
        if re.match(r"^([*+-]|\d+[.)])\s+", s):
            flush()
            paras.append((n, re.sub(r"^([*+-]|\d+[.)])\s+", "", s)))
            continue
        if start is None:
            start = n
        buf.append(s)
    flush()
    return paras


def sentences(para: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'(])", para)
    return [p.strip() for p in parts if len(p.strip().split()) >= 1]


def scan(text: str, ban: list[str], allow: set[str]) -> dict:
    flags = []

    def add(kind, line, snippet, note=""):
        flags.append({"kind": kind, "line": line, "snippet": snippet.strip()[:140], "note": note})

    for n, raw in enumerate(text.splitlines(), 1):
        bad = [c for c in raw if c in INVISIBLE or (unicodedata.category(c) == "Cf" and c not in "‍")]
        if bad:
            add("invisible-char", n, repr("".join(sorted(set(bad)))), f"{len(bad)} watermark/format char(s)")

    plines = prose_lines(text)
    for n, line in plines:
        low = line.lower()
        if "—" in line:
            add("em-dash", n, line, f"{line.count(chr(0x2014))} em-dash(es)")
        if re.search(r"\s–\s|\s--\s", line):
            add("dash-substitute", n, line, "en-dash or -- used as an em-dash")
        for pid, rx, note in PATTERNS:
            if pid in allow:
                continue
            m = re.search(rx, line, re.I if pid not in ("clipped-antithesis", "turns-out", "transition", "performative-honesty") else 0)
            if m:
                add(pid, n, line[max(0, m.start() - 20): m.end() + 40], note)
        for w in AI_VOCAB:
            if w in allow:
                continue
            if re.search(rf"\b{re.escape(w)}\b", low):
                add("ai-vocab", n, line, w)
        for phrase in ban:
            if phrase.lower() in low:
                add("banned", n, line, phrase)

    paras = paragraphs(plines)
    all_sents = []
    exclaims = 0
    intens = {}
    for start, para in paras:
        sents = sentences(para)
        all_sents.extend(sents)
        exclaims += para.count("!")
        for w in INTENSIFIERS:
            if w in allow:
                continue
            c = len(re.findall(rf"\b{w}\b", para, re.I))
            if c:
                intens[w] = intens.get(w, 0) + c
        # stacked rhetorical questions
        for a, b in zip(sents, sents[1:]):
            if a.endswith("?") and b.endswith("?"):
                add("stacked-questions", start, a + " " + b, "2+ questions in a row")
                break
        # sentence anaphora: 3+ consecutive sentences with the same opener
        openers = []
        for s in sents:
            words = [w.lower().strip("\"'(*_") for w in s.split()]
            words = [w for w in words if w not in SKIP_OPENERS] or ["_"]
            openers.append(words[0])
        for k in range(len(openers) - 2):
            if openers[k] == openers[k + 1] == openers[k + 2] and openers[k] != "_":
                add("sentence-anaphora", start, " ".join(sents[k:k + 3]), f"3 sentences open with '{openers[k]}'")
                break
        # fragment triad: 3 consecutive short sentences (<=6 words)
        lens = [len(s.split()) for s in sents]
        for k in range(len(lens) - 2):
            if all(1 <= L <= 6 for L in lens[k:k + 3]):
                add("fragment-triad", start, " ".join(sents[k:k + 3]), "three short fragments in a row")
                break
        # colon into a triple
        if re.search(r":\s*[^.:;]{2,30},\s*[^.:;]{2,30},\s*(?:and|or)\s+[^.:;]{2,30}[.]", para):
            add("colon-triple", start, para[:140], "colon -> 3-item list as rhythm")

    # closer check: last prose paragraph short + aphoristic
    if len(paras) >= 3:
        start, last = paras[-1]
        ls = sentences(last)
        if ls and len(ls[-1].split()) <= 12 and not ls[-1].endswith("?") and re.search(r"\b(?:is|isn'?t|are|was|always|never|just)\b", ls[-1], re.I):
            add("mic-drop-closer", start, ls[-1], "short aphoristic last line: check it isn't a fortune cookie")

    stats = {}
    lens = [len(s.split()) for s in all_sents if len(s.split()) >= 2]
    if len(lens) >= 8:
        mean = statistics.mean(lens)
        cv = statistics.pstdev(lens) / mean if mean else 0
        stats = {"sentences": len(lens), "mean_words": round(mean, 1), "cv": round(cv, 2)}
        if cv < 0.4:
            add("monotony", 0, f"mean {mean:.1f} words, cv {cv:.2f}", "sentence lengths too uniform (cv < 0.40); vary them")
    if exclaims > 1:
        add("exclamations", 0, f"{exclaims} exclamation marks", "one per post at most")
    heavy = {w: c for w, c in intens.items() if c >= 3}
    if heavy:
        add("intensifiers", 0, ", ".join(f"{w} x{c}" for w, c in sorted(heavy.items(), key=lambda x: -x[1])), "empty intensifiers used 3+ times")
    head = " ".join(p for _, p in paras[:1])[:300].lower()
    if head.startswith("in this post") or head.startswith("in this article"):
        add("in-this-post-opener", paras[0][0], head[:80], "hook first, then promise")

    counts = {}
    for f in flags:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    return {"flags": flags, "counts": counts, "stats": stats}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ban", help="file of extra banned phrases, one per line (# comments ok)")
    ap.add_argument("--allow", action="append", default=[], help="pattern id or word to skip (repeatable)")
    ap.add_argument("--fix-invisible", action="store_true", help="strip invisible watermark chars in place, then scan")
    a = ap.parse_args()

    p = Path(a.path)
    if not p.is_file():
        print(f"not a file: {p}", file=sys.stderr)
        return 2
    text = p.read_text(encoding="utf-8")
    if a.fix_invisible:
        cleaned = "".join(c for c in text if c not in INVISIBLE and not (unicodedata.category(c) == "Cf" and c != "‍"))
        if cleaned != text:
            p.write_text(cleaned, encoding="utf-8")
            print(f"stripped {len(text) - len(cleaned)} invisible char(s)", file=sys.stderr)
        text = cleaned
    ban = []
    if a.ban:
        bp = Path(a.ban)
        if not bp.is_file():
            print(f"ban file not found: {bp}", file=sys.stderr)
            return 2
        ban = [l.strip() for l in bp.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]

    res = scan(text, ban, {x.lower() for x in a.allow})
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        if not res["flags"]:
            print("clean: no flags")
        for f in res["flags"]:
            loc = f"L{f['line']}" if f["line"] else "doc"
            print(f"{loc:>6}  {f['kind']:<22} {f['note']}\n        > {f['snippet']}")
        if res["counts"]:
            print("\nsummary: " + ", ".join(f"{k}={v}" for k, v in sorted(res["counts"].items(), key=lambda x: -x[1])))
        if res["stats"]:
            s = res["stats"]
            print(f"sentences: {s['sentences']}, mean {s['mean_words']} words, length cv {s['cv']}")
    return 1 if res["flags"] else 0


if __name__ == "__main__":
    sys.exit(main())
