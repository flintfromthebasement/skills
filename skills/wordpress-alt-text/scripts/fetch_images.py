#!/usr/bin/env python3
"""
wordpress-alt-text — API-FREE fallback helper. Downloads missing-alt images locally and
downscales them so the HOST AGENT (e.g. Claude Code) can view them with its OWN vision (via
its file-read tool) and write alt — no external vision API needed.

Workflow for the fallback (see references/models-and-fallbacks.md):
  1. python3 fetch_images.py --manifest manifest.json --tiers P1_content --limit 50
     -> writes ./alt-images/<id>.jpg  and  ./alt-images/index.jsonl (id, local_path, context)
  2. The agent reads each ./alt-images/<id>.jpg, applies the prompt contract
     (references/prompt-and-seo.md), and appends a row to results.jsonl shaped exactly like
     generate.py would: {"id","tier","url","file","title","pages","proposed_alt",
     "keyword_used","chars","needs_visual_review":false,"fetch_error":"","model_error":""}
  3. Continue with make_gallery.py + apply_alt.php as normal.

Deps: requests, Pillow (+ cairosvg for SVGs).
"""
import os, sys, json, io, argparse
import requests
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
MAXDIM = 768

def fetch(url, is_svg, out):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 alt-bot"}); r.raise_for_status()
    raw = r.content
    if is_svg or url.lower().endswith(".svg"):
        import cairosvg; raw = cairosvg.svg2png(bytestring=raw, output_width=MAXDIM, background_color="white")
    im = Image.open(io.BytesIO(raw))
    try: im.seek(0)
    except Exception: pass
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255)); im = im.convert("RGBA")
        bg.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None); im = bg
    else: im = im.convert("RGB")
    im.thumbnail((MAXDIM, MAXDIM)); im.save(out, format="JPEG", quality=85)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=""); ap.add_argument("--db", default="")
    ap.add_argument("--outdir", default="alt-images")
    ap.add_argument("--tiers", default="P1_content,P2_featured,P3_orphan")
    ap.add_argument("--ids", default=""); ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    tiers = set(args.tiers.split(","))
    want = set(int(x) for x in args.ids.split(",") if x.strip()) if args.ids else None
    sel = []
    if args.db:
        import sqlite3
        con = sqlite3.connect(args.db)
        rows = con.execute(
            "SELECT i.id, i.url, i.file, i.mime, i.title, i.tier, "
            "(SELECT GROUP_CONCAT(post_title, '; ') FROM (SELECT DISTINCT post_title FROM usage u WHERE u.attachment_id=i.id LIMIT 4)) "
            "FROM images i WHERE i.has_alt=0 AND i.status != 'excluded_private' AND i.proposed_alt IS NULL").fetchall()
        con.close()
        for rid, url, file, mime, title, tier, pages in rows:
            if want is not None:
                if rid not in want: continue
            elif tier not in tiers: continue
            sel.append({"id": rid, "url": url, "file": file, "mime": mime, "title": title,
                        "tier": tier, "used_content": [{"title": pages}] if pages else [], "has_alt": False})
    else:
        data = json.load(open(args.manifest or "manifest.json"))
        for img in data["images"]:
            if img["has_alt"]: continue
            if want is not None:
                if img["id"] not in want: continue
            elif img["tier"] not in tiers: continue
            sel.append(img)
    if args.limit: sel = sel[:args.limit]
    idx = open(os.path.join(args.outdir, "index.jsonl"), "w")
    ok = err = 0
    for img in sel:
        p = os.path.join(args.outdir, f"{img['id']}.jpg")
        try:
            fetch(img["url"], img["mime"] == "image/svg+xml", p); ok += 1; localp = p; fe = ""
        except Exception as e:
            localp = ""; fe = f"fetch: {str(e)[:120]}"; err += 1
        pages = "; ".join(u.get("title","?") for u in (img.get("used_content") or [])[:4])
        idx.write(json.dumps({"id": img["id"], "tier": img["tier"], "url": img["url"], "file": img.get("file",""),
                              "title": img.get("title",""), "pages": pages, "local_path": localp,
                              "fetch_error": fe}, ensure_ascii=False) + "\n")
    idx.close()
    print(f"fetched {ok}, errors {err} -> {args.outdir}/ (read each .jpg, write results.jsonl rows)")

if __name__ == "__main__":
    main()
