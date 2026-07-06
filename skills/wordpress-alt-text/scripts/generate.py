#!/usr/bin/env python3
"""wordpress-alt-text — Stage 2 generation. NO site writes; reads/writes the local SQLite DB only.

Resumable: only processes rows with proposed_alt IS NULL (use --redo to regenerate).
Skips rows with status='excluded_private'.

Usage:
  python3 generate.py --db alt.db --tiers P1_content --limit 10      # sample first
  python3 generate.py --db alt.db --tiers P1_content,P2_featured,P3_orphan

Env: AI_API_KEY or OPENROUTER_API_KEY. Any OpenAI-compatible vision endpoint works via
--api-url/--model (default OpenRouter + google/gemini-3.1-flash-lite, ~$0.0004/image).
"""
import os, re, sys, json, base64, io, time, argparse, threading, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

MAXDIM = 768

PROMPT = """You write alt text for an image in a WordPress media library. Output ONE alt string.

Rules:
- Describe ONLY what is actually visible. Never invent brand names, people, logos, or screen text. If unsure, describe generically and accurately.
- Under 125 characters. Concise. No trailing period.
- Do NOT begin with "image of", "photo of", "picture of", "graphic of". Say "screenshot of" only when it is genuinely a software screenshot and that matters.
- Write for screen-reader users first: clear, factual, specific.
- Output ONLY the alt text. No quotes, no labels.

Context:
- Filename: {fname}
- Media title: {title}
- Caption: {caption}
- Appears on page(s): {pages}
"""

TRAIL = set("the a an and or for with of to in on at by from that this featuring showing".split())


def humanize(file):
    b = re.sub(r"\.\w+$", "", os.path.basename(file or ""))
    b = re.sub(r"-\d+x\d+$", "", b)
    b = re.sub(r"[-_]+", " ", b)
    b = re.sub(r"\b\d{3,}\b", "", b)
    return b.strip()


def clean_alt(s):
    s = (s or "").strip().strip('"').strip("'").strip()
    s = re.sub(r"^(alt(\s*text)?\s*[:\-]\s*)", "", s, flags=re.I)
    s = re.sub(r"^(image|photo|picture|graphic)\s+of\s+", "", s, flags=re.I)
    s = s.strip().rstrip(".")
    if len(s) > 125:
        s = s[:125].rsplit(" ", 1)[0]
    words = s.split()
    while words and re.sub(r"[^a-z]", "", words[-1].lower()) in TRAIL:
        words.pop()
    s = " ".join(words).strip().rstrip(",").strip()
    return (s[0].upper() + s[1:]) if s and s[0].islower() else s


def fetch_b64(url):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 alt-bot"})
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content))
    try:
        im.seek(0)
    except Exception:
        pass
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((MAXDIM, MAXDIM))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def call_model(b64, ctx, key, api_url, model):
    payload = {"model": model, "max_tokens": 120, "temperature": 0.4, "usage": {"include": True},
               "messages": [{"role": "user", "content": [
                   {"type": "text", "text": ctx},
                   {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]}
    last = ""
    for attempt in range(4):
        try:
            r = requests.post(api_url, headers={"Authorization": f"Bearer {key}"},
                              json=payload, timeout=90)
            if r.status_code in (429, 500, 502, 503):
                last = f"http {r.status_code}"
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            d = r.json()
            return d["choices"][0]["message"]["content"], (d.get("usage") or {}).get("cost", 0) or 0, ""
        except Exception as e:
            last = str(e)[:160]
            time.sleep(1.5 * (attempt + 1))
    return "", 0, last


lock = threading.Lock()


def worker(img, key, db_path, api_url, model):
    aid, url, file, title, caption, pages = img
    ctx = PROMPT.format(fname=humanize(file) or "(none)", title=title or "(none)",
                        caption=(caption or "(none)")[:160], pages=pages or "(not used on a page)")
    b64, ferr = None, ""
    try:
        b64 = fetch_b64(url)
    except Exception as e:
        ferr = f"fetch: {str(e)[:120]}"
    if ferr:
        alt, cost, merr = "", 0, ""
    else:
        raw, cost, merr = call_model(b64, ctx, key, api_url, model)
        alt = clean_alt(raw)
    with lock:
        db = sqlite3.connect(db_path, timeout=30)
        db.execute("UPDATE images SET proposed_alt=?, chars=?, needs_visual_review=?, "
                   "fetch_error=?, model_error=?, cost=?, status='generated' WHERE id=?",
                   (alt, len(alt or ""), 1 if (ferr or merr or not alt) else 0, ferr, merr, cost, aid))
        db.commit()
        db.close()
    return aid, alt, ferr or merr, cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="alt.db")
    ap.add_argument("--tiers", default="P1_content,P2_featured,P3_orphan")
    ap.add_argument("--ids", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--api-url", default="https://openrouter.ai/api/v1/chat/completions")
    ap.add_argument("--model", default="google/gemini-3.1-flash-lite")
    args = ap.parse_args()
    key = os.environ.get("AI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("set AI_API_KEY or OPENROUTER_API_KEY")

    db = sqlite3.connect(args.db)
    q = ("SELECT i.id, i.url, i.file, i.title, i.caption, "
         "(SELECT GROUP_CONCAT(post_title || ' (' || kind || ')', '; ') FROM "
         " (SELECT post_title, kind FROM usage u WHERE u.attachment_id=i.id LIMIT 5)) "
         "FROM images i WHERE i.has_alt=0 AND i.status != 'excluded_private'")
    params = []
    if args.ids:
        ids = [int(x) for x in args.ids.split(",") if x.strip()]
        q += f" AND i.id IN ({','.join('?' * len(ids))})"
        params += ids
    else:
        tiers = args.tiers.split(",")
        q += f" AND i.tier IN ({','.join('?' * len(tiers))})"
        params += tiers
    if not args.redo:
        q += " AND i.proposed_alt IS NULL"
    q += " ORDER BY CASE i.tier WHEN 'P1_content' THEN 1 WHEN 'P2_featured' THEN 2 ELSE 3 END, i.id"
    if args.limit:
        q += f" LIMIT {args.limit}"
    todo = db.execute(q, params).fetchall()
    db.close()

    print(f"to process: {len(todo)} (model={args.model})", flush=True)
    n = cost = errs = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(worker, im, key, args.db, args.api_url, args.model) for im in todo]
        for fut in as_completed(futs):
            aid, alt, err, c = fut.result()
            n += 1
            cost += c
            if err:
                errs += 1
            if n % 50 == 0 or n == len(todo):
                print(f"  {n}/{len(todo)}  ~${cost:.4f}  errors={errs}", flush=True)
    print(f"DONE {n} processed, ~${cost:.4f}, {errs} errors", flush=True)


if __name__ == "__main__":
    main()
