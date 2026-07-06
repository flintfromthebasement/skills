#!/usr/bin/env python3
"""wordpress-alt-text — build a self-contained human-review HTML (thumbnails embedded
as data URIs) from the SQLite DB. Sampled cards per tier + every flagged row + the
in-post backfill table.

  python3 build_review.py --db alt.db --out review.html --site example.com
"""
import argparse, base64, html, io, json, os, sqlite3
import requests
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

THUMB = 360


def thumb_b64(url):
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 alt-bot"})
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
        im.thumbnail((THUMB, THUMB))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=72)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def card(row, thumb):
    rid, file, url, title, tier, alt, pages, flagged = row
    tier_label = {"P1_content": "in content", "P2_featured": "featured", "P3_orphan": "orphan"}[tier]
    img_el = f'<img src="{thumb}" alt="" loading="lazy">' if thumb else '<div class="noimg">image unavailable</div>'
    flag = '<span class="chip warn">needs review</span>' if flagged else ""
    pages_el = f'<div class="pages">{html.escape(pages or "")}</div>' if pages else ""
    return f"""<div class="card">
  <div class="imgwrap">{img_el}</div>
  <div class="body">
    <div class="metarow"><span class="chip t-{tier}">{tier_label}</span>{flag}<span class="fid">#{rid}</span></div>
    <p class="alt">{html.escape(alt or "(empty — flagged for human review)")}</p>
    <div class="file">{html.escape(file or "")}</div>
    {pages_el}
  </div>
</div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="alt.db")
    ap.add_argument("--out", default="review.html")
    ap.add_argument("--site", default="WordPress site", help="label shown in the artifact header")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    summary = json.loads(db.execute("SELECT v FROM meta WHERE k='summary'").fetchone()[0])
    gen = db.execute("SELECT COUNT(*), COALESCE(SUM(cost),0), SUM(needs_visual_review) "
                     "FROM images WHERE status='generated'").fetchone()

    samples = []
    for tier, n in (("P1_content", 40), ("P2_featured", 10), ("P3_orphan", 30)):
        samples += db.execute(
            "SELECT i.id, i.file, i.url, i.title, i.tier, i.proposed_alt, "
            "(SELECT GROUP_CONCAT(post_title, '; ') FROM (SELECT DISTINCT post_title FROM usage u WHERE u.attachment_id=i.id LIMIT 3)), "
            "i.needs_visual_review FROM images i "
            "WHERE i.tier=? AND i.status='generated' AND i.needs_visual_review=0 "
            "ORDER BY (i.id * 2654435761) % 1000 LIMIT ?", (tier, n)).fetchall()
    flagged = db.execute(
        "SELECT i.id, i.file, i.url, i.title, i.tier, i.proposed_alt, '', 1 FROM images i "
        "WHERE i.status='generated' AND i.needs_visual_review=1 LIMIT 12").fetchall()

    print(f"embedding {len(samples) + len(flagged)} thumbnails...", flush=True)
    cards_by_tier = {"P1_content": [], "P2_featured": [], "P3_orphan": []}
    for row in samples:
        cards_by_tier[row[4]].append(card(row, thumb_b64(row[2])))
    flag_cards = [card(row, thumb_b64(row[2])) for row in flagged]

    inpost = db.execute("""
      SELECT pi.post_title, pi.post_type, pi.src, pi.attachment_id,
             COALESCE(NULLIF(i.cur_alt,''), i.proposed_alt) AS fill_alt, i.has_alt
      FROM post_images pi LEFT JOIN images i ON i.id = pi.attachment_id
      WHERE pi.has_alt_attr=0 OR TRIM(COALESCE(pi.alt_value,''))=''
      ORDER BY pi.post_title, pi.tag_index""").fetchall()
    inpost_rows = []
    for ptitle, ptype, src, aid, fill, has in inpost:
        short_src = src.split("/")[-1][:60] if src else "(no src)"
        if aid is None:
            status = '<span class="chip warn">no attachment match</span>'
            fill_txt = "manual review"
        elif has:
            status = '<span class="chip ok">from existing media alt</span>'
            fill_txt = fill or ""
        else:
            status = '<span class="chip new">from new AI alt</span>'
            fill_txt = fill or "(pending)"
        inpost_rows.append(
            f"<tr><td>{html.escape(ptitle or '')}<span class='ptype'>{html.escape(ptype or '')}</span></td>"
            f"<td class='mono'>{html.escape(short_src)}</td><td>{status}</td>"
            f"<td class='alttd'>{html.escape(fill_txt)}</td></tr>")

    excluded = db.execute("SELECT COUNT(*) FROM images WHERE status='excluded_private'").fetchone()[0]
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_template.html")
    tpl = open(tpl_path).read()
    out = (tpl
           .replace("__SITE__", html.escape(args.site))
           .replace("__TOTAL__", f"{summary['total_images']:,}")
           .replace("__MISSING__", f"{summary['missing_alt']:,}")
           .replace("__P1__", f"{summary['P1_content']:,}")
           .replace("__P2__", f"{summary['P2_featured']:,}")
           .replace("__P3__", f"{summary['P3_orphan']:,}")
           .replace("__GENDONE__", f"{gen[0]:,}")
           .replace("__COST__", f"${gen[1]:.2f}")
           .replace("__FLAGGED__", f"{gen[2] or 0:,}")
           .replace("__EXCLUDED__", f"{excluded:,}")
           .replace("__INPOST_TAGS__", f"{summary.get('inpost_missing_alt', 0):,}")
           .replace("__INPOST_POSTS__", f"{summary.get('inpost_posts_affected', 0):,}")
           .replace("__CARDS_P1__", "\n".join(cards_by_tier["P1_content"]))
           .replace("__CARDS_P2__", "\n".join(cards_by_tier["P2_featured"]))
           .replace("__CARDS_P3__", "\n".join(cards_by_tier["P3_orphan"]))
           .replace("__CARDS_FLAGGED__", "\n".join(flag_cards) or "<p class='none'>None flagged so far.</p>")
           .replace("__INPOST_ROWS__", "\n".join(inpost_rows) or "<tr><td colspan='4'>No in-post data (manifest mode) — use inpost_alt.php DRY_RUN=1 to scope Phase 2.</td></tr>"))
    open(args.out, "w").write(out)
    print(f"wrote {args.out} ({len(out)//1024} KB)")


if __name__ == "__main__":
    main()
