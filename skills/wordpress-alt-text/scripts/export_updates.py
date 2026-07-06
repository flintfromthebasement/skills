#!/usr/bin/env python3
"""wordpress-alt-text — export approved alts from the SQLite DB to alt_updates.json
(the input for apply_alt.php), and mark rows applied after a successful run.

  python3 export_updates.py --db alt.db --out alt_updates.json
  python3 export_updates.py --db alt.db --mark-applied alt_updates.json   # after apply

Exports rows with status='generated' and a non-empty proposed_alt. Rows flagged
needs_visual_review are included unless --skip-flagged; excluded_private never exports.
"""
import argparse, json, sqlite3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="alt.db")
    ap.add_argument("--out", default="alt_updates.json")
    ap.add_argument("--skip-flagged", action="store_true")
    ap.add_argument("--mark-applied", metavar="JSON",
                    help="mark ids in JSON as status='applied_media' instead of exporting")
    args = ap.parse_args()
    db = sqlite3.connect(args.db)

    if args.mark_applied:
        ids = [r["id"] for r in json.load(open(args.mark_applied))]
        db.executemany("UPDATE images SET status='applied_media' WHERE id=? AND status='generated'",
                       [(i,) for i in ids])
        db.commit()
        print(f"marked {db.total_changes} rows applied_media")
        return

    q = "SELECT id, proposed_alt FROM images WHERE status='generated' AND TRIM(COALESCE(proposed_alt,'')) != ''"
    if args.skip_flagged:
        q += " AND needs_visual_review=0"
    rows = [{"id": r[0], "alt": r[1]} for r in db.execute(q).fetchall()]
    json.dump(rows, open(args.out, "w"), indent=1)
    print(f"wrote {len(rows)} records to {args.out}")


if __name__ == "__main__":
    main()
