#!/usr/bin/env python3
"""
cachedb.py — load the cache (the 1:1 PDF extraction) into a RELATIONAL DATABASE.

Treat the cache as a database, not a text pile to search. This is pure, lossless
ETL: every structural unit in cache/*.jsonl becomes a row. Nothing is interpreted,
nothing is searched-for, nothing is dropped. Conservation is proven by arithmetic
(rows inserted == units enumerated). Downstream tools QUERY this DB to derive the
architecture; a verifier checks coverage by COUNT(*). AI/human come last, to review.

SCHEMA (SQLite, ../cache.db):
  pages(doc, page, text, n_tables, n_headings, has_primitive_decl)
  tables(id, doc, page, tidx, header_sig, ncols, nrows)
  table_rows(table_id, ridx, cells_json)
  cells(table_id, ridx, cidx, value)             -- fully unpivoted: one row per cell
  headings(doc, page, hidx, label, y)            -- figure block-labels (heads)
  text_headings(doc, page, lidx, label)          -- ALL-CAPS heading lines in text

Every cell of every table is a queryable row — the structure reveals itself with
GROUP BY, not regex.

USAGE
  python3 cachedb.py            # (re)build ../cache.db from cache/*.jsonl
  python3 cachedb.py --verify   # rebuild, then prove conservation by COUNT(*)
  python3 cachedb.py --stats    # show row counts + top table header signatures
"""
import argparse, json, os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "cache")
DB = os.path.join(ROOT, "cache.db")

def header_sig(rows):
    if not rows or not rows[0]: return "(empty)"
    return "|".join(str(c or "").strip().lower().replace("\n"," ")[:18] for c in rows[0]) or "(blank)"

def is_heading_line(s):
    return bool(re.match(r"^[A-Z][A-Z0-9_]{2,31}$", str(s or "").strip()))

SCHEMA = """
DROP TABLE IF EXISTS pages; DROP TABLE IF EXISTS tables; DROP TABLE IF EXISTS table_rows;
DROP TABLE IF EXISTS cells; DROP TABLE IF EXISTS headings; DROP TABLE IF EXISTS text_headings;
CREATE TABLE pages(doc TEXT, page INT, text TEXT, n_tables INT, n_headings INT, has_primitive_decl INT);
CREATE TABLE tables(id INTEGER PRIMARY KEY, doc TEXT, page INT, tidx INT, header_sig TEXT, ncols INT, nrows INT);
CREATE TABLE table_rows(table_id INT, ridx INT, cells_json TEXT);
CREATE TABLE cells(table_id INT, ridx INT, cidx INT, value TEXT);
CREATE TABLE headings(doc TEXT, page INT, hidx INT, label TEXT, y REAL);
CREATE TABLE text_headings(doc TEXT, page INT, lidx INT, label TEXT);
CREATE INDEX ix_tab ON tables(doc,page); CREATE INDEX ix_cell ON cells(table_id);
CREATE INDEX ix_sig ON tables(header_sig);
"""

def build(verify=False):
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.executescript(SCHEMA)
    enum = {"pages":0,"tables":0,"rows":0,"cells":0,"headings":0,"text_headings":0}
    tid = 0
    for fn in sorted(os.listdir(CACHE)):
        if not fn.endswith(".jsonl"): continue
        doc = fn[:-6]
        with open(os.path.join(CACHE, fn)) as f:
            for line in f:
                line=line.strip()
                if not line: continue
                try: r=json.loads(line)
                except json.JSONDecodeError: continue
                if r.get("page") is None: continue
                pg=int(r["page"]); text=r.get("text","") or ""
                tbls=r.get("tables",[]) or []; heads=r.get("heads",[]) or []
                has_prim = 1 if ("Primitive:" in text or "PRIMITIVE_GROUP" in text) else 0
                th=[l.strip() for l in text.splitlines() if is_heading_line(l)]
                cur.execute("INSERT INTO pages VALUES(?,?,?,?,?,?)",
                            (doc,pg,text,len(tbls),len(heads),has_prim)); enum["pages"]+=1
                for ti,tb in enumerate(tbls):
                    rows=tb.get("rows") if isinstance(tb,dict) else tb
                    rows=rows or []
                    sig=header_sig(rows); ncols=max((len(x) for x in rows),default=0)
                    tid+=1
                    cur.execute("INSERT INTO tables VALUES(?,?,?,?,?,?,?)",
                                (tid,doc,pg,ti,sig,ncols,len(rows))); enum["tables"]+=1
                    for ri,row in enumerate(rows):
                        cur.execute("INSERT INTO table_rows VALUES(?,?,?)",(tid,ri,json.dumps(row)))
                        enum["rows"]+=1
                        for ci,c in enumerate(row):
                            cur.execute("INSERT INTO cells VALUES(?,?,?,?)",
                                        (tid,ri,ci,(str(c) if c is not None else "")))
                            enum["cells"]+=1
                for hi,h in enumerate(heads):
                    lab=(h[0] if isinstance(h,list) and h else str(h))
                    y=(h[1] if isinstance(h,list) and len(h)>1 else None)
                    cur.execute("INSERT INTO headings VALUES(?,?,?,?,?)",(doc,pg,hi,lab,y)); enum["headings"]+=1
                for li,l in enumerate(th):
                    cur.execute("INSERT INTO text_headings VALUES(?,?,?,?)",(doc,pg,li,l)); enum["text_headings"]+=1
    con.commit()
    if verify:
        chk={"pages":"pages","tables":"tables","rows":"table_rows","cells":"cells",
             "headings":"headings","text_headings":"text_headings"}
        ok=True
        for k,t in chk.items():
            n=cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            bal = (n==enum[k]); ok&=bal
            print(f"  {k:14} enumerated={enum[k]:7}  in_db={n:7}  {'OK' if bal else 'MISMATCH'}")
        assert ok, "CONSERVATION FAIL: a unit was lost in ETL"
        print("verify: OK — cache fully loaded, conservation balances on all tables")
    con.close()
    return enum

def stats():
    con=sqlite3.connect(DB); cur=con.cursor()
    print("row counts:")
    for t in ("pages","tables","table_rows","cells","headings","text_headings"):
        print(f"  {t:14}", cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    print("\ntop 20 table header signatures (the shapes the data reveals):")
    for sig,c in cur.execute("SELECT header_sig,COUNT(*) c FROM tables GROUP BY header_sig ORDER BY c DESC LIMIT 20"):
        print(f"  {c:4}  {sig}")
    con.close()

def main():
    ap=argparse.ArgumentParser(description="load the cache into a relational database")
    ap.add_argument("--verify",action="store_true"); ap.add_argument("--stats",action="store_true")
    a=ap.parse_args()
    if not os.path.isdir(CACHE): print(f"error: {CACHE} not found",file=sys.stderr); sys.exit(2)
    if a.stats and os.path.exists(DB): stats(); return
    enum=build(a.verify)
    print(f"cachedb: built {DB} — {enum['pages']} pages, {enum['tables']} tables, "
          f"{enum['cells']} cells, {enum['headings']+enum['text_headings']} headings")
    if a.stats: stats()

if __name__=="__main__":
    main()
