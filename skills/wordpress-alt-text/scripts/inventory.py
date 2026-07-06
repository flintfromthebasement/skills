#!/usr/bin/env python3
"""wordpress-alt-text — Stage 1 inventory into a local SQLite DB. READ-ONLY against the site.

Two source modes (pick one):
  A) Manifest mode (works with WP-CLI-only access, no DB creds):
       wp eval-file inventory.php > manifest.json     # on the site
       python3 inventory.py --db alt.db --from-manifest manifest.json
     Note: manifest mode does not populate the post_images table (per-<img>-tag scan);
     use inpost_alt.php DRY_RUN=1 to scope Phase 2 instead.

  B) Direct MySQL mode (read-only DB user recommended):
       WP_DB_HOST=1.2.3.4 WP_DB_USER=ro WP_DB_PASS=... WP_DB_NAME=wp \
       python3 inventory.py --db alt.db --base-url https://example.com/wp-content/uploads \
         --post-types post,page --exclude-pattern 'uploads/private-dir/'

Env (mode B): WP_DB_HOST, WP_DB_USER, WP_DB_PASS, WP_DB_NAME, WP_DB_PREFIX (default wp_)
--exclude-pattern marks matching files status='excluded_private' (e.g. access-protected
upload dirs that 403 anonymous fetches — never send those through the pipeline).
"""
import argparse, json, os, re, sqlite3, sys

