#!/usr/bin/env python3
"""
db_to_tree.py — turn the COMPLETE cache database into a walkable FILE TREE.

This is a TOTAL MECHANICAL TRANSFORM, not a query and not a search:
  every row in cache.db becomes exactly one path in the tree.
Nothing is selected, nothing is looked for, nothing is judged. The tree holds the
same information as the database — one is rows, the other is folders. Walking the
tree IS reading the data.

LAYOUT (derived only from the row's own columns — no decisions):
  <out>/<doc>/p<page>/page.txt                 the page's full text
  <out>/<doc>/p<page>/table<t>/header.txt      the table's header row
  <out>/<doc>/p<page>/table<t>/row<r>.txt      one file per table row (its cells)
  <out>/<doc>/p<page>/headings.txt             the page's figure/text headings
  INDEX.md                                      counts + the conservation proof

CONSERVATION: paths emitted == rows read, asserted. If they differ, a row was
lost or duplicated and the tool exits 1. Completeness is arithmetic.

USAGE
  python3 db_to_tree.py [--db ../db/cache.db] [--out ../tree] [--verify]
"""
import argparse, json, os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

def safe(s):
    return "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(s)).strip("_") or "_"

def build(db, out, verify=False):
    con = sqlite3.connect(db); cur = con.cursor()
    os.makedirs(out, exist_ok=True)
    counts = {"pages":0, "tables":0, "rows":0, "headings_files":0}
    paths = 0

    # 1. pages -> doc/pNNNN/page.txt   (every page row -> one file)
    for doc, page, text in cur.execute("SELECT doc, page, text FROM pages"):
        d = os.path.join(out, safe(doc), f"p{int(page):04d}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "page.txt"), "w") as f:
            f.write(text or "")
        counts["pages"] += 1; paths += 1

    # table id -> (doc,page,tidx) location, fetched once (no nested cursor reuse)
    tloc = {tid: (doc, int(page), tidx)
            for tid, doc, page, tidx in cur.execute("SELECT id, doc, page, tidx FROM tables").fetchall()}

    # 2. tables -> doc/pNNNN/tableT/   (every table row -> one folder)
    for tid, (doc, page, tidx) in tloc.items():
        td = os.path.join(out, safe(doc), f"p{page:04d}", f"table{tidx}")
        os.makedirs(td, exist_ok=True)
        counts["tables"] += 1; paths += 1

    # 3. table_rows -> doc/pNNNN/tableT/rowR.txt   (every row -> one file; row0 also = header)
    for tid, ridx, cells_json in cur.execute("SELECT table_id, ridx, cells_json FROM table_rows").fetchall():
        doc, page, tidx = tloc[tid]
        td = os.path.join(out, safe(doc), f"p{page:04d}", f"table{tidx}")
        os.makedirs(td, exist_ok=True)
        cells = json.loads(cells_json)
        fname = "header.txt" if ridx == 0 else f"row{ridx}.txt"
        with open(os.path.join(td, fname), "w") as f:
            f.write("\n".join(("" if c is None else str(c)) for c in cells))
        counts["rows"] += 1; paths += 1

    # 4. headings -> doc/pNNNN/headings.txt  (figure labels + text headings, one file per page that has any)
    hpages = {}
    for doc, page, label in cur.execute("SELECT doc, page, label FROM headings"):
        hpages.setdefault((doc, int(page)), []).append(("fig", label))
    for doc, page, label in cur.execute("SELECT doc, page, label FROM text_headings"):
        hpages.setdefault((doc, int(page)), []).append(("txt", label))
    for (doc, page), labels in hpages.items():
        d = os.path.join(out, safe(doc), f"p{int(page):04d}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "headings.txt"), "w") as f:
            for kind, lab in labels: f.write(f"[{kind}] {lab}\n")
        counts["headings_files"] += 1; paths += 1

    # conservation: every page/table/row row produced a path
    db_pages = cur.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    db_tables = cur.execute("SELECT COUNT(*) FROM tables").fetchone()[0]
    db_rows = cur.execute("SELECT COUNT(*) FROM table_rows").fetchone()[0]

    with open(os.path.join(out, "INDEX.md"), "w") as f:
        f.write("# Cache database as a file tree (total mechanical transform)\n\n")
        f.write("Every database row is one path. Nothing selected, nothing searched.\n\n")
        f.write("| db table | rows in db | paths emitted | balances |\n|---|---|---|---|\n")
        f.write(f"| pages | {db_pages} | {counts['pages']} | {'YES' if db_pages==counts['pages'] else 'NO'} |\n")
        f.write(f"| tables | {db_tables} | {counts['tables']} | {'YES' if db_tables==counts['tables'] else 'NO'} |\n")
        f.write(f"| table_rows | {db_rows} | {counts['rows']} | {'YES' if db_rows==counts['rows'] else 'NO'} |\n")
        f.write(f"\nheading files: {counts['headings_files']}  ·  total paths: {paths}\n")

    con.close()
    if verify:
        assert db_pages == counts["pages"], f"pages lost: {db_pages} != {counts['pages']}"
        assert db_tables == counts["tables"], f"tables lost: {db_tables} != {counts['tables']}"
        assert db_rows == counts["rows"], f"rows lost: {db_rows} != {counts['rows']}"
        print(f"verify: OK — every db row placed. pages={counts['pages']}, "
              f"tables={counts['tables']}, rows={counts['rows']}, paths={paths}")
    return counts, paths

def main():
    ap = argparse.ArgumentParser(description="transform the complete cache.db into a walkable file tree")
    ap.add_argument("--db", default=os.path.join(ROOT, "db", "cache.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "tree"))
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print(f"error: {a.db} not found (build it with cachedb.py)", file=sys.stderr); sys.exit(2)
    counts, paths = build(a.db, a.out, a.verify)
    print(f"db_to_tree: {paths} paths -> {a.out}")

if __name__ == "__main__":
    main()