SCHEMA = """
DROP TABLE IF EXISTS images; DROP TABLE IF EXISTS usage; DROP TABLE IF EXISTS post_images;
CREATE TABLE images (
  id INTEGER PRIMARY KEY, file TEXT, url TEXT, mime TEXT, width INTEGER, height INTEGER,
  title TEXT, caption TEXT, parent INTEGER, post_date TEXT, cur_alt TEXT, has_alt INTEGER,
  tier TEXT, proposed_alt TEXT, keyword_used TEXT, chars INTEGER,
  needs_visual_review INTEGER DEFAULT 0, fetch_error TEXT, model_error TEXT, cost REAL,
  status TEXT DEFAULT 'pending');
CREATE TABLE usage (attachment_id INTEGER, post_id INTEGER, post_type TEXT, post_title TEXT,
  post_slug TEXT, kind TEXT);
CREATE TABLE post_images (post_id INTEGER, post_type TEXT, post_title TEXT, post_slug TEXT,
  src TEXT, attachment_id INTEGER, has_alt_attr INTEGER, alt_value TEXT, tag_index INTEGER);
CREATE INDEX idx_usage_att ON usage(attachment_id);
CREATE INDEX idx_pi_post ON post_images(post_id);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


def norm_base(path):
    b = os.path.basename(path or "").lower()
    b = re.sub(r"\?.*$", "", b)
    b = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", b)
    b = re.sub(r"-scaled(\.\w+)$", r"\1", b)
    return b


def open_db(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def finish(db, summary, post_types, exclude_re):
    if exclude_re:
        rows = db.execute("SELECT id, file, url FROM images").fetchall()
        pat = re.compile(exclude_re)
        excl = [r[0] for r in rows if pat.search(r[1] or "") or pat.search(r[2] or "")]
        if excl:
            db.executemany("UPDATE images SET status='excluded_private' WHERE id=?",
                           [(i,) for i in excl])
        summary["excluded_private"] = len(excl)
    missing_inpost = db.execute(
        "SELECT COUNT(*) FROM post_images WHERE has_alt_attr=0 OR TRIM(COALESCE(alt_value,''))=''").fetchone()[0]
    posts_affected = db.execute(
        "SELECT COUNT(DISTINCT post_id) FROM post_images WHERE has_alt_attr=0 OR TRIM(COALESCE(alt_value,''))=''").fetchone()[0]
    summary["inpost_img_tags"] = db.execute("SELECT COUNT(*) FROM post_images").fetchone()[0]
    summary["inpost_missing_alt"] = missing_inpost
    summary["inpost_posts_affected"] = posts_affected
    db.execute("INSERT OR REPLACE INTO meta VALUES ('summary', ?)", (json.dumps(summary),))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('post_types', ?)", (",".join(post_types),))
    db.commit()
    db.close()
    print(json.dumps(summary, indent=2))


def from_manifest(args):
    data = json.load(open(args.from_manifest))
    db = open_db(args.db)
    summary = {"total_images": 0, "has_alt": 0, "missing_alt": 0,
               "P1_content": 0, "P2_featured": 0, "P3_orphan": 0}
    for img in data["images"]:
        summary["total_images"] += 1
        if img["has_alt"]:
            summary["has_alt"] += 1
        else:
            summary["missing_alt"] += 1
            summary[img["tier"]] += 1
        dim = img.get("dim") or (None, None)
        db.execute("INSERT INTO images (id,file,url,mime,width,height,title,caption,parent,post_date,cur_alt,has_alt,tier) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (img["id"], img["file"], img["url"], img["mime"], dim[0], dim[1],
                    img.get("title"), img.get("caption"), img.get("parent"), img.get("date"),
                    img.get("cur_alt", ""), 1 if img["has_alt"] else 0, img["tier"]))
        for u in img.get("used_content", []):
            db.execute("INSERT INTO usage VALUES (?,?,?,?,?,'content')",
                       (img["id"], u["id"], u["type"], u["title"], u["slug"]))
        for u in img.get("used_featured", []):
            db.execute("INSERT INTO usage VALUES (?,?,?,?,?,'featured')",
                       (img["id"], u["id"], u["type"], u["title"], u["slug"]))
    finish(db, summary, args.post_types.split(","), args.exclude_pattern)


def from_mysql(args):
    import pymysql
    need = {k: os.environ.get(k) for k in ("WP_DB_HOST", "WP_DB_USER", "WP_DB_PASS", "WP_DB_NAME")}
    missing = [k for k, v in need.items() if not v]
    if missing:
        sys.exit(f"missing env: {', '.join(missing)}")
    prefix = os.environ.get("WP_DB_PREFIX", "wp_")
    if not args.base_url:
        sys.exit("--base-url is required in MySQL mode (e.g. https://example.com/wp-content/uploads)")
    baseurl = args.base_url.rstrip("/")
    post_types = [t.strip() for t in args.post_types.split(",") if t.strip()]

    conn = pymysql.connect(host=need["WP_DB_HOST"], user=need["WP_DB_USER"], password=need["WP_DB_PASS"],
                           database=need["WP_DB_NAME"], charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor)
    cur = conn.cursor()
    P, M = f"{prefix}posts", f"{prefix}postmeta"

    print("1/6 attachments...", flush=True)
    cur.execute(f"SELECT ID, post_title, post_excerpt, post_mime_type, post_parent, post_date "
                f"FROM {P} WHERE post_type='attachment' AND post_mime_type LIKE 'image/%%'")
    atts = cur.fetchall()

    print("2/6 attached files...", flush=True)
    cur.execute(f"SELECT post_id, meta_value FROM {M} WHERE meta_key='_wp_attached_file'")
    file_by_id, id_by_base = {}, {}
    for r in cur.fetchall():
        file_by_id[r["post_id"]] = r["meta_value"]
        id_by_base[norm_base(r["meta_value"])] = r["post_id"]

    print("3/6 alt + dims...", flush=True)
    cur.execute(f"SELECT post_id, meta_value FROM {M} WHERE meta_key='_wp_attachment_image_alt'")
    alt_by_id = {r["post_id"]: r["meta_value"] for r in cur.fetchall()}
    cur.execute(f"SELECT post_id, meta_value FROM {M} WHERE meta_key='_wp_attachment_metadata'")
    dim_by_id = {}
    for r in cur.fetchall():
        m = re.search(r's:5:"width";i:(\d+);s:6:"height";i:(\d+);', r["meta_value"] or "")
        if m:
            dim_by_id[r["post_id"]] = (int(m.group(1)), int(m.group(2)))

    print("4/6 featured usage...", flush=True)
    cur.execute(f"SELECT pm.meta_value att, pm.post_id used, p.post_type ptype, p.post_title ptitle, p.post_name pslug "
                f"FROM {M} pm JOIN {P} p ON p.ID = pm.post_id "
                f"WHERE pm.meta_key='_thumbnail_id' AND p.post_status='publish'")
    featured = {}
    for r in cur.fetchall():
        try:
            featured.setdefault(int(r["att"]), []).append(r)
        except (TypeError, ValueError):
            pass

    print("5/6 published content scan...", flush=True)
    types_sql = ",".join(["%s"] * len(post_types))
    cur.execute(f"SELECT ID, post_type, post_title, post_name, post_content FROM {P} "
                f"WHERE post_status='publish' AND post_type IN ({types_sql}) "
                f"AND (post_content LIKE '%%wp-image-%%' OR post_content LIKE '%%wp-content/uploads%%' "
                f"OR post_content LIKE '%%<img%%')", post_types)
    posts = cur.fetchall()
    conn.close()

    content_use, post_images = {}, []
    img_tag_re = re.compile(r"<img\b[^>]*>", re.I)
    for p in posts:
        c = p["post_content"] or ""
        found = set()
        for m in re.findall(r"wp-image-(\d+)", c):
            found.add(int(m))
        for m in re.findall(r'"id"\s*:\s*(\d+)', c):
            if int(m) in file_by_id:
                found.add(int(m))
        for u in re.findall(r"wp-content/uploads/[^\"'\s)]+\.(?:jpe?g|png|gif|webp|svg)", c, re.I):
            aid = id_by_base.get(norm_base(u))
            if aid:
                found.add(aid)
        for aid in found:
            content_use.setdefault(aid, []).append(p)
        for i, tag in enumerate(img_tag_re.findall(c)):
            src_m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', tag, re.I)
            alt_m = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', tag, re.I)
            src = src_m.group(1) if src_m else ""
            aid = None
            cls_m = re.search(r"wp-image-(\d+)", tag)
            if cls_m:
                aid = int(cls_m.group(1))
            elif src and "wp-content/uploads" in src:
                aid = id_by_base.get(norm_base(src))
            post_images.append((p["ID"], p["post_type"], p["post_title"], p["post_name"], src, aid,
                                1 if alt_m else 0, alt_m.group(1) if alt_m else None, i))

    print("6/6 writing sqlite...", flush=True)
    db = open_db(args.db)
    summary = {"total_images": 0, "has_alt": 0, "missing_alt": 0,
               "P1_content": 0, "P2_featured": 0, "P3_orphan": 0}
    for a in atts:
        aid = a["ID"]
        alt = (alt_by_id.get(aid) or "").strip()
        has = alt != ""
        uc, uf = content_use.get(aid, []), featured.get(aid, [])
        tier = "has_alt" if has else ("P1_content" if uc else ("P2_featured" if uf else "P3_orphan"))
        summary["total_images"] += 1
        if has:
            summary["has_alt"] += 1
        else:
            summary["missing_alt"] += 1
            summary[tier] += 1
        f = file_by_id.get(aid, "")
        dim = dim_by_id.get(aid)
        db.execute("INSERT INTO images (id,file,url,mime,width,height,title,caption,parent,post_date,cur_alt,has_alt,tier) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (aid, f, f"{baseurl}/{f}" if f else "", a["post_mime_type"],
                    dim[0] if dim else None, dim[1] if dim else None,
                    a["post_title"], a["post_excerpt"], a["post_parent"], str(a["post_date"]),
                    alt, 1 if has else 0, tier))
        for u in uc:
            db.execute("INSERT INTO usage VALUES (?,?,?,?,?,'content')",
                       (aid, u["ID"], u["post_type"], u["post_title"], u["post_name"]))
        for u in uf:
            db.execute("INSERT INTO usage VALUES (?,?,?,?,?,'featured')",
                       (aid, u["used"], u["ptype"], u["ptitle"], u["pslug"]))
    db.executemany("INSERT INTO post_images VALUES (?,?,?,?,?,?,?,?,?)", post_images)
    finish(db, summary, post_types, args.exclude_pattern)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="alt.db")
    ap.add_argument("--from-manifest", help="ingest manifest.json produced by inventory.php")
    ap.add_argument("--base-url", default="", help="uploads base URL (MySQL mode)")
    ap.add_argument("--post-types", default="post,page")
    ap.add_argument("--exclude-pattern", default="", help="regex; matching files marked excluded_private")
    args = ap.parse_args()
    if args.from_manifest:
        from_manifest(args)
    else:
        from_mysql(args)


if __name__ == "__main__":
    main()
